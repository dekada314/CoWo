from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.chat_session import ChatSession
from src.infrastructure.database.mappers.chat_session_mapper import (
    ChatSessionMapper,
)
from src.infrastructure.database.models.chat_session import ChatSessionORM


class SQLAlchemyChatSessionRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, session: ChatSession) -> ChatSession:
        orm = ChatSessionMapper.to_orm(session)
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return ChatSessionMapper.to_domain(orm)

    async def find_by_id(self, session_id: UUID) -> ChatSession | None:
        stmt = select(ChatSessionORM).where(ChatSessionORM.id == session_id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        return ChatSessionMapper.to_domain(orm) if orm else None

    async def find_by_user(self, user_id: UUID) -> list[ChatSession]:
        stmt = (
            select(ChatSessionORM)
            .where(ChatSessionORM.user_id == user_id)
            .order_by(ChatSessionORM.updated_at.desc())
        )
        orms = (await self._session.execute(stmt)).scalars().all()
        return [ChatSessionMapper.to_domain(orm) for orm in orms]

    async def delete(self, session_id: UUID) -> bool:
        stmt = delete(ChatSessionORM).where(ChatSessionORM.id == session_id)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount > 0
