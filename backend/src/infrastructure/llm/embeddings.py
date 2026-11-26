import asyncio
import math
from time import perf_counter

import httpx
import structlog

from src.application.ingestion.contracts import IngestionError
from src.core.settings import LLMSettings

logger = structlog.get_logger(__name__)


class OpenAIEmbeddingClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        config: LLMSettings,
        dimension: int,
    ):
        self.client = client
        self.config = config
        self.dimension = dimension
        if (
            config.embedding_dimensions is not None
            and config.embedding_dimensions != dimension
        ):
            raise ValueError("embedding dimensions must match FalkorDB dimensions")
        self.slots = asyncio.Semaphore(config.max_concurrency)

    def _headers(self) -> dict[str, str]:
        if self.config.api_key and self.config.api_key.get_secret_value():
            return {"Authorization": f"Bearer {self.config.api_key.get_secret_value()}"}
        return {}

    async def _embed_batch(
        self, texts: list[str], input_type: str
    ) -> list[list[float]]:
        attributes = {
            "llm_model": self.config.model_embedding,
            "input_count": len(texts),
            "input_chars": sum(map(len, texts)),
            "input_type": input_type,
        }
        started = perf_counter()
        logger.info("embedding_request_started", **attributes)
        try:
            async with self.slots:
                payload = {
                    "model": self.config.model_embedding,
                    "input": [f"{input_type}: {text}" for text in texts],
                }
                if self.config.embedding_dimensions is not None:
                    payload["dimensions"] = self.config.embedding_dimensions
                response = await self.client.post(
                    self.config.base_url.rstrip("/") + "/embeddings",
                    json=payload,
                    headers=self._headers(),
                    timeout=self.config.timeout_seconds,
                )
            if response.status_code >= 400:
                retryable = (
                    response.status_code in {408, 429} or response.status_code >= 500
                )
                logger.error(
                    "embedding_request_failed",
                    **attributes,
                    status_code=response.status_code,
                    duration_ms=round((perf_counter() - started) * 1000, 2),
                    error_code=f"embedding_http_{response.status_code}",
                    retryable=retryable,
                )
                raise IngestionError(
                    f"embedding_http_{response.status_code}", retryable=retryable
                )
            raw_data = response.json()["data"]
            indexed_data = [
                (item.get("index", position), item)
                for position, item in enumerate(raw_data)
            ]
            if sorted(index for index, _ in indexed_data) != list(range(len(texts))):
                raise ValueError
            data = [item for _, item in sorted(indexed_data, key=lambda pair: pair[0])]
            vectors = [item["embedding"] for item in data]
            if len(vectors) != len(texts) or any(
                len(vector) != self.dimension
                or any(not math.isfinite(value) for value in vector)
                for vector in vectors
            ):
                raise ValueError
            logger.info(
                "embedding_request_completed",
                **attributes,
                status_code=response.status_code,
                duration_ms=round((perf_counter() - started) * 1000, 2),
                embedding_dimension=self.dimension,
            )
            return vectors
        except httpx.TransportError as exc:
            logger.exception(
                "embedding_request_failed",
                **attributes,
                duration_ms=round((perf_counter() - started) * 1000, 2),
                error_code="embedding_unavailable",
                retryable=True,
            )
            raise IngestionError("embedding_unavailable", retryable=True) from exc
        except KeyError, TypeError, ValueError:
            logger.error(
                "embedding_response_invalid",
                **attributes,
                duration_ms=round((perf_counter() - started) * 1000, 2),
                error_code="embedding_invalid_response",
                retryable=True,
            )
            raise IngestionError("embedding_invalid_response", retryable=True) from None

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for offset in range(0, len(texts), self.config.embedding_batch_size):
            vectors.extend(
                await self._embed_batch(
                    texts[offset : offset + self.config.embedding_batch_size],
                    "passage",
                )
            )
        return vectors

    async def embed_queries(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for offset in range(0, len(texts), self.config.embedding_batch_size):
            vectors.extend(
                await self._embed_batch(
                    texts[offset : offset + self.config.embedding_batch_size],
                    "query",
                )
            )
        return vectors
