from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ParsedPage:
    document_id: str
    page_number: int
    text: str
    metadata: dict[str, str | int | list[int] | None]


@dataclass(frozen=True, slots=True)
class ParsedChunk:
    text: str
    raw_text: str
    index: int
    metadata: dict


class ParserStrategy(Protocol):
    async def parse(
        self, content: bytes, filename: str = ""
    ) -> list[ParsedChunk]: ...
