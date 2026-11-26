from datetime import UTC, datetime, timedelta
from typing import Protocol

import structlog

from src.application.interfaces.storages.file_storage import FileStorage
from src.core.settings import IngestionSettings

logger = structlog.get_logger(__name__)


class FileReferenceStore(Protocol):
    async def referenced_file_keys(self, keys: list[str]) -> set[str]: ...


class S3Cleanup:
    def __init__(
        self,
        store: FileReferenceStore,
        storage: FileStorage,
        config: IngestionSettings,
    ):
        self.store = store
        self.storage = storage
        self.config = config

    async def run(self) -> int:
        if not self.config.cleanup_enabled:
            return 0
        cutoff = datetime.now(UTC) - timedelta(hours=self.config.cleanup_grace_hours)
        files = await self.storage.list_files(self.config.cleanup_prefix)
        candidates = sorted(
            (
                item
                for item in files
                if item.last_modified is not None and item.last_modified < cutoff
            ),
            key=lambda item: item.last_modified,
        )[: self.config.cleanup_batch_size]
        referenced = await self.store.referenced_file_keys(
            [item.key for item in candidates]
        )
        deleted = 0
        for item in candidates:
            if item.key in referenced:
                continue
            try:
                await self.storage.delete(item.key)
                deleted += 1
            except Exception:
                logger.exception("s3_orphan_delete_failed", object_key=item.key)
        if deleted:
            logger.info(
                "s3_orphans_deleted",
                deleted_count=deleted,
                candidate_count=len(candidates),
                grace_hours=self.config.cleanup_grace_hours,
            )
        return deleted
