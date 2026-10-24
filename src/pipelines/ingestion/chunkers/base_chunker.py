from typing import Protocol

from pipelines.ingestion.parsing.strategies.parser_strategy import (
    ParsedChunk,
    ParsedPage,
)


class BaseChunker(Protocol):
    def get_chunks(self, pages: list[ParsedPage]) -> list[ParsedChunk]: ...
