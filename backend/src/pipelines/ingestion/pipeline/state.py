from typing import TypedDict

from src.application.ingestion.contracts import KnowledgeCard


class IngestionState(TypedDict, total=False):
    content: bytes
    filename: str
    fragments: list[str]
    card: KnowledgeCard
