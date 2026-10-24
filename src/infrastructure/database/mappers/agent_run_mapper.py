from src.domain.entities.agent_run import AgentRun
from src.infrastructure.database.models.agent_run import AgentRunORM


class AgentRunMapper:
    @staticmethod
    def to_domain(orm: AgentRunORM) -> AgentRun:
        return AgentRun(
            id=orm.id,
            thread_id=orm.thread_id,
            graph_name=orm.graph_name,
            user_id=orm.user_id,
            status=orm.status,
            error_message=orm.error_message,
            started_at=orm.started_at,
            finished_at=orm.finished_at,
        )

    @staticmethod
    def to_orm(run: AgentRun) -> AgentRunORM:
        return AgentRunORM(
            id=run.id,
            thread_id=run.thread_id,
            graph_name=run.graph_name,
            user_id=run.user_id,
            status=run.status,
            error_message=run.error_message,
            started_at=run.started_at,
            finished_at=run.finished_at,
        )

    @staticmethod
    def update_orm(orm: AgentRunORM, run: AgentRun) -> None:
        orm.status = run.status
        orm.error_message = run.error_message
        orm.started_at = run.started_at
        orm.finished_at = run.finished_at
