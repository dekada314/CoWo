from dishka import Provider, Scope, provide

from src.application.graph.service import KnowledgeGraphService
from src.application.interfaces.storages.graph_storage import GraphStorage
from src.infrastructure.database.repositories.ingestion_store import IngestionStore


class GraphProvider(Provider):
    @provide(scope=Scope.APP)
    def graph_service(
        self,
        graph: GraphStorage,
        store: IngestionStore,
    ) -> KnowledgeGraphService:
        return KnowledgeGraphService(graph, store)
