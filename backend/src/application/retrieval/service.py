from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

import structlog

from src.application.ingestion.contracts import IngestionError, KnowledgeCardView
from src.application.interfaces.storages.graph_storage import GraphStorage
from src.application.retrieval.contracts import (
    AnswerResponse,
    Citation,
    EvidencePath,
    KnowledgeNotFound,
    RetrievalUnavailable,
)
from src.core.settings import RetrievalSettings
from src.domain.exceptions import GraphStorageError
from src.infrastructure.database.repositories.ingestion_store import IngestionStore

logger = structlog.get_logger(__name__)


class QueryEmbeddingClient(Protocol):
    async def embed_queries(self, texts: list[str]) -> list[list[float]]: ...


class AnswerGenerator(Protocol):
    async def answer(
        self, question: str, sources: list[KnowledgeCardView]
    ) -> tuple[str, list[UUID]]: ...


@dataclass(frozen=True)
class ConceptCandidate:
    id: str
    name: str
    summary: str
    score: float
    path: tuple[str, ...]


@dataclass(frozen=True)
class CardCandidate:
    job_id: UUID
    score: float
    path: tuple[str, ...]


class RetrievalService:
    def __init__(
        self,
        graph: GraphStorage,
        store: IngestionStore,
        embeddings: QueryEmbeddingClient,
        generator: AnswerGenerator,
        config: RetrievalSettings,
    ):
        self.graph = graph
        self.store = store
        self.embeddings = embeddings
        self.generator = generator
        self.config = config

    async def _entry_concepts(self, question: str) -> dict[str, ConceptCandidate]:
        vectors = await self.embeddings.embed_queries([question])
        records = await self.graph.find_similar_concepts(
            vectors[0], self.config.entry_top_k
        )
        return {
            record["id"]: ConceptCandidate(
                id=record["id"],
                name=record["name"],
                summary=record["summary"],
                score=max(0.0, min(1.0, float(record["score"]))),
                path=(record["id"],),
            )
            for record in records
            if float(record["score"]) >= self.config.min_entry_similarity
        }

    async def _expand(
        self, entries: dict[str, ConceptCandidate]
    ) -> dict[str, ConceptCandidate]:
        candidates = dict(entries)
        frontier = list(entries.values())
        for _ in range(self.config.max_hops):
            frontier = sorted(frontier, key=lambda item: item.score, reverse=True)[
                : self.config.beam_width
            ]
            if not frontier:
                break
            frontier_by_id = {candidate.id: candidate for candidate in frontier}
            records = await self.graph.get_concept_neighbors(
                list(frontier_by_id),
                per_concept=self.config.neighbors_per_concept,
            )
            per_source: dict[str, int] = {}
            next_frontier: dict[str, ConceptCandidate] = {}
            for record in records:
                source_id = record["source_id"]
                source = frontier_by_id.get(source_id)
                if source is None:
                    continue
                used = per_source.get(source_id, 0)
                if used >= self.config.neighbors_per_concept:
                    continue
                per_source[source_id] = used + 1
                weight = max(0.0, float(record["weight"] or 0.0))
                edge_strength = 0.5 + 0.5 * weight / (weight + 1.0)
                score = source.score * self.config.path_decay * edge_strength
                known = candidates.get(record["id"])
                if known is not None and known.score >= score:
                    continue
                candidate = ConceptCandidate(
                    id=record["id"],
                    name=record["name"],
                    summary=record["summary"],
                    score=score,
                    path=(*source.path, record["id"]),
                )
                candidates[candidate.id] = candidate
                next_frontier[candidate.id] = candidate
            frontier = list(next_frontier.values())
        return candidates

    async def _cards(
        self,
        concepts: dict[str, ConceptCandidate],
        user_id: UUID,
    ) -> tuple[list[CardCandidate], dict[UUID, KnowledgeCardView]]:
        links = await self.graph.get_cards_for_concepts(
            list(concepts),
            limit=min(2000, max(100, len(concepts) * self.config.max_cards * 2)),
        )
        matches: dict[UUID, dict[str, float]] = {}
        for link in links:
            concept = concepts.get(link["concept_id"])
            if concept is None:
                continue
            try:
                job_id = UUID(link["id"])
            except ValueError:
                continue
            relevance = max(0.0, float(link["relevance"] or 0.0))
            matches.setdefault(job_id, {})[concept.id] = concept.score * relevance
        ranked: list[CardCandidate] = []
        for job_id, scores in matches.items():
            best_concept_id, best_score = max(scores.items(), key=lambda item: item[1])
            coverage = min(0.2, 0.03 * (len(scores) - 1))
            ranked.append(
                CardCandidate(
                    job_id=job_id,
                    score=min(1.0, best_score + coverage),
                    path=concepts[best_concept_id].path,
                )
            )
        ranked.sort(key=lambda item: (-item.score, str(item.job_id)))
        ranked = ranked[: self.config.max_cards]
        cards = await self.store.cards(
            [candidate.job_id for candidate in ranked],
            user_id,
        )
        return [candidate for candidate in ranked if candidate.job_id in cards], cards

    async def answer(self, question: str, user_id: UUID) -> AnswerResponse:
        logger.info("retrieval_started", question_chars=len(question))
        try:
            entries = await self._entry_concepts(question)
            if not entries:
                raise KnowledgeNotFound("knowledge_not_found")
            concepts = await self._expand(entries)
            ranked, cards = await self._cards(concepts, user_id)
            if not ranked:
                raise KnowledgeNotFound("knowledge_not_found")
            sources = [cards[candidate.job_id] for candidate in ranked]
            answer, cited_job_ids = await self.generator.answer(question, sources)
        except KnowledgeNotFound:
            logger.info("retrieval_empty", question_chars=len(question))
            raise
        except (GraphStorageError, IngestionError) as exc:
            logger.exception("retrieval_failed", error_code=str(exc))
            raise RetrievalUnavailable(str(exc)) from exc
        ranked_by_job = {candidate.job_id: candidate for candidate in ranked}
        citations = []
        paths = []
        seen: set[UUID] = set()
        for job_id in cited_job_ids:
            if job_id in seen or job_id not in cards or job_id not in ranked_by_job:
                continue
            seen.add(job_id)
            card = cards[job_id]
            candidate = ranked_by_job[job_id]
            citations.append(
                Citation(
                    card_id=card.id,
                    job_id=card.job_id,
                    document_id=card.document_id,
                    document_version_id=card.document_version_id,
                    summary=card.analysis.summary,
                    original_url=card.original_url,
                )
            )
            paths.append(
                EvidencePath(
                    job_id=job_id,
                    concepts=[concepts[item].name for item in candidate.path],
                    score=round(candidate.score, 6),
                )
            )
        if not citations:
            raise RetrievalUnavailable("responder_returned_no_valid_sources")
        logger.info(
            "retrieval_completed",
            entry_count=len(entries),
            concept_count=len(concepts),
            source_count=len(sources),
            citation_count=len(citations),
        )
        return AnswerResponse(
            answer=answer,
            citations=citations,
            evidence_paths=paths,
        )
