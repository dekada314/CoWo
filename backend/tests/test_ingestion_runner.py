import asyncio
import hashlib
from unittest.mock import AsyncMock
from uuid import uuid4

from src.application.ingestion.contracts import (
    ClaimedJob,
    IngestionError,
    KnowledgeCard,
)
from src.application.ingestion.runner import IngestionRunner
from src.core.settings import IngestionSettings


class Storage:
    async def stream(self, key):
        yield b"source"


def test_duplicate_delivery_does_not_execute_pipeline():
    async def scenario():
        store, pipeline, projector = AsyncMock(), AsyncMock(), AsyncMock()
        store.claim.return_value = None
        retry_delay = await IngestionRunner(
            store,
            Storage(),
            pipeline,
            projector,
            IngestionSettings(_env_file=None),
            100,
        ).run(uuid4())
        pipeline.run.assert_not_called()
        projector.project.assert_not_called()
        store.complete.assert_not_called()
        assert retry_delay is None

    asyncio.run(scenario())


def make_claim():
    return ClaimedJob(
        id=uuid4(),
        document_version_id=uuid4(),
        token=uuid4(),
        filename="file.txt",
        s3_file_key="key",
        attempt=1,
        content_hash=hashlib.sha256(b"source").hexdigest(),
    )


def test_pipeline_failure_records_safe_retryable_error():
    async def scenario():
        store, pipeline, projector = AsyncMock(), AsyncMock(), AsyncMock()
        claim = make_claim()
        store.claim.return_value = claim
        store.fail.return_value = 30
        pipeline.run.side_effect = IngestionError("llm_unavailable", retryable=True)
        retry_delay = await IngestionRunner(
            store,
            Storage(),
            pipeline,
            projector,
            IngestionSettings(_env_file=None),
            100,
        ).run(claim.id)
        projector.project.assert_not_called()
        store.complete.assert_not_called()
        error = store.fail.call_args.args[1]
        assert error.retryable
        assert str(error) == "llm_unavailable"
        assert retry_delay == 30

    asyncio.run(scenario())


def test_lease_loss_cancels_work_without_committing_or_marking_new_owner_failed():
    async def scenario():
        cancelled = asyncio.Event()

        async def block(*args):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        store, pipeline, projector = AsyncMock(), AsyncMock(), AsyncMock()
        claim = make_claim()
        store.claim.return_value = claim
        store.heartbeat.return_value = False
        pipeline.run.side_effect = block
        config = IngestionSettings(_env_file=None, heartbeat_seconds=1)
        await IngestionRunner(store, Storage(), pipeline, projector, config, 100).run(
            claim.id
        )
        assert cancelled.is_set()
        store.fail.assert_not_called()
        store.complete.assert_not_called()

    asyncio.run(scenario())


def test_valid_card_is_committed_once():
    async def scenario():
        store, pipeline, projector = AsyncMock(), AsyncMock(), AsyncMock()
        claim = make_claim()
        store.claim.return_value = claim
        card = KnowledgeCard(
            summary="Summary",
            key_points=["Point"],
            community={"name": "Science", "description": "Scientific knowledge"},
            domain={"name": "AI", "description": "Artificial intelligence"},
            concepts=[{"name": "RAG", "description": "Retrieval"}],
        )
        pipeline.run.return_value = card
        await IngestionRunner(
            store,
            Storage(),
            pipeline,
            projector,
            IngestionSettings(_env_file=None),
            100,
        ).run(claim.id)
        projector.project.assert_awaited_once_with(claim, card)
        store.complete.assert_awaited_once_with(claim, card)
        store.fail.assert_not_called()

    asyncio.run(scenario())
