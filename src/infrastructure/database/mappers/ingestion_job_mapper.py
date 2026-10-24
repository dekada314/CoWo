from src.domain.entities.ingestion_job import IngestionJob
from src.infrastructure.database.models.ingestion_job import IngestionJobORM


class IngestionJobMapper:
    @staticmethod
    def to_domain(orm: IngestionJobORM) -> IngestionJob:
        return IngestionJob(
            id=orm.id,
            document_version_id=orm.document_version_id,
            pipeline_version=orm.pipeline_version,
            status=orm.status,
            stage=orm.stage,
            attempt=orm.attempt,
            error_message=orm.error_message,
            error_details=orm.error_details,
            started_at=orm.started_at,
            finished_at=orm.finished_at,
        )

    @staticmethod
    def to_orm(job: IngestionJob) -> IngestionJobORM:
        return IngestionJobORM(
            id=job.id,
            document_version_id=job.document_version_id,
            pipeline_version=job.pipeline_version,
            status=job.status,
            stage=job.stage,
            attempt=job.attempt,
            error_message=job.error_message,
            error_details=job.error_details,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )

    @staticmethod
    def update_orm(orm: IngestionJobORM, job: IngestionJob) -> None:
        orm.status = job.status
        orm.stage = job.stage
        orm.attempt = job.attempt
        orm.error_message = job.error_message
        orm.error_details = job.error_details
        orm.started_at = job.started_at
        orm.finished_at = job.finished_at
