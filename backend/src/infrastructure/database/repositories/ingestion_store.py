from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.application.ingestion.contracts import (
    ClaimedJob,
    DocumentDeletionTarget,
    DocumentJobView,
    IngestionError,
    JobView,
    KnowledgeCard,
    KnowledgeCardView,
    LeaseLost,
)
from src.core.settings import IngestionSettings
from src.domain.enums import JobStatus, ProcessingStage
from src.infrastructure.database.models.document import DocumentORM
from src.infrastructure.database.models.document_version import DocumentVersionORM
from src.infrastructure.database.models.ingestion_job import IngestionJobORM as Job
from src.infrastructure.database.models.knowledge_card import KnowledgeCardORM


class IngestionStore:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], config: IngestionSettings
    ):
        self.sessions = sessions
        self.config = config

    async def submit(
        self,
        filename: str,
        key: str,
        content_hash: str,
        size: int,
        user_id: UUID | None = None,
    ) -> JobView:
        document_id, version_id = uuid4(), uuid4()
        async with self.sessions.begin() as session:
            session.add(
                DocumentORM(
                    id=document_id,
                    doc_name=filename,
                    doc_type=filename.rsplit(".", 1)[-1].lower(),
                    is_deleted=False,
                    uploaded_by=user_id,
                )
            )
            await session.flush()
            session.add(
                DocumentVersionORM(
                    id=version_id,
                    document_id=document_id,
                    version_number=1,
                    s3_file_key=key,
                    content_hash=content_hash,
                    file_size_bytes=size,
                )
            )
            await session.flush()
            job = Job(
                id=uuid4(),
                document_version_id=version_id,
                pipeline_version=self.config.pipeline_version,
                status=JobStatus.QUEUED,
                stage=ProcessingStage.UPLOADED,
                attempt=0,
            )
            session.add(job)
            await session.flush()
            result = JobView.model_validate(job)
        return result

    def _eligible(self):
        return and_(
            Job.pipeline_version == self.config.pipeline_version,
            or_(
                and_(
                    Job.status == JobStatus.QUEUED,
                    Job.attempt < self.config.max_attempts,
                ),
                Job.status == JobStatus.RUNNING,
            ),
        )

    async def claim(self, job_id: UUID) -> ClaimedJob | None:
        async with self.sessions.begin() as session:
            row = (
                await session.execute(
                    select(Job, DocumentVersionORM, DocumentORM.doc_name)
                    .join(
                        DocumentVersionORM,
                        Job.document_version_id == DocumentVersionORM.id,
                    )
                    .join(DocumentORM, DocumentVersionORM.document_id == DocumentORM.id)
                    .where(
                        Job.id == job_id,
                        DocumentORM.is_deleted.is_(False),
                        self._eligible(),
                    )
                    .with_for_update(of=Job, skip_locked=True)
                )
            ).first()
            if row is None:
                return None
            job, version, filename = row
            token = uuid4()
            was_queued = job.status == JobStatus.QUEUED
            job.status = JobStatus.RUNNING
            if was_queued:
                job.attempt += 1
            job.lease_token = token
            job.lease_expires_at = func.now() + timedelta(
                seconds=self.config.lease_seconds
            )
            job.started_at = func.now()
            job.finished_at = None
            job.error_message = None
            job.error_details = None
            return ClaimedJob(
                id=job.id,
                token=token,
                document_version_id=version.id,
                filename=filename,
                s3_file_key=version.s3_file_key,
                content_hash=version.content_hash,
                attempt=job.attempt,
            )

    @staticmethod
    def _owned(claim: ClaimedJob):
        return and_(
            Job.id == claim.id,
            Job.lease_token == claim.token,
            Job.status == JobStatus.RUNNING,
            Job.lease_expires_at > func.now(),
        )

    async def heartbeat(self, claim: ClaimedJob) -> bool:
        async with self.sessions.begin() as session:
            return (
                await session.scalar(
                    update(Job)
                    .where(self._owned(claim))
                    .values(
                        lease_expires_at=func.now()
                        + timedelta(seconds=self.config.lease_seconds)
                    )
                    .returning(Job.id)
                )
            ) is not None

    async def stage(self, claim: ClaimedJob, stage: ProcessingStage) -> None:
        async with self.sessions.begin() as session:
            if (
                await session.scalar(
                    update(Job)
                    .where(self._owned(claim))
                    .values(stage=stage)
                    .returning(Job.id)
                )
                is None
            ):
                raise LeaseLost()

    async def complete(self, claim: ClaimedJob, card: KnowledgeCard) -> None:
        async with self.sessions.begin() as session:
            changed = await session.scalar(
                update(Job)
                .where(self._owned(claim))
                .values(
                    status=JobStatus.COMPLETED,
                    finished_at=func.now(),
                    lease_token=None,
                    lease_expires_at=None,
                )
                .returning(Job.id)
            )
            if changed is None:
                raise LeaseLost()
            session.add(
                KnowledgeCardORM(
                    id=uuid4(),
                    job_id=claim.id,
                    document_version_id=claim.document_version_id,
                    analysis=card.model_dump(mode="json"),
                )
            )

    async def fail(
        self, claim: ClaimedJob, error: IngestionError
    ) -> float | None:
        retry = error.retryable and claim.attempt < self.config.max_attempts
        delay = min(self.config.retry_base_seconds * 2 ** (claim.attempt - 1), 900)
        async with self.sessions.begin() as session:
            changed = await session.scalar(
                update(Job)
                .where(self._owned(claim))
                .values(
                    status=JobStatus.QUEUED if retry else JobStatus.FAILED,
                    error_message=str(error),
                    error_details={"retryable": error.retryable},
                    lease_token=None,
                    lease_expires_at=None,
                    finished_at=None if retry else func.now(),
                )
                .returning(Job.id)
            )
        return float(delay) if changed is not None and retry else None

    async def mark_publish_failed(
        self, job_id: UUID, error_code: str = "queue_publish_failed"
    ) -> None:
        async with self.sessions.begin() as session:
            await session.execute(
                update(Job)
                .where(Job.id == job_id, Job.status == JobStatus.QUEUED)
                .values(
                    status=JobStatus.FAILED,
                    error_message=error_code,
                    error_details={"retryable": True},
                    finished_at=func.now(),
                    lease_token=None,
                    lease_expires_at=None,
                )
            )

    async def get(
        self,
        job_id: UUID,
        user_id: UUID | None = None,
    ) -> JobView | None:
        async with self.sessions() as session:
            stmt = (
                select(Job)
                .join(
                    DocumentVersionORM,
                    Job.document_version_id == DocumentVersionORM.id,
                )
                .join(
                    DocumentORM,
                    DocumentVersionORM.document_id == DocumentORM.id,
                )
                .where(
                    Job.id == job_id,
                    DocumentORM.is_deleted.is_(False),
                )
            )
            if user_id is not None:
                stmt = stmt.where(DocumentORM.uploaded_by == user_id)
            job = await session.scalar(stmt)
            return JobView.model_validate(job) if job else None

    async def list_documents(
        self,
        user_id: UUID,
        offset: int = 0,
        limit: int = 200,
    ) -> list[DocumentJobView]:
        async with self.sessions() as session:
            rows = (
                await session.execute(
                    select(
                        Job,
                        DocumentVersionORM.document_id,
                        DocumentORM.doc_name,
                    )
                    .join(
                        DocumentVersionORM,
                        Job.document_version_id == DocumentVersionORM.id,
                    )
                    .join(
                        DocumentORM,
                        DocumentVersionORM.document_id == DocumentORM.id,
                    )
                    .where(
                        DocumentORM.uploaded_by == user_id,
                        DocumentORM.is_deleted.is_(False),
                    )
                    .order_by(Job.created_at.desc(), Job.id.desc())
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
            return [
                DocumentJobView(
                    **JobView.model_validate(job).model_dump(),
                    document_id=document_id,
                    filename=filename,
                    created_at=job.created_at,
                )
                for job, document_id, filename in rows
            ]

    async def referenced_file_keys(self, keys: list[str]) -> set[str]:
        if not keys:
            return set()
        async with self.sessions() as session:
            return set(
                await session.scalars(
                    select(DocumentVersionORM.s3_file_key).where(
                        DocumentVersionORM.s3_file_key.in_(keys)
                    )
                )
            )

    async def card(
        self,
        job_id: UUID,
        user_id: UUID | None = None,
    ) -> KnowledgeCardView | None:
        async with self.sessions() as session:
            stmt = (
                select(
                    KnowledgeCardORM,
                    DocumentVersionORM.document_id,
                    DocumentORM.doc_name,
                )
                .join(
                    DocumentVersionORM,
                    KnowledgeCardORM.document_version_id == DocumentVersionORM.id,
                )
                .join(
                    DocumentORM,
                    DocumentVersionORM.document_id == DocumentORM.id,
                )
                .where(KnowledgeCardORM.job_id == job_id)
                .where(DocumentORM.is_deleted.is_(False))
            )
            if user_id is not None:
                stmt = stmt.where(DocumentORM.uploaded_by == user_id)
            row = (await session.execute(stmt)).first()
            if row is None:
                return None
            card, document_id, filename = row
            return KnowledgeCardView(
                id=card.id,
                job_id=card.job_id,
                document_id=document_id,
                document_version_id=card.document_version_id,
                filename=filename,
                original_url=f"/api/v1/ingestion/jobs/{job_id}/original",
                analysis=KnowledgeCard.model_validate(card.analysis),
            )

    async def cards(
        self,
        job_ids: list[UUID],
        user_id: UUID | None = None,
    ) -> dict[UUID, KnowledgeCardView]:
        if not job_ids:
            return {}
        async with self.sessions() as session:
            stmt = (
                select(
                    KnowledgeCardORM,
                    DocumentVersionORM.document_id,
                    DocumentORM.doc_name,
                )
                .join(
                    DocumentVersionORM,
                    KnowledgeCardORM.document_version_id == DocumentVersionORM.id,
                )
                .join(
                    DocumentORM,
                    DocumentVersionORM.document_id == DocumentORM.id,
                )
                .where(KnowledgeCardORM.job_id.in_(job_ids))
                .where(DocumentORM.is_deleted.is_(False))
            )
            if user_id is not None:
                stmt = stmt.where(DocumentORM.uploaded_by == user_id)
            rows = (await session.execute(stmt)).all()
            return {
                card.job_id: KnowledgeCardView(
                    id=card.id,
                    job_id=card.job_id,
                    document_id=document_id,
                    document_version_id=card.document_version_id,
                    filename=filename,
                    original_url=(f"/api/v1/ingestion/jobs/{card.job_id}/original"),
                    analysis=KnowledgeCard.model_validate(card.analysis),
                )
                for card, document_id, filename in rows
            }

    async def original(
        self,
        job_id: UUID,
        user_id: UUID | None = None,
    ) -> tuple[str, str] | None:
        async with self.sessions() as session:
            stmt = (
                select(DocumentVersionORM.s3_file_key, DocumentORM.doc_name)
                .join(Job, Job.document_version_id == DocumentVersionORM.id)
                .join(DocumentORM, DocumentORM.id == DocumentVersionORM.document_id)
                .where(
                    Job.id == job_id,
                    DocumentORM.is_deleted.is_(False),
                )
            )
            if user_id is not None:
                stmt = stmt.where(DocumentORM.uploaded_by == user_id)
            row = (await session.execute(stmt)).first()
            return (row[0], row[1]) if row else None

    async def retry(
        self,
        job_id: UUID,
        user_id: UUID | None = None,
    ) -> JobView | None:
        async with self.sessions.begin() as session:
            stmt = (
                select(Job)
                .join(
                    DocumentVersionORM,
                    Job.document_version_id == DocumentVersionORM.id,
                )
                .join(
                    DocumentORM,
                    DocumentVersionORM.document_id == DocumentORM.id,
                )
                .where(
                    Job.id == job_id,
                    DocumentORM.is_deleted.is_(False),
                )
            )
            if user_id is not None:
                stmt = stmt.where(DocumentORM.uploaded_by == user_id)
            job = await session.scalar(stmt.with_for_update(of=Job))
            if job is None:
                return None
            if job.status != JobStatus.FAILED:
                raise IngestionError("only_failed_jobs_can_be_retried")
            job.status = JobStatus.QUEUED
            job.attempt = 0
            job.stage = ProcessingStage.UPLOADED
            job.error_message = None
            job.error_details = None
            job.finished_at = None
            job.started_at = None
            job.lease_token = None
            job.lease_expires_at = None
            await session.flush()
            return JobView.model_validate(job)

    async def prepare_document_deletion(
        self,
        job_id: UUID,
        user_id: UUID,
    ) -> DocumentDeletionTarget | None:
        async with self.sessions.begin() as session:
            document = await session.scalar(
                select(DocumentORM)
                .join(
                    DocumentVersionORM,
                    DocumentVersionORM.document_id == DocumentORM.id,
                )
                .join(Job, Job.document_version_id == DocumentVersionORM.id)
                .where(Job.id == job_id, DocumentORM.uploaded_by == user_id)
                .with_for_update(of=DocumentORM)
            )
            if document is None:
                return None
            jobs = (
                await session.scalars(
                    select(Job)
                    .join(
                        DocumentVersionORM,
                        Job.document_version_id == DocumentVersionORM.id,
                    )
                    .where(DocumentVersionORM.document_id == document.id)
                    .with_for_update(of=Job)
                )
            ).all()
            if any(job.status == JobStatus.RUNNING for job in jobs):
                raise IngestionError("document_processing_in_progress")
            file_keys = tuple(
                await session.scalars(
                    select(DocumentVersionORM.s3_file_key).where(
                        DocumentVersionORM.document_id == document.id
                    )
                )
            )
            for job in jobs:
                job.status = JobStatus.CANCELLED
                job.finished_at = func.now()
                job.lease_token = None
                job.lease_expires_at = None
            return DocumentDeletionTarget(
                document_id=document.id,
                job_ids=tuple(job.id for job in jobs),
                file_keys=file_keys,
            )

    async def purge_document(self, document_id: UUID, user_id: UUID) -> bool:
        async with self.sessions.begin() as session:
            deleted_id = await session.scalar(
                delete(DocumentORM)
                .where(
                    DocumentORM.id == document_id,
                    DocumentORM.uploaded_by == user_id,
                )
                .returning(DocumentORM.id)
            )
            return deleted_id is not None
