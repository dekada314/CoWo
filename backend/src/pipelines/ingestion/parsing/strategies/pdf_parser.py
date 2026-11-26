import io

from pypdf import PdfReader

from src.pipelines.ingestion.chunkers.base_chunker import BaseChunker
from src.pipelines.ingestion.parsing.strategies.parser_strategy import (
    ParsedChunk,
    ParsedPage,
)


class PdfStrategy:
    def __init__(self, chunker: BaseChunker):
        self._chunker = chunker

    async def parse(
        self, content: bytes, filename: str = "unknown.pdf"
    ) -> list[ParsedChunk]:
        pages: list[ParsedPage] = []
        document = PdfReader(io.BytesIO(content))
        for page_number, page in enumerate(document.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(
                    ParsedPage(
                        document_id=filename,
                        page_number=page_number,
                        text=text,
                        metadata={
                            "source_format": "pdf",
                            "page": page_number,
                        },
                    )
                )
        return self._chunker.get_chunks(pages)
