"""Real PostgreSQL transactions and migrations, isolated in a random test schema."""

import asyncio
import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.application.ingestion.contracts import IngestionError, KnowledgeCard, LeaseLost
from src.core.settings import IngestionSettings, get_settings
from src.domain.enums import JobStatus
from src.infrastructure.database.models.knowledge_card import KnowledgeCardORM
from src.infrastructure.database.models.user import UserORM
from src.infrastructure.database.repositories.ingestion_store import IngestionStore

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (
            os.getenv("COWO_TEST_DATABASE_URL") or os.getenv("COWO_TEST_POSTGRES_PORT")
        ),
        reason="configure an isolated PostgreSQL integration database",
    ),
]


def test_migrations_delivery_claims_recovery_and_atomic_card():
    async def scenario():
        database_url = os.getenv("COWO_TEST_DATABASE_URL")
        if database_url is None:
            pg = get_settings().postgres.model_copy(
                update={
                    "host": "127.0.0.1",
                    "port": int(os.environ["COWO_TEST_POSTGRES_PORT"]),
                }
            )
            database_url = pg.url
        schema = "cowo_test_" + uuid4().hex
        admin = create_async_engine(database_url)
        engine = create_async_engine(
            database_url,
            connect_args={"server_settings": {"search_path": schema}},
            pool_size=5,
        )
        try:
            async with admin.begin() as conn:
                await conn.execute(text(f'CREATE SCHEMA "{schema}"'))

            def migrate(conn):
                config = Config("alembic.ini")
                config.attributes["connection"] = conn
                command.upgrade(config, "head")

            async with engine.begin() as conn:
                await conn.run_sync(migrate)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            settings = IngestionSettings(_env_file=None, max_attempts=2)
            store = IngestionStore(sessions, settings)
            user_id, other_user_id = uuid4(), uuid4()
            async with sessions.begin() as session:
                session.add_all(
                    [
                        UserORM(
                            id=user_id,
                            email=f"{user_id}@example.com",
                            password_hash="hash",
                        ),
                        UserORM(
                            id=other_user_id,
                            email=f"{other_user_id}@example.com",
                            password_hash="hash",
                        ),
                    ]
                )
            job = await store.submit("test.txt", "key", "a" * 64, 6, user_id)
            assert await store.get(job.id, user_id) is not None
            assert await store.get(job.id, other_user_id) is None
            documents = await store.list_documents(user_id)
            assert len(documents) == 1
            assert documents[0].id == job.id
            assert documents[0].filename == "test.txt"
            assert await store.list_documents(other_user_id) == []
            claims = await asyncio.gather(store.claim(job.id), store.claim(job.id))
            assert sum(claim is not None for claim in claims) == 1
            stale = next(claim for claim in claims if claim)
            assert await store.heartbeat(stale)
            # A redelivered RabbitMQ message fences the previous lease immediately.
            recovered = await store.claim(job.id)
            assert recovered and recovered.attempt == 1
            assert recovered.token != stale.token
            assert not await store.heartbeat(stale)

            card = KnowledgeCard(
                summary="Summary",
                key_points=["Point"],
                community={"name": "Science", "description": "Knowledge"},
                domain={"name": "AI", "description": "Artificial intelligence"},
                concepts=[{"name": "RAG", "description": "Retrieval"}],
            )
            with pytest.raises(LeaseLost):
                await store.complete(stale, card)
            await store.fail(stale, IngestionError("stale_failure"))
            assert (await store.get(job.id)).status == JobStatus.RUNNING
            await store.complete(recovered, card)
            assert (await store.get(job.id)).status == JobStatus.COMPLETED
            assert await store.claim(job.id) is None
            assert (await store.card(job.id, user_id)).analysis == card
            assert await store.card(job.id, other_user_id) is None
            assert await store.original(job.id, user_id) == ("key", "test.txt")
            assert await store.original(job.id, other_user_id) is None
            async with sessions() as session:
                assert (
                    await session.scalar(
                        select(func.count()).select_from(KnowledgeCardORM)
                    )
                    == 1
                )

            assert await store.prepare_document_deletion(job.id, other_user_id) is None
            deletion = await store.prepare_document_deletion(job.id, user_id)
            assert deletion is not None
            assert deletion.job_ids == (job.id,)
            assert deletion.file_keys == ("key",)
            assert (await store.get(job.id, user_id)).status == JobStatus.CANCELLED
            assert await store.card(job.id, user_id) is not None
            assert await store.original(job.id, user_id) == ("key", "test.txt")
            assert await store.purge_document(deletion.document_id, user_id)

            retry_job = await store.submit("retry.txt", "key2", "b" * 64, 6, user_id)
            first = await store.claim(retry_job.id)
            first_delay = await store.fail(
                first, IngestionError("llm_unavailable", retryable=True)
            )
            assert first_delay == settings.retry_base_seconds
            assert (await store.get(retry_job.id)).status == JobStatus.QUEUED
            second = await store.claim(retry_job.id)
            second_delay = await store.fail(
                second, IngestionError("llm_unavailable", retryable=True)
            )
            assert second_delay is None
            assert (await store.get(retry_job.id)).status == JobStatus.FAILED
            assert await store.retry(retry_job.id, other_user_id) is None
            assert (await store.retry(retry_job.id, user_id)).attempt == 0
            with pytest.raises(IngestionError):
                await store.retry(retry_job.id)

            publish_failed = await store.submit(
                "queue.txt", "key3", "c" * 64, 6, user_id
            )
            await store.mark_publish_failed(publish_failed.id)
            failed_view = await store.get(publish_failed.id)
            assert failed_view.status == JobStatus.FAILED
            assert failed_view.error_message == "queue_publish_failed"
        finally:
            await engine.dispose()
            async with admin.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            await admin.dispose()

    asyncio.run(scenario())
