from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.repositories.agent_run_repository import (
    AgentRunRepository,
)
from src.infrastructure.database.repositories.chat_session_repository import (
    ChatSessionRepository,
)
from src.infrastructure.database.repositories.document_repository import (
    DocumentRepository,
)
from src.infrastructure.database.repositories.ingestion_job_repository import (
    IngestionJobRepository,
)
from src.infrastructure.database.repositories.user_repository import (
    UserRepository,
)


class RepositoryProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def user_repository(self, session: AsyncSession) -> UserRepository:
        return UserRepository(session)

    @provide(scope=Scope.REQUEST)
    def document_repository(self, session: AsyncSession) -> DocumentRepository:
        return DocumentRepository(session)

    @provide(scope=Scope.REQUEST)
    def ingestion_job_repository(
        self, session: AsyncSession
    ) -> IngestionJobRepository:
        return IngestionJobRepository(session)

    @provide(scope=Scope.REQUEST)
    def chat_session_repository(
        self, session: AsyncSession
    ) -> ChatSessionRepository:
        return ChatSessionRepository(session)

    @provide(scope=Scope.REQUEST)
    def agent_run_repository(self, session: AsyncSession) -> AgentRunRepository:
        return AgentRunRepository(session)
