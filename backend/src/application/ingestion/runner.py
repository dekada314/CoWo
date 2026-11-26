import asyncio
import hashlib
from uuid import UUID

import structlog

from src.application.ingestion.contracts import (
    ClaimedJob,
    IngestionError,
    JobStore,
    LeaseLost,
)
from src.application.ingestion.graph_projector import GraphProjector
from src.application.interfaces.storages.file_storage import FileStorage
from src.core.settings import IngestionSettings
from src.domain.enums import ProcessingStage
from src.pipelines.ingestion.pipeline.pipeline import IngestionPipeline

logger = structlog.get_logger(__name__)


def classify_error(exc: Exception) -> IngestionError:
    if isinstance(exc, IngestionError):
        return exc
    if isinstance(exc, ExceptionGroup):
        errors = [classify_error(error) for error in exc.exceptions]
        return next((error for error in errors if not error.retryable), errors[0])
    if isinstance(exc, TimeoutError):
        return IngestionError("job_timeout", retryable=True)
    return IngestionError("ingestion_internal_error", retryable=True)


class IngestionRunner:
    def __init__(
        self,
        store: JobStore,
        storage: FileStorage,
        pipeline: IngestionPipeline,
        projector: GraphProjector,
        config: IngestionSettings,
        max_file_bytes: int,
    ):
        self.store, self.storage = store, storage
        self.pipeline, self.projector, self.config = pipeline, projector, config
        self.max_file_bytes = max_file_bytes

    async def _heartbeat(self, claim: ClaimedJob) -> None:
        while True:
            await asyncio.sleep(self.config.heartbeat_seconds)
            if not await self.store.heartbeat(claim):
                raise LeaseLost()

    async def _execute(self, claim: ClaimedJob) -> None:
        async with asyncio.timeout(self.config.job_timeout_seconds):
            content = bytearray()
            async for part in self.storage.stream(claim.s3_file_key):
                if len(content) + len(part) > self.max_file_bytes:
                    raise IngestionError("document_file_limit_exceeded")
                content.extend(part)
            if hashlib.sha256(content).hexdigest() != claim.content_hash:
                raise IngestionError("document_integrity_check_failed")
            card = await self.pipeline.run(
                bytes(content),
                claim.filename,
                lambda stage: self.store.stage(claim, stage),
            )
            await self.store.stage(claim, ProcessingStage.EMBEDDING)
            await self.projector.project(claim, card)
            await self.store.stage(claim, ProcessingStage.GRAPH_INDEXING)
            await self.store.complete(claim, card)

    async def run(self, job_id: UUID) -> None:
        claim = await self.store.claim(job_id)
        if claim is None:
            return
        job_logger = logger.bind(
            job_id=str(job_id),
            attempt=claim.attempt,
            document_version_id=str(claim.document_version_id),
        )
        job_logger.info("ingestion_started")
        work = asyncio.create_task(self._execute(claim))
        heartbeat = asyncio.create_task(self._heartbeat(claim))
        try:
            done, _ = await asyncio.wait(
                {work, heartbeat}, return_when=asyncio.FIRST_COMPLETED
            )
            if work in done:
                await work
                job_logger.info("ingestion_completed")
            else:
                await heartbeat
        except LeaseLost:
            job_logger.warning("ingestion_lease_lost")
        except Exception as exc:
            error = classify_error(exc)
            work.cancel()
            await asyncio.gather(work, return_exceptions=True)
            job_logger.exception(
                "ingestion_failed",
                error_code=str(error),
                retryable=error.retryable,
            )
            try:
                await self.store.fail(claim, error)
            except Exception:
                job_logger.exception(
                    "ingestion_failure_persist_failed",
                    error_code=str(error),
                )
                raise
        finally:
            work.cancel()
            heartbeat.cancel()
            await asyncio.gather(work, heartbeat, return_exceptions=True)
