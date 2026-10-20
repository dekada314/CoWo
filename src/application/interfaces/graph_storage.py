from typing import Any, Protocol


class GraphStorage(Protocol):
    async def create_domain(
        self, name: str, summary: str, embedding: list[float]
    ) -> str: ...
    async def create_concept(
        self,
        name: str,
        summary: str,
        embedding: list[float],
        domain_id: str | None = None,
    ) -> str: ...
    async def create_card(
        self, summary: str, document_id: str, key_points: list[str]
    ) -> str: ...
    async def get_concept_by_id(self, concept_id: str) -> dict | None: ...
    async def find_similar_domains(
        self, embedding: list[float], top_k: int = 3
    ) -> list[dict]: ...
    async def find_similar_concepts(
        self, embedding: list[float], top_k: int = 5
    ) -> list[dict]: ...
    async def create_relation(
        self, source_id: str, target_id: str, weight: float = 1.0
    ) -> None: ...
    async def link_card_to_concept(
        self, card_id: str, concept_id: str, relevance: float = 1.0
    ) -> None: ...
    async def link_concept_to_domain(
        self, conept_id: str, domain_id: str, relevance: float = 1.0
    ) -> None: ...
    async def traverse_from_concepts(
        self, concept_ids: list[str], hops: int = 2
    ) -> dict: ...
    async def get_cards_for_concepts(
        self, concept_ids: list[str]
    ) -> list[dict]: ...
