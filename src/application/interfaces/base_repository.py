from abc import ABC, abstractmethod
from typing import Generic, TypeVar

DTO = TypeVar("DTO")
ORM = TypeVar("ORM")
ID = TypeVar("ID")


class BaseRepository(Generic[DTO, ID], ABC):
    @abstractmethod
    async def create(self, entity: DTO) -> DTO: ...
    @abstractmethod
    async def update(self, entity_id: ID, entity: DTO) -> DTO | None: ...
    @abstractmethod
    async def delete_by_id(self, entity_id: ID) -> bool: ...
    @abstractmethod
    async def find_by_id(self, entity_id: ID) -> DTO | None: ...


# class BaseMapper(Generic[DTO, ORM], ABC):
#     @abstractmethod
#     async def from_orm_to_dto(self, orm: ORM) -> DTO | None: ...
#     @abstractmethod
#     async def from_dto_to_orm(self, dto: DTO) -> ORM | None: ...
