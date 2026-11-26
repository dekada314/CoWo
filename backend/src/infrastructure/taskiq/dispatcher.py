import asyncio
import signal

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.core.logging import configure_logging, reset_log_context, start_log_context
from src.core.settings import get_settings
from src.infrastructure.database.repositories.ingestion_store import IngestionStore
from src.infrastructure.taskiq.broker import broker
from src.infrastructure.taskiq.tasks import ingestion

logger = structlog.get_logger(__name__)


async def dispatch_once(store: IngestionStore) -> None:
    for job_id in await store.deliveries():
        context_tokens = start_log_context(trace_id=str(job_id))
        try:
            async with asyncio.timeout(10):
                await ingestion.kiq(str(job_id))
        except Exception:
            logger.exception("ingestion_publish_failed", job_id=str(job_id))
        finally:
            reset_log_context(context_tokens)


async def main() -> None:
    settings = get_settings()
    configure_logging("dispatcher", settings.logging)
    engine = create_async_engine(
        settings.postgres.url, pool_pre_ping=True, pool_size=2, max_overflow=0
    )
    store = IngestionStore(
        async_sessionmaker(engine, expire_on_commit=False), settings.ingestion
    )
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig, stop.set)
    try:
        await broker.startup()
        while not stop.is_set():
            try:
                await dispatch_once(store)
            except Exception:
                logger.exception("ingestion_dispatcher_failed")
            try:
                await asyncio.wait_for(
                    stop.wait(), settings.ingestion.dispatch_interval_seconds
                )
            except TimeoutError:
                pass
    finally:
        try:
            await broker.shutdown()
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
