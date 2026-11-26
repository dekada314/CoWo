from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddedTopic:
    id: str
    name: str
    summary: str
    embedding: list[float]
    aliases: tuple[str, ...] = ()
    is_new: bool = True


@dataclass(frozen=True)
class GraphCommunity:
    id: str
    name: str
    summary: str
    concept_ids: tuple[str, ...]


@dataclass(frozen=True)
class GraphProjection:
    card_id: str
    community_id: str
    community_name: str
    community_summary: str
    domain: EmbeddedTopic
    concepts: list[EmbeddedTopic]


class GraphStorage(ABC):
    @abstractmethod
    async def ensure_schema(self, dimension: int) -> None: ...

    @abstractmethod
    async def project(self, projection: GraphProjection) -> None: ...

    @abstractmethod
    async def remove_cards(self, card_ids: list[str]) -> None: ...

    @abstractmethod
    async def find_similar_concepts(
        self,
        embedding: list[float],
        top_k: int = 5,
    ) -> list[dict]: ...

    @abstractmethod
    async def traverse_from_concepts(
        self,
        concept_ids: list[str],
        hops: int = 2,
        limit: int = 100,
    ) -> list[dict]: ...

    @abstractmethod
    async def get_concept_neighbors(
        self,
        concept_ids: list[str],
        per_concept: int = 8,
    ) -> list[dict]: ...

    @abstractmethod
    async def get_cards_for_concepts(
        self,
        concept_ids: list[str],
        limit: int = 100,
    ) -> list[dict]: ...

    @abstractmethod
    async def get_visual_graph(self) -> dict: ...

    @abstractmethod
    async def get_card_ids_for_concept(
        self,
        concept_id: str,
    ) -> list[str] | None: ...

    @abstractmethod
    async def detect_communities(self, max_iterations: int = 10) -> list[dict]: ...

    @abstractmethod
    async def apply_communities(
        self,
        communities: list[GraphCommunity],
    ) -> None: ...
