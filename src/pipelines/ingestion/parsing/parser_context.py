from typing import runtime_checkable

from src.pipelines.ingestion.parsing.pdf_router import PdfRouter
from src.pipelines.ingestion.parsing.strategies.docx_strategy import (
    DocxStrategy,
)
from src.pipelines.ingestion.parsing.strategies.parser_strategy import (
    ParserStrategy,
)
from src.pipelines.ingestion.parsing.strategies.plain_text_strategy import (
    PlainTextStrategy,
)


class RAGDocumentParser:
    def __init__(self):
        self._strategies = {}

    @runtime_checkable
    def register_strategy(
        self, extension: str, strategy: ParserStrategy
    ) -> None:
        ext = extension.lower()
        if ext in self._strategies:
            raise ValueError(f"Strategy for type {ext} already registrated")

        if isinstance(strategy, ParserStrategy):
            self._strategies[ext] = strategy

    def load_and_parse(self, file_path: str) -> str:
        ext = file_path.split(".")[-1].lower()

        strategy = self._strategies.get(ext)
        if not strategy:
            raise ValueError(self._suggest_fix(ext))

        return strategy.parse(file_path)

    def _suggest_fix(self, ext: str) -> str:
        return f"Формат .{ext} пока не поддерживается."
