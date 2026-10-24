import io
from uuid import uuid4

from docx import Document

from pipelines.ingestion.parsing.strategies.parser_strategy import (
    ParsedPage,
)
from src.pipelines.ingestion.chunkers.base_chunker import BaseChunker
from src.pipelines.ingestion.parsing.strategies.parser_strategy import (
    ParsedChunk,
)


class DocxStrategy:
    def __init__(self, chunker: BaseChunker):
        self._chunker = chunker

    async def parse(
        self, content: bytes, filename: str = "unknown.docx"
    ) -> list[ParsedChunk]:
        doc = Document(io.BytesIO(content))
        pages: list[ParsedPage] = []
        document_id = filename or str(uuid4())
        current_heading = None

        section_texts: list[tuple[str | None, list[str]]] = []
        current_paragraphs: list[str] = []

        for paragraph in doc.paragraphs:
            if paragraph.style.name.startswith("Heading"):
                if current_paragraphs:
                    section_texts.append((current_heading, current_paragraphs))
                current_heading = paragraph.text.strip()
                current_paragraphs = []
            elif paragraph.text.strip():
                current_paragraphs.append(paragraph.text.strip())

        if current_paragraphs:
            section_texts.append((current_heading, current_paragraphs))

        for section_num, (heading, paragraphs) in enumerate(
            section_texts, start=1
        ):
            pages.append(
                ParsedPage(
                    document_id=document_id,
                    page_number=section_num,
                    text="\n".join(paragraphs),
                    metadata={
                        "source_format": "docx",
                        "heading": heading or "",
                    },
                )
            )

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
