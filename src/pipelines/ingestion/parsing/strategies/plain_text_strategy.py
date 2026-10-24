from src.pipelines.ingestion.chunkers.base_chunker import BaseChunker

from pipelines.ingestion.parsing.strategies.parser_strategy import (
    ParsedChunk,
    ParsedPage,
)


class PlainTextStrategy:
    def __init__(self, chunker: BaseChunker):
        self._chunker = chunker

    async def parse(
        self, content: bytes, filename: str = "unknown.txt"
    ) -> list[ParsedChunk]:
        text = content.decode("utf-8")
        if not text.strip():
            return []

        pages = [
            ParsedPage(
                document_id=filename,
                page_number=1,
                text=text,
                metadata={},
            )
        ]

        chunks = self._chunker.get_chunks(pages)
        return [
            ParsedChunk(
                text=chunk.text,
                raw_text=chunk.text,
                index=chunk.index,
                metadata=dict(chunk.metadata),
            )
            for chunk in chunks
        ]
