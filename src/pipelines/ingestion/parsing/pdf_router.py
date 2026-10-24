import io

from pipelines.ingestion.parsing.strategies.docling_strategy import (
    DoclingStrategy,
)
from pipelines.ingestion.parsing.strategies.parser_strategy import ParsedChunk
from pipelines.ingestion.parsing.strategies.pdf_parser import PdfStrategy


class PdfRouter:
    def __init__(
        self,
        docling: DoclingStrategy,
        pymupdf: PdfStrategy,
        docling_enabled: bool = True,
    ):
        self._docling = docling
        self._pymupdf = pymupdf
        self._docling_enabled = docling_enabled

    async def parse(
        self, content: bytes, filename: str = "document.pdf"
    ) -> list[ParsedChunk]:
        if not self._docling_enabled:
            return await self._pymupdf.parse(content, filename)

        if self._needs_docling(content):
            try:
                return await self._docling.parse(content, filename)
            except Exception:
                return await self._pymupdf.parse(content, filename)

        return await self._pymupdf.parse(content, filename)

    @staticmethod
    def _needs_docling(content: bytes) -> bool:
        try:
            import pdf_inspector

            info = pdf_inspector.inspect(io.BytesIO(content))
            return info.is_complex_layout or bool(info.pages_with_tables)
        except Exception:
            return True
