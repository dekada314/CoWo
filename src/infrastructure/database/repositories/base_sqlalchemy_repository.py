from typing import Any, Generic, TypeVar

from sqlalchemy import delete, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase
from src.application.interfaces.repositories.base_repository import (
    BaseRepository,
)
from src.domain.exceptions import RepositoryError

DTO = TypeVar("DTO")
ORM = TypeVar("ORM", bound=DeclarativeBase)
ID = TypeVar("ID")


class SQLAlchemyBaseRepository(
    BaseRepository[DTO, ID],
    Generic[DTO, ORM, ID],
):
    def __init__(self, session: AsyncSession, orm_class: type[ORM]):
        self.session = session
        self.orm_class = orm_class
        self.entity_id = inspect(orm_class).primary_key[0]

    async def create(self, entity: DTO) -> DTO:
        orm_obj = await self.mapper.from_dto_to_orm(entity)
        self.session.add(orm_obj)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise RepositoryError(f"create failed: {exc}") from exc
        await self.session.refresh(orm_obj)
        return await self.mapper.from_orm_to_dto(orm_obj)

    async def _find_by_id(self, entity_id: ID) -> ORM | None:
        stmt = select(self.orm_class).where(self.entity_id == entity_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def find_by_id(self, entity_id: ID) -> DTO | None:
        orm_entity = await self._find_by_id(entity_id=entity_id)
        if orm_entity is None:
            return None
        return await self.mapper.from_orm_to_dto(orm_entity)

    async def find_all(self, offset: int, limit: int) -> list[DTO]:
        stmt = select(self.orm_class).offset(offset).limit(limit)
        orm_entities = (await self.session.execute(stmt)).scalars().all()
        return [
            await self.mapper.from_orm_to_dto(orm_entity)
            for orm_entity in orm_entities
        ]

    async def update(self, entity_id: ID, entity: DTO) -> DTO | None:
        existed_orm = await self._find_by_id(entity_id=entity_id)
        if existed_orm is None:
            return None

        payload = self._extract_payload(entity)
        if not payload:
            return await self.mapper.from_orm_to_dto(existed_orm)

        column_keys = {column.key for column in inspect(self.orm_class).columns}
        primary_key_name = self.entity_id.key

        for key, value in payload.items():
            if key not in column_keys or key == primary_key_name:
                continue
            setattr(existed_orm, key, value)

        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise RepositoryError(f"update failed: {exc}") from exc
        await self.session.refresh(existed_orm)
        return await self.mapper.from_orm_to_dto(existed_orm)

    async def delete_by_id(self, entity_id: ID) -> bool:
        stmt = delete(self.orm_class).where(self.entity_id == entity_id)
        try:
            result = await self.session.execute(stmt)
            await self.session.commit()
        except Exception as exc:
            await self.session.rollback()
            raise RepositoryError(f"delete failed: {exc}") from exc
        return result.rowcount > 0

    async def exists(self, entity_id: ID) -> bool:
        stmt = select(self.entity_id).where(self.entity_id == entity_id).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    @staticmethod
    def _extract_payload(entity: Any) -> dict[str, Any]:
        if hasattr(entity, "model_dump"):
            return entity.model_dump(exclude_unset=True)
        return {
            key: value
            for key, value in vars(entity).items()
            if not key.startswith("_")
        }