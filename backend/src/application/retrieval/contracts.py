from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Question = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
]
Answer = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=12000)
]


class AnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: Question


class GeneratedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: Answer
    cited_job_ids: list[UUID] = Field(min_length=1, max_length=50)


class Citation(BaseModel):
    card_id: UUID
    job_id: UUID
    document_id: UUID
    document_version_id: UUID
    summary: str
    original_url: str


class EvidencePath(BaseModel):
    job_id: UUID
    concepts: list[str]
    score: float


class AnswerResponse(BaseModel):
    answer: str
    citations: list[Citation]
    evidence_paths: list[EvidencePath]


class KnowledgeNotFound(Exception):
    pass


class RetrievalUnavailable(Exception):
    pass
