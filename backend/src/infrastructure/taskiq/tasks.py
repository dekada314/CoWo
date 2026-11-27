import asyncio
from uuid import UUID, uuid4

from taskiq import Context, TaskiqDepends, TaskiqEvents, TaskiqState

from src.core.logging import configure_logging, reset_log_context, start_log_context
from src.core.settings import get_settings
from src.infrastructure.taskiq.broker import broker
from src.infrastructure.taskiq.runtime import worker_runtime


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState) -> None:
    settings = get_settings()
    configure_logging("worker", settings.logging)
    state.runtime_manager = worker_runtime(settings)
    state.services = await state.runtime_manager.__aenter__()


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def shutdown(state: TaskiqState) -> None:
    await state.runtime_manager.__aexit__(None, None, None)


@broker.task(task_name="cowo.ingestion.analyst.v1", ack_type="when_executed")
async def ingestion(job_id: str, context: Context = TaskiqDepends()) -> None:
    parsed_job_id = UUID(job_id)
    context_tokens = start_log_context(trace_id=str(parsed_job_id))
    try:
        while True:
            retry_delay = await context.state.services.runner.run(parsed_job_id)
            if retry_delay is None:
                break
            await asyncio.sleep(retry_delay)
    finally:
        reset_log_context(context_tokens)


@broker.task(
    task_name="cowo.maintenance.s3-cleanup.v1",
    schedule=[{"cron": "0 * * * *", "schedule_id": "s3-cleanup-hourly"}],
    ack_type="when_executed",
)
async def cleanup_s3(context: Context = TaskiqDepends()) -> None:
    context_tokens = start_log_context(trace_id=f"cleanup-{uuid4().hex}")
    try:
        await context.state.services.s3_cleanup.run()
    finally:
        reset_log_context(context_tokens)


@broker.task(
    task_name="cowo.maintenance.community-clustering.v1",
    schedule=[
        {
            "cron": get_settings().clustering.cron,
            "schedule_id": "community-clustering",
        }
    ],
    ack_type="when_executed",
)
async def cluster_communities(context: Context = TaskiqDepends()) -> None:
    context_tokens = start_log_context(trace_id=f"clustering-{uuid4().hex}")
    try:
        await context.state.services.community_agent.run()
    finally:
        reset_log_context(context_tokens)
