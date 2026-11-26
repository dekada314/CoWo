import asyncio
from unittest.mock import AsyncMock, MagicMock, call
from uuid import uuid4

import pytest

from src.application.ingestion.contracts import DocumentDeletionTarget
from src.application.ingestion.deletion import (
    DocumentDeletionService,
    DocumentDeletionUnavailable,
)
from src.application.services.graph_storages.falkor_storage import FalkorDBStorage


def test_document_deletion_cleans_graph_files_and_database_in_order():
    async def scenario():
        store, storage, graph = AsyncMock(), AsyncMock(), AsyncMock()
        job_id, other_job_id, user_id, document_id = (
            uuid4(),
            uuid4(),
            uuid4(),
            uuid4(),
        )
        store.prepare_document_deletion.return_value = DocumentDeletionTarget(
            document_id=document_id,
            job_ids=(job_id, other_job_id),
            file_keys=("originals/one", "originals/two"),
        )
        store.purge_document.return_value = True

        deleted = await DocumentDeletionService(store, storage, graph).delete(
            job_id, user_id
        )

        assert deleted
        graph.remove_cards.assert_awaited_once_with([str(job_id), str(other_job_id)])
        assert storage.delete.await_args_list == [
            call("originals/one"),
            call("originals/two"),
        ]
        store.purge_document.assert_awaited_once_with(document_id, user_id)

    asyncio.run(scenario())


def test_document_deletion_keeps_prepared_record_for_safe_retry_on_failure():
    async def scenario():
        store, storage, graph = AsyncMock(), AsyncMock(), AsyncMock()
        job_id, user_id, document_id = uuid4(), uuid4(), uuid4()
        store.prepare_document_deletion.return_value = DocumentDeletionTarget(
            document_id=document_id,
            job_ids=(job_id,),
            file_keys=("originals/file",),
        )
        graph.remove_cards.side_effect = RuntimeError("graph unavailable")

        with pytest.raises(DocumentDeletionUnavailable):
            await DocumentDeletionService(store, storage, graph).delete(job_id, user_id)

        storage.delete.assert_not_awaited()
        store.purge_document.assert_not_awaited()

    asyncio.run(scenario())


def test_graph_card_removal_is_idempotent_and_recalculates_weights():
    async def scenario():
        graph = AsyncMock()
        client = MagicMock()
        client.select_graph.return_value = graph
        storage = FalkorDBStorage(client, "knowledge")

        await storage.remove_cards(["card-1", "card-1", "card-2"])

        assert graph.query.await_count == 6
        assert graph.query.await_args_list[0].args[1] == {
            "card_ids": ["card-1", "card-2"]
        }
        relation_queries = [
            invocation.args[0] for invocation in graph.query.await_args_list[1:3]
        ]
        assert all(
            "relation.weight = size(remaining)" in query for query in relation_queries
        )
        assert "RELATED_TO" in relation_queries[0]
        assert "IN_DOMAIN" in relation_queries[1]

    asyncio.run(scenario())
