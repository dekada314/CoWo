from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from src.domain.enums import JobStatus, ProcessingStage

ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
Summary = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]


class Topic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: ShortText
    description: ShortText


class KnowledgeCard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: Summary
    key_points: list[ShortText] = Field(min_length=1, max_length=12)
    community: Topic
    domain: Topic
    concepts: list[Topic] = Field(min_length=1, max_length=8)


class JobView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_version_id: UUID
    status: JobStatus
    stage: ProcessingStage | None
    attempt: int
    pipeline_version: str
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None


class DocumentJobView(JobView):
    document_id: UUID
    filename: str
    created_at: datetime


class KnowledgeCardView(BaseModel):
    id: UUID
    job_id: UUID
    document_id: UUID
    document_version_id: UUID
    filename: str
    original_url: str
    analysis: KnowledgeCard


class ClaimedJob(BaseModel):
    id: UUID
    document_version_id: UUID
    token: UUID
    filename: str
    s3_file_key: str
    content_hash: str
    attempt: int


@dataclass(frozen=True)
class DocumentDeletionTarget:
    document_id: UUID
    job_ids: tuple[UUID, ...]
    file_keys: tuple[str, ...]


class IngestionError(Exception):
    def __init__(self, code: str, *, retryable: bool = False):
        super().__init__(code)
        self.retryable = retryable


class LeaseLost(IngestionError):
    def __init__(self):
        super().__init__("job_lease_lost")


class JobStore(Protocol):
    async def claim(self, job_id: UUID) -> ClaimedJob | None: ...
    async def heartbeat(self, claim: ClaimedJob) -> bool: ...
    async def stage(self, claim: ClaimedJob, stage: ProcessingStage) -> None: ...
    async def complete(self, claim: ClaimedJob, card: KnowledgeCard) -> None: ...
    async def fail(self, claim: ClaimedJob, error: IngestionError) -> float | None: ...
