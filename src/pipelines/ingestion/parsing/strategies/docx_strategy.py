from uuid import uuid4

from pipelines.ingestion.parsing.strategies.parser_strategy import (
    ParsedPage,
)


class DocxStrategy:
    def parse(
        self, content: bytes, filename: str = "unknown.docx"
    ) -> list[ParsedPage]:
        import io

        from docx import Document

        doc = Document(io.BytesIO(content))
        pages: list[ParsedPage] = []
        document_id = str(uuid4())
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

        return pages
