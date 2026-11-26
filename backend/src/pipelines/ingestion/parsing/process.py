import asyncio
import json
import sys
from dataclasses import asdict

from src.pipelines.ingestion.parsing.strategies.parser_strategy import (
    ParsedChunk,
    ParsedPage,
)


class AnalystChunker:
    def __init__(self, chunk_chars: int, max_text_chars: int):
        self.chunk_chars = chunk_chars
        self.max_text_chars = max_text_chars

    def get_chunks(self, pages: list[ParsedPage]) -> list[ParsedChunk]:
        if sum(len(page.text) for page in pages) > self.max_text_chars:
            raise ValueError("document_text_limit_exceeded")
        result: list[ParsedChunk] = []
        for page in pages:
            for start in range(0, len(page.text), self.chunk_chars):
                text = page.text[start : start + self.chunk_chars].strip()
                if text:
                    result.append(
                        ParsedChunk(
                            text=text,
                            raw_text=text,
                            index=len(result),
                            metadata={**page.metadata, "page": page.page_number},
                        )
                    )
        return result


async def parse_document(
    content: bytes,
    filename: str,
    chunk_chars: int,
    max_text_chars: int,
):
    from src.pipelines.ingestion.parsing.parser_context import RAGDocumentParser
    from src.pipelines.ingestion.parsing.strategies.docx_strategy import DocxStrategy
    from src.pipelines.ingestion.parsing.strategies.pdf_parser import PdfStrategy
    from src.pipelines.ingestion.parsing.strategies.plain_text_strategy import (
        PlainTextStrategy,
    )

    chunker = AnalystChunker(chunk_chars, max_text_chars)
    parser = RAGDocumentParser()
    parser.register_strategy("txt", PlainTextStrategy(chunker))
    parser.register_strategy("md", PlainTextStrategy(chunker))
    parser.register_strategy("docx", DocxStrategy(chunker))
    parser.register_strategy("pdf", PdfStrategy(chunker))
    chunks = await parser.parse(content, filename)
    return chunks


def main() -> None:
    known_errors = {
        "document_file_limit_exceeded",
        "document_text_limit_exceeded",
        "document_has_no_text",
    }
    try:
        (
            filename,
            chunk_chars,
            max_text_chars,
            max_bytes,
        ) = sys.argv[1:]
        content = sys.stdin.buffer.read(int(max_bytes) + 1)
        if len(content) > int(max_bytes):
            raise ValueError("document_file_limit_exceeded")
        chunks = asyncio.run(
            parse_document(
                content,
                filename,
                int(chunk_chars),
                int(max_text_chars),
            )
        )
        if not chunks:
            raise ValueError("document_has_no_text")
        json.dump([asdict(chunk) for chunk in chunks], sys.stdout, ensure_ascii=False)
    except Exception as exc:
        code = str(exc) if str(exc) in known_errors else "document_parse_failed"
        json.dump(
            {"error": code, "error_type": type(exc).__name__},
            sys.stdout,
            ensure_ascii=False,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
