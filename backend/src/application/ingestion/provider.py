from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.application.ingestion.deletion import DocumentDeletionService
from src.application.interfaces.storages.file_storage import FileStorage
from src.application.interfaces.storages.graph_storage import GraphStorage
from src.core.settings import Settings
from src.infrastructure.database.repositories.ingestion_store import IngestionStore


class IngestionProvider(Provider):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    @provide(scope=Scope.APP)
    def store(self, sessions: async_sessionmaker[AsyncSession]) -> IngestionStore:
        return IngestionStore(sessions, self.settings.ingestion)

    @provide(scope=Scope.APP)
    def deletion_service(
        self,
        store: IngestionStore,
        storage: FileStorage,
        graph: GraphStorage,
    ) -> DocumentDeletionService:
        return DocumentDeletionService(store, storage, graph)
