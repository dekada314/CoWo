from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.chat_session import ChatSession
from src.infrastructure.database.mappers.chat_session_mapper import (
    ChatSessionMapper,
)
from src.infrastructure.database.models.chat_session import ChatSessionORM
from src.infrastructure.database.models.chat_message import ChatMessageORM


class ChatSessionRepository:
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

    async def delete(self, session_id: UUID, user_id: UUID | None = None) -> bool:
        stmt = delete(ChatSessionORM).where(ChatSessionORM.id == session_id)
        if user_id is not None:
            stmt = stmt.where(ChatSessionORM.user_id == user_id)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount > 0

    async def rename(self, session_id: UUID, title: str) -> None:
        await self._session.execute(
            update(ChatSessionORM)
            .where(ChatSessionORM.id == session_id)
            .values(title=title, updated_at=func.now())
        )
        await self._session.commit()

    async def messages(self, session_id: UUID) -> list[ChatMessageORM]:
        result = await self._session.execute(
            select(ChatMessageORM)
            .where(ChatMessageORM.session_id == session_id)
            .order_by(ChatMessageORM.created_at, ChatMessageORM.id)
        )
        return list(result.scalars().all())

    async def add_message(
        self,
        session_id: UUID,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> ChatMessageORM:
        message = ChatMessageORM(
            session_id=session_id,
            role=role,
            content=content,
            metadata_json=metadata,
        )
        self._session.add(message)
        await self._session.execute(
            update(ChatSessionORM)
            .where(ChatSessionORM.id == session_id)
            .values(updated_at=func.now())
        )
        await self._session.commit()
        await self._session.refresh(message)
        return message
