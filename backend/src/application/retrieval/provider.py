from collections.abc import AsyncIterable

import httpx
from dishka import Provider, Scope, provide

from src.application.interfaces.storages.graph_storage import GraphStorage
from src.application.retrieval.service import RetrievalService
from src.core.settings import Settings
from src.infrastructure.database.repositories.ingestion_store import IngestionStore
from src.infrastructure.llm.embeddings import OpenAIEmbeddingClient
from src.infrastructure.llm.responder import ResponderAgent


class RetrievalProvider(Provider):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    @provide(scope=Scope.APP)
    async def llm_http_client(self) -> AsyncIterable[httpx.AsyncClient]:
        async with httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=self.settings.llm.max_concurrency,
                max_keepalive_connections=self.settings.llm.max_concurrency,
            ),
            trust_env=False,
        ) as client:
            yield client

    @provide(scope=Scope.APP)
    def embeddings(self, client: httpx.AsyncClient) -> OpenAIEmbeddingClient:
        return OpenAIEmbeddingClient(
            client,
            self.settings.llm,
            self.settings.falkordb.embedding_dim,
        )

    @provide(scope=Scope.APP)
    def responder(self, client: httpx.AsyncClient) -> ResponderAgent:
        return ResponderAgent(client, self.settings.llm)

    @provide(scope=Scope.APP)
    def retrieval(
        self,
        graph: GraphStorage,
        store: IngestionStore,
        embeddings: OpenAIEmbeddingClient,
        responder: ResponderAgent,
    ) -> RetrievalService:
        return RetrievalService(
            graph,
            store,
            embeddings,
            responder,
            self.settings.retrieval,
        )
