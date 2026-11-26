import structlog

from src.application.ingestion.contracts import ClaimedJob, KnowledgeCard
from src.application.ingestion.normalizer import NormalizedKnowledge, topic_id
from src.application.interfaces.storages.graph_storage import (
    GraphProjection,
    GraphStorage,
)

logger = structlog.get_logger(__name__)


class LinkerAgent:
    def __init__(self, graph: GraphStorage):
        self.graph = graph

    async def link(
        self,
        claim: ClaimedJob,
        card: KnowledgeCard,
        knowledge: NormalizedKnowledge,
    ) -> None:
        await self.graph.project(
            GraphProjection(
                card_id=str(claim.id),
                community_id=topic_id("community", card.community.name),
                community_name=card.community.name,
                community_summary=card.community.description,
                domain=knowledge.domain,
                concepts=knowledge.concepts,
            )
        )
        logger.info(
            "linking_completed",
            concept_count=len(knowledge.concepts),
            relation_count=(
                len(knowledge.concepts) * (len(knowledge.concepts) - 1) // 2
            ),
        )
