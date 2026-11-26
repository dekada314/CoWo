from pathlib import Path

from src.pipelines.ingestion.parsing.strategies.parser_strategy import (
    ParsedChunk,
    ParserStrategy,
)


class RAGDocumentParser:
    def __init__(self) -> None:
        self._strategies: dict[str, ParserStrategy] = {}

    def register_strategy(self, extension: str, strategy: ParserStrategy) -> None:
        ext = extension.lower().lstrip(".")
        if ext in self._strategies:
            raise ValueError(f"Strategy for type {ext} is already registered")

        if not isinstance(strategy, ParserStrategy):
            raise TypeError("strategy must implement ParserStrategy")
        self._strategies[ext] = strategy

    async def parse(
        self,
        content: bytes,
        filename: str,
    ) -> list[ParsedChunk]:
        ext = Path(filename).suffix.lower().lstrip(".")

        strategy = self._strategies.get(ext)
        if not strategy:
            raise ValueError(self._suggest_fix(ext))

        return await strategy.parse(content, filename)

    @staticmethod
    def _suggest_fix(ext: str) -> str:
        return f"Формат .{ext} пока не поддерживается."
