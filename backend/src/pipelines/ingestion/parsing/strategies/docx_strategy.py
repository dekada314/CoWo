import io
from uuid import uuid4

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from src.pipelines.ingestion.chunkers.base_chunker import BaseChunker
from src.pipelines.ingestion.parsing.strategies.parser_strategy import (
    ParsedChunk,
    ParsedPage,
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
        current_heading: str | None = None

        section_texts: list[tuple[str | None, list[str]]] = []
        current_paragraphs: list[str] = []

        for block in doc.iter_inner_content():
            if isinstance(block, Paragraph):
                text = block.text.strip()
                if not text:
                    continue
                try:
                    style_name = (block.style.name or "").casefold()
                except (AttributeError, KeyError):
                    style_name = ""
                if style_name.startswith(("heading", "заголовок")):
                    if current_heading or current_paragraphs:
                        section_texts.append((current_heading, current_paragraphs))
                    current_heading = text
                    current_paragraphs = []
                else:
                    current_paragraphs.append(text)
            elif isinstance(block, Table):
                for row in block.rows:
                    cells: list[str] = []
                    for cell in row.cells:
                        value = " ".join(cell.text.split())
                        if value and (not cells or cells[-1] != value):
                            cells.append(value)
                    if cells:
                        current_paragraphs.append(" | ".join(cells))

        if current_heading or current_paragraphs:
            section_texts.append((current_heading, current_paragraphs))

        for section_num, (heading, paragraphs) in enumerate(section_texts, start=1):
            text_parts = ([heading] if heading else []) + paragraphs
            if text_parts:
                pages.append(
                    ParsedPage(
                        document_id=document_id,
                        page_number=section_num,
                        text="\n".join(text_parts),
                        metadata={
                            "source_format": "docx",
                            "heading": heading or "",
                        },
                    )
                )

        if not pages:
            fallback = [
                node.text.strip()
                for node in doc.element.body.iter()
                if node.tag.endswith("}t") and node.text and node.text.strip()
            ]
            if fallback:
                pages.append(
                    ParsedPage(
                        document_id=document_id,
                        page_number=1,
                        text="\n".join(fallback),
                        metadata={
                            "source_format": "docx",
                            "fallback": "xml_text",
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
