from uuid import UUID

import structlog

from src.application.graph.contracts import (
    GraphCommunityView,
    GraphConceptNotFound,
    GraphConceptView,
    GraphDomainView,
    GraphEdgeView,
    GraphUnavailable,
    KnowledgeGraphView,
)
from src.application.ingestion.contracts import KnowledgeCardView
from src.application.interfaces.storages.graph_storage import GraphStorage
from src.domain.exceptions import GraphStorageError
from src.infrastructure.database.repositories.ingestion_store import IngestionStore

logger = structlog.get_logger(__name__)


class KnowledgeGraphService:
    def __init__(self, graph: GraphStorage, store: IngestionStore):
        self.graph = graph
        self.store = store

    @staticmethod
    def _community(domain: dict) -> dict:
        communities = domain["communities"]
        if not communities:
            return {
                "id": "ungrouped",
                "name": "Без сообщества",
                "summary": "Домены вне автоматически определённых сообществ",
            }
        return max(
            communities,
            key=lambda item: (
                item["source"] == "clusterizer" and item["active"] is not False,
                item["source"] == "analyst",
            ),
        )

    async def overview(self, user_id: UUID) -> KnowledgeGraphView:
        try:
            raw = await self.graph.get_visual_graph()
            job_ids = {
                UUID(card_id)
                for concept in raw["concepts"]
                for card_id in concept["card_ids"]
                if self._is_uuid(card_id)
            }
            cards = await self.store.cards(list(job_ids), user_id)
        except GraphStorageError as exc:
            logger.exception("graph_overview_failed", user_id=str(user_id))
            raise GraphUnavailable("graph_unavailable") from exc

        visible_concepts: list[GraphConceptView] = []
        for concept in raw["concepts"]:
            visible_cards = {
                UUID(card_id)
                for card_id in concept["card_ids"]
                if self._is_uuid(card_id) and UUID(card_id) in cards
            }
            if not visible_cards or not concept["domains"]:
                continue
            primary_domain = max(
                concept["domains"],
                key=lambda item: (float(item["weight"]), item["id"]),
            )
            visible_concepts.append(
                GraphConceptView(
                    id=concept["id"],
                    name=concept["name"],
                    summary=concept["summary"],
                    domain_id=primary_domain["id"],
                    card_count=len(visible_cards),
                )
            )

        concept_ids = {concept.id for concept in visible_concepts}
        domain_ids = {concept.domain_id for concept in visible_concepts}
        communities: dict[str, GraphCommunityView] = {}
        domains = []
        for domain in raw["domains"]:
            if domain["id"] not in domain_ids:
                continue
            community = self._community(domain)
            communities.setdefault(
                community["id"],
                GraphCommunityView(
                    id=community["id"],
                    name=community["name"],
                    summary=community["summary"],
                ),
            )
            domains.append(
                GraphDomainView(
                    id=domain["id"],
                    name=domain["name"],
                    summary=domain["summary"],
                    community_id=community["id"],
                )
            )
        edges = [
            GraphEdgeView(
                source_id=edge["source_id"],
                target_id=edge["target_id"],
                weight=max(0.0, float(edge["weight"] or 0)),
            )
            for edge in raw["edges"]
            if edge["source_id"] in concept_ids and edge["target_id"] in concept_ids
        ]
        logger.info(
            "graph_overview_loaded",
            user_id=str(user_id),
            domain_count=len(domains),
            concept_count=len(visible_concepts),
            edge_count=len(edges),
        )
        return KnowledgeGraphView(
            communities=list(communities.values()),
            domains=domains,
            concepts=visible_concepts,
            edges=edges,
        )

    async def concept_cards(
        self,
        concept_id: str,
        user_id: UUID,
    ) -> list[KnowledgeCardView]:
        try:
            raw_ids = await self.graph.get_card_ids_for_concept(concept_id)
            if raw_ids is None:
                raise GraphConceptNotFound("concept_not_found")
            job_ids = [UUID(value) for value in raw_ids if self._is_uuid(value)]
            cards = await self.store.cards(job_ids, user_id)
        except GraphConceptNotFound:
            raise
        except GraphStorageError as exc:
            logger.exception(
                "graph_concept_cards_failed",
                concept_id=concept_id,
                user_id=str(user_id),
            )
            raise GraphUnavailable("graph_unavailable") from exc
        return [cards[job_id] for job_id in job_ids if job_id in cards]

    @staticmethod
    def _is_uuid(value: str) -> bool:
        try:
            UUID(value)
        except (TypeError, ValueError):
            return False
        return True
