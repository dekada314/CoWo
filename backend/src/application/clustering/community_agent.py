import asyncio
import hashlib
from typing import Protocol

import structlog

from src.application.clustering.contracts import CommunityDescription
from src.application.interfaces.storages.graph_storage import (
    GraphCommunity,
    GraphStorage,
)
from src.core.settings import ClusteringSettings

logger = structlog.get_logger(__name__)


class CommunityNamer(Protocol):
    async def describe(self, concepts: list[dict]) -> CommunityDescription: ...


class CommunityAgent:
    def __init__(
        self,
        graph: GraphStorage,
        namer: CommunityNamer,
        config: ClusteringSettings,
    ):
        self.graph = graph
        self.namer = namer
        self.config = config

    @staticmethod
    def _id(concept_ids: list[str]) -> str:
        anchor = min(concept_ids)
        return hashlib.sha256(f"cluster:{anchor}".encode()).hexdigest()

    async def _describe(self, group: dict) -> GraphCommunity:
        concepts = group["concepts"]
        try:
            description = await self.namer.describe(concepts)
        except Exception:
            logger.exception(
                "community_description_failed",
                community_size=len(concepts),
            )
            names = [concept["name"] for concept in concepts]
            description = CommunityDescription(
                name=(" / ".join(names[:3]))[:200],
                summary=("Связанные концепции: " + ", ".join(names))[:2000],
            )
        concept_ids = [concept["id"] for concept in concepts]
        return GraphCommunity(
            id=self._id(concept_ids),
            name=description.name,
            summary=description.summary,
            concept_ids=tuple(concept_ids),
        )

    async def run(self) -> int:
        if not self.config.enabled:
            return 0
        groups = await self.graph.detect_communities(self.config.max_iterations)
        groups = [
            group
            for group in groups
            if len(group["concepts"]) >= self.config.min_community_size
        ][: self.config.max_communities]
        communities = await asyncio.gather(*(self._describe(group) for group in groups))
        await self.graph.apply_communities(list(communities))
        logger.info(
            "community_clustering_completed",
            community_count=len(communities),
            concept_count=sum(len(item.concept_ids) for item in communities),
        )
        return len(communities)
