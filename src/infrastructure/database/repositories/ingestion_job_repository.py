from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.ingestion_job import IngestionJob
from src.domain.enums import JobStatus
from src.infrastructure.database.mappers.ingestion_job_mapper import (
    IngestionJobMapper,
)
from src.infrastructure.database.models.ingestion_job import IngestionJobORM


class SQLAlchemyIngestionJobRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, job: IngestionJob) -> IngestionJob:
        orm = IngestionJobMapper.to_orm(job)
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return IngestionJobMapper.to_domain(orm)

    async def find_by_id(self, job_id: UUID) -> IngestionJob | None:
        stmt = select(IngestionJobORM).where(IngestionJobORM.id == job_id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        return IngestionJobMapper.to_domain(orm) if orm else None

    async def find_by_version(
        self, document_version_id: UUID
    ) -> list[IngestionJob]:
        stmt = (
            select(IngestionJobORM)
            .where(IngestionJobORM.document_version_id == document_version_id)
            .order_by(IngestionJobORM.created_at.desc())
        )
        orms = (await self._session.execute(stmt)).scalars().all()
        return [IngestionJobMapper.to_domain(orm) for orm in orms]

    async def find_by_status(
        self, status: JobStatus, limit: int
    ) -> list[IngestionJob]:
        stmt = (
            select(IngestionJobORM)
            .where(IngestionJobORM.status == status)
            .order_by(IngestionJobORM.created_at.asc())
            .limit(limit)
        )
        orms = (await self._session.execute(stmt)).scalars().all()
        return [IngestionJobMapper.to_domain(orm) for orm in orms]

    async def update(self, job: IngestionJob) -> IngestionJob:
        stmt = select(IngestionJobORM).where(IngestionJobORM.id == job.id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            raise ValueError(f"IngestionJob {job.id} not found")
        IngestionJobMapper.update_orm(orm, job)
        await self._session.commit()
        await self._session.refresh(orm)
        return IngestionJobMapper.to_domain(orm)
