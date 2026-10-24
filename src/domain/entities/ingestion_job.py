from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from src.domain.enums import JobStatus, ProcessingStage

tz = timezone(offset=timedelta(hours=3))


@dataclass
class IngestionJob:
    id: UUID
    document_version_id: UUID
    pipeline_version: str
    status: JobStatus = JobStatus.QUEUED
    stage: ProcessingStage | None = None
    attempt: int = 0
    error_message: str | None = None
    error_details: dict | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def start(self) -> None:
        if self.status != JobStatus.QUEUED:
            raise ValueError(f"Cannot start job in status {self.status}")
        self.status = JobStatus.RUNNING
        self.started_at = datetime.now(tz=tz)
        self.attempt += 1

    def complete(self) -> None:
        if self.status != JobStatus.RUNNING:
            raise ValueError(f"Cannot complete job in status {self.status}")
        self.status = JobStatus.COMPLETED
        self.finished_at = datetime.now(tz=tz)

    def fail(self, message: str, details: dict | None = None) -> None:
        self.status = JobStatus.FAILED
        self.error_message = message
        self.error_details = details
        self.finished_at = datetime.now(tz=tz)

    def cancel(self) -> None:
        if self.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            raise ValueError(f"Cannot cancel job in status {self.status}")
        self.status = JobStatus.CANCELLED
        self.finished_at = datetime.now(tz=tz)

    def advance_stage(self, stage: ProcessingStage) -> None:
        if self.status != JobStatus.RUNNING:
            raise ValueError("Cannot advance stage for non-running job")
        self.stage = stage

    def can_retry(self, max_attempts: int = 3) -> bool:
        return self.status == JobStatus.FAILED and self.attempt < max_attempts
