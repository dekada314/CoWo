from uuid import UUID

import structlog

from src.application.interfaces.storages.file_storage import FileStorage
from src.application.interfaces.storages.graph_storage import GraphStorage
from src.infrastructure.database.repositories.ingestion_store import IngestionStore

logger = structlog.get_logger(__name__)


class DocumentDeletionUnavailable(Exception):
    pass


class DocumentDeletionService:
    def __init__(
        self,
        store: IngestionStore,
        storage: FileStorage,
        graph: GraphStorage,
    ):
        self.store = store
        self.storage = storage
        self.graph = graph

    async def delete(self, job_id: UUID, user_id: UUID) -> bool:
        target = await self.store.prepare_document_deletion(job_id, user_id)
        if target is None:
            return False
        try:
            await self.graph.remove_cards([str(value) for value in target.job_ids])
            for key in target.file_keys:
                await self.storage.delete(key)
            if not await self.store.purge_document(target.document_id, user_id):
                raise RuntimeError("prepared document disappeared before purge")
        except Exception as exc:
            logger.exception(
                "document_deletion_failed",
                document_id=str(target.document_id),
                job_id=str(job_id),
            )
            raise DocumentDeletionUnavailable("document_deletion_failed") from exc
        logger.info(
            "document_deleted",
            document_id=str(target.document_id),
            job_count=len(target.job_ids),
            file_count=len(target.file_keys),
        )
        return True
