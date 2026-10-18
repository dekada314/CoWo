from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import delete, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql.schema import Column

from src.application.interfaces.base_repository import (
    BaseMapper,
    BaseRepository,
)

ID = TypeVar("ID")
DTO = TypeVar("DTO")
ORM = TypeVar("ORM", bound=DeclarativeBase)


class SQLAlchemyBaseRepository(BaseRepository[DTO, ID], Generic[DTO, ORM, ID]):
    def __init__(
        self,
        session: AsyncSession,
        orm_class: type[ORM],
        mapper: BaseMapper[DTO, ORM],
    ):
        self.session = session
        self.orm_class = orm_class
        self.mapper = mapper
        self.entity_id: Column = list(inspect(orm_class).primary_key)[0]

    async def create(self, entity: DTO) -> DTO:
        orm_obj = await self.mapper.from_dto_to_orm(entity)
        self.session.add(orm_obj)

        await self.session.commit()
        await self.session.refresh(orm_obj)
        return await self.mapper.from_orm_to_dto(orm_obj)

    async def _find_by_id(self, entity_id: UUID) -> ORM | None:
        stmt = select(self.orm_class).where(self.entity_id == entity_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def find_by_id(self, entity_id: UUID) -> DTO | None:
        orm_entity = await self._find_by_id(entity_id=entity_id)
        return (
            await self.mapper.from_orm_to_dto(orm_entity)
            if orm_entity
            else None
        )

    async def find_all(self, offset: int, limit: int) -> list[DTO]:
        stmt = select(self.orm_class).offset(offset).limit(limit)
        stmt_output = (await self.session.execute(stmt)).scalars().all()
        if stmt_output is None:
            return []

        return [
            await self.mapper.from_orm_to_dto(orm_entity)
            for orm_entity in stmt_output
        ]

    async def update(self, entity_id: UUID, entity: DTO) -> DTO | None:
        existed_orm = await self._find_by_id(entity_id=entity_id)
        if not existed_orm:
            return None

        if hasattr(entity, "model_dump"):
            payload = entity.model_dump(exclude_none=True)
        else:
            payload = {
                key: value
                for key, value in vars(entity).items()
                if value is not None
            }

        column_keys = {column.key for column in inspect(self.orm_class).columns}
        primary_key_name = self.entity_id.key

        for key, value in payload.items():
            if key not in column_keys or key == primary_key_name:
                continue

            setattr(existed_orm, key, value)

        await self.session.commit()
        await self.session.refresh(existed_orm)
        return await self.mapper.from_orm_to_dto(existed_orm)

    async def delete_by_id(self, entity_id: UUID) -> bool:
        stmt = delete(self.orm_class).where(self.entity_id == entity_id)
        stmt_output = await self.session.execute(stmt)
        await self.session.commit()
        return stmt_output.rowcount > 0
