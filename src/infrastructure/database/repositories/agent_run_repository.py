from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.agent_run import AgentRun
from src.infrastructure.database.mappers.agent_run_mapper import AgentRunMapper
from src.infrastructure.database.models.agent_run import AgentRunORM


class SQLAlchemyAgentRunRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, run: AgentRun) -> AgentRun:
        orm = AgentRunMapper.to_orm(run)
        self._session.add(orm)
        await self._session.commit()
        await self._session.refresh(orm)
        return AgentRunMapper.to_domain(orm)

    async def find_by_id(self, run_id: UUID) -> AgentRun | None:
        stmt = select(AgentRunORM).where(AgentRunORM.id == run_id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        return AgentRunMapper.to_domain(orm) if orm else None

    async def find_by_thread(self, thread_id: str) -> list[AgentRun]:
        stmt = (
            select(AgentRunORM)
            .where(AgentRunORM.thread_id == thread_id)
            .order_by(AgentRunORM.created_at.asc())
        )
        orms = (await self._session.execute(stmt)).scalars().all()
        return [AgentRunMapper.to_domain(orm) for orm in orms]

    async def update(self, run: AgentRun) -> AgentRun:
        stmt = select(AgentRunORM).where(AgentRunORM.id == run.id)
        orm = (await self._session.execute(stmt)).scalar_one_or_none()
        if orm is None:
            raise ValueError(f"AgentRun {run.id} not found")
        AgentRunMapper.update_orm(orm, run)
        await self._session.commit()
        await self._session.refresh(orm)
        return AgentRunMapper.to_domain(orm)
