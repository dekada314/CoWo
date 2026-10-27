from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.entities.document import Document, DocumentVersion
from src.infrastructure.database.mappers.document_mapper import DocumentMapper
from src.infrastructure.database.models.document import DocumentORM
from src.infrastructure.database.models.document_version import (
    DocumentVersionORM,
)


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, document: Document) -> Document:
        orm = DocumentMapper.to_orm(document)
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return DocumentMapper.to_domain(orm)

    async def find_by_id(self, document_id: UUID) -> Document | None:
        stmt = (
            select(DocumentORM)
            .where(DocumentORM.id == document_id)
            .options(selectinload(DocumentORM.versions))
        )
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        return DocumentMapper.to_domain(orm) if orm else None

    async def find_by_user(
        self, user_id: UUID, offset: int, limit: int
    ) -> list[Document]:
        stmt = (
            select(DocumentORM)
            .where(DocumentORM.uploaded_by == user_id)
            .where(DocumentORM.is_deleted.is_(False))
            .offset(offset)
            .limit(limit)
            .options(selectinload(DocumentORM.versions))
        )
        orms = (await self._session.execute(stmt)).scalars().all()
        return [DocumentMapper.to_domain(orm) for orm in orms]

    async def soft_delete(self, document_id: UUID) -> bool:
        stmt = (
            update(DocumentORM)
            .where(DocumentORM.id == document_id)
            .values(is_deleted=True)
        )
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        await self._session.commit()
        return True

    async def add_version(self, version: DocumentVersion) -> DocumentVersion:
        orm = DocumentMapper.version_to_orm(version)
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return DocumentMapper.version_to_domain(orm)

    async def get_versions(self, document_id: UUID) -> list[DocumentVersion]:
        stmt = (
            select(DocumentVersionORM)
            .where(DocumentVersionORM.document_id == document_id)
            .order_by(DocumentVersionORM.version_number.asc())
        )
        orms = (await self._session.execute(stmt)).scalars().all()
        return [DocumentMapper.version_to_domain(orm) for orm in orms]
