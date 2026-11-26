import asyncio
import hashlib
import math
import unicodedata
from dataclasses import dataclass, replace
from typing import Protocol

import structlog

from src.application.ingestion.contracts import KnowledgeCard
from src.application.interfaces.storages.graph_storage import (
    EmbeddedTopic,
    GraphStorage,
)
from src.core.settings import NormalizationSettings

logger = structlog.get_logger(__name__)


class EmbeddingClient(Protocol):
    async def embed_passages(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class NormalizedKnowledge:
    domain: EmbeddedTopic
    concepts: list[EmbeddedTopic]


def canonicalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split())


def topic_id(kind: str, name: str) -> str:
    value = f"{kind}:{canonicalize(name)}".encode()
    return hashlib.sha256(value).hexdigest()


def cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


class NormalizerAgent:
    def __init__(
        self,
        graph: GraphStorage,
        embeddings: EmbeddingClient,
        config: NormalizationSettings,
        max_graph_concurrency: int,
    ):
        self.graph = graph
        self.embeddings = embeddings
        self.config = config
        self.graph_slots = asyncio.Semaphore(max_graph_concurrency)

    async def _find_similar(self, vector: list[float]) -> list[dict]:
        async with self.graph_slots:
            return await self.graph.find_similar_concepts(
                vector,
                self.config.candidates,
            )

    async def normalize(self, card: KnowledgeCard) -> NormalizedKnowledge:
        topics = [card.domain, *card.concepts]
        vectors = await self.embeddings.embed_passages(
            [f"{topic.name}\n{topic.description}" for topic in topics]
        )
        searches = await asyncio.gather(
            *(self._find_similar(vector) for vector in vectors[1:])
        )
        domain = EmbeddedTopic(
            id=topic_id("domain", card.domain.name),
            name=card.domain.name,
            summary=card.domain.description,
            embedding=vectors[0],
            aliases=(card.domain.name,),
        )
        resolved: dict[str, EmbeddedTopic] = {}
        for topic, vector, matches in zip(
            card.concepts, vectors[1:], searches, strict=True
        ):
            matched = next(
                (
                    item
                    for item in matches
                    if float(item["score"]) >= self.config.similarity_threshold
                ),
                None,
            )
            local = max(
                resolved.values(),
                key=lambda item: cosine_similarity(vector, item.embedding),
                default=None,
            )
            if local is not None and (
                cosine_similarity(vector, local.embedding)
                >= self.config.similarity_threshold
            ):
                concept_id = local.id
                name = local.name
                summary = local.summary
                is_new = local.is_new
            elif matched is not None:
                concept_id = matched["id"]
                name = matched["name"]
                summary = matched["summary"]
                is_new = False
            else:
                concept_id = topic_id("concept", topic.name)
                name = topic.name
                summary = topic.description
                is_new = True
            existing = resolved.get(concept_id)
            aliases = tuple(
                dict.fromkeys([*(existing.aliases if existing else ()), topic.name])
            )
            resolved[concept_id] = replace(
                existing
                or EmbeddedTopic(
                    id=concept_id,
                    name=name,
                    summary=summary,
                    embedding=vector,
                    is_new=is_new,
                ),
                aliases=aliases,
            )
        normalized = NormalizedKnowledge(
            domain=domain, concepts=list(resolved.values())
        )
        logger.info(
            "normalization_completed",
            extracted_count=len(card.concepts),
            normalized_count=len(normalized.concepts),
            reused_count=sum(not concept.is_new for concept in normalized.concepts),
        )
        return normalized
