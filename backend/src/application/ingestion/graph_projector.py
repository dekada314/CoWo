import structlog

from src.application.ingestion.contracts import ClaimedJob, KnowledgeCard
from src.application.ingestion.linker import LinkerAgent
from src.application.ingestion.normalizer import NormalizerAgent

logger = structlog.get_logger(__name__)


class GraphProjector:
    def __init__(self, normalizer: NormalizerAgent, linker: LinkerAgent):
        self.normalizer = normalizer
        self.linker = linker

    async def project(self, claim: ClaimedJob, card: KnowledgeCard) -> None:
        logger.info("graph_projection_started", concept_count=len(card.concepts))
        knowledge = await self.normalizer.normalize(card)
        await self.linker.link(claim, card, knowledge)
        logger.info(
            "graph_projection_completed",
            concept_count=len(knowledge.concepts),
        )
