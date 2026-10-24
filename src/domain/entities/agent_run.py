from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from src.domain.enums import AgentRunStatus

tz = timezone(offset=timedelta(hours=3))


@dataclass
class AgentRun:
    id: UUID
    thread_id: str
    graph_name: str
    user_id: UUID | None = None
    status: AgentRunStatus = AgentRunStatus.QUEUED
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def start(self) -> None:
        self.status = AgentRunStatus.RUNNING
        self.started_at = datetime.now(tz=tz)

    def complete(self) -> None:
        self.status = AgentRunStatus.COMPLETED
        self.finished_at = datetime.now(tz=tz)

    def fail(self, message: str) -> None:
        self.status = AgentRunStatus.FAILED
        self.error_message = message
        self.finished_at = datetime.now(tz=tz)

    def interrupt(self) -> None:
        self.status = AgentRunStatus.INTERRUPTED
        self.finished_at = datetime.now(tz=tz)
