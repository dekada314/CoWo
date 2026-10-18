from typing import Any, Protocol


class GraphStorage(Protocol):
    async def create_concept(
        self,
        name: str,
        description: str,
        embedding: list[float],
        domain_id: str | None = None,
    ) -> str: ...
    async def get_concept(self, concept_id: str) -> dict | None: ...
    async def find_similar_concepts(
        self, embedding: list[float], top_k: int = 5
    ) -> list[dict]: ...
    async def create_relation(
        self, source_id: str, target_id: str, weight: float = 1.0
    ) -> None: ...
    async def link_card_to_concept(
        self, card_id: str, concept_id: str, relevance: float = 1.0
    ) -> None: ...
    async def traverse_from_concepts(
        self, concept_ids: list[str], hops: int = 2
    ) -> dict: ...
    async def get_cards_for_concepts(
        self, concept_ids: list[str]
    ) -> list[dict]: ...
