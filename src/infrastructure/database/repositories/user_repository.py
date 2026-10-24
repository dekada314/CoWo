from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.user import User
from src.infrastructure.database.mappers.user_mapper import UserMapper
from src.infrastructure.database.models.user import UserORM


class SQLAlchemyUserRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, user: User, password_hash: str) -> User:
        orm = UserMapper.to_orm(user, password_hash)
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return UserMapper.to_domain(orm)

    async def find_by_id(self, user_id: UUID) -> User | None:
        stmt = select(UserORM).where(UserORM.id == user_id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        return UserMapper.to_domain(orm) if orm else None

    async def find_by_email(self, email: str) -> tuple[User, str] | None:
        stmt = select(UserORM).where(UserORM.email == email)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            return None
        return UserMapper.to_domain(orm), orm.password_hash

    async def exists_by_email(self, email: str) -> bool:
        stmt = select(UserORM.id).where(UserORM.email == email).limit(1)
        return (
            await self._session.execute(stmt)
        ).scalar_one_or_none() is not None
