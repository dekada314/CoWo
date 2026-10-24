from typing import Protocol


class GraphStorage(Protocol):
    async def create_domain(
        self,
        name: str,
        summary: str,
        embedding: list[float],
    ) -> str: ...

    async def get_domain_by_id(self, domain_id: str) -> dict | None: ...

    async def find_similar_domains(
        self,
        embedding: list[float],
        top_k: int = 3,
    ) -> list[dict]: ...

    async def create_concept(
        self,
        name: str,
        summary: str,
        embedding: list[float],
        domain_id: str | None = None,
    ) -> str: ...

    async def get_concept_by_id(self, concept_id: str) -> dict | None: ...

    async def find_similar_concepts(
        self,
        embedding: list[float],
        top_k: int = 5,
    ) -> list[dict]: ...

    async def create_card(
        self,
        summary: str,
        document_id: str,
        key_points: list[str],
    ) -> str: ...

    async def get_card_by_id(self, card_id: str) -> dict | None: ...

    async def create_chunk(
        self,
        text: str,
        embedding: list[float],
        card_id: str,
        index: int,
    ) -> str: ...

    async def find_similar_chunks(
        self,
        embedding: list[float],
        top_k: int = 10,
    ) -> list[dict]: ...

    async def get_chunks_for_card(self, card_id: str) -> list[dict]: ...

    async def create_relation(
        self,
        source_id: str,
        target_id: str,
        weight: float = 1.0,
    ) -> None: ...

    async def link_card_to_concept(
        self,
        card_id: str,
        concept_id: str,
        relevance: float = 1.0,
    ) -> None: ...

    async def link_concept_to_domain(
        self,
        concept_id: str,
        domain_id: str,
        relevance: float = 1.0,
    ) -> None: ...

    async def link_chunk_to_card(
        self,
        chunk_id: str,
        card_id: str,
    ) -> None: ...

    async def traverse_from_concepts(
        self,
        concept_ids: list[str],
        hops: int = 2,
    ) -> dict: ...

    async def get_cards_for_concepts(
        self,
        concept_ids: list[str],
    ) -> list[dict]: ...

    async def get_domains_for_concepts(
        self,
        concept_ids: list[str],
    ) -> list[dict]: ...
