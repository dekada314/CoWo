import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
from fastapi import FastAPI

from src.application.auth.service import AuthService
from src.application.ingestion.contracts import JobView
from src.application.ingestion.deletion import DocumentDeletionService
from src.application.interfaces.storages.file_storage import FileStorage, StoredFile
from src.core.settings import get_settings
from src.domain.entities.user import User
from src.domain.value_objects.email import Email
from src.infrastructure.database.repositories.ingestion_store import IngestionStore
from src.presentation.api.v1.ingestion_routes import router


class FakeScope:
    def __init__(self, store, storage, auth, deletion=None):
        self.dependencies = {
            IngestionStore: store,
            FileStorage: storage,
            AuthService: auth,
            DocumentDeletionService: deletion,
        }

    async def get(self, dependency, component="", **kwargs):
        return self.dependencies[dependency]


def test_upload_accepts_durable_job_and_validates_input(monkeypatch):
    async def scenario():
        config = get_settings()
        monkeypatch.setattr(config.llm, "model_analyst", "local-test")
        monkeypatch.setattr(config.app, "max_upload_size_mb", 1)
        store, storage, auth, deletion = (
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
        )
        user = User(uuid4(), Email("user@example.com"), True)
        auth.authenticate_access.return_value = user
        store.submit.return_value = JobView(
            id=uuid4(),
            document_version_id=uuid4(),
            status="queued",
            stage="uploaded",
            attempt=0,
            pipeline_version="analyst-v1",
            error_message=None,
            started_at=None,
            finished_at=None,
        )
        storage.upload_file.return_value = StoredFile(
            "key", "documents", 6, "text/plain"
        )
        store.list_documents.return_value = []
        app = FastAPI()

        @app.middleware("http")
        async def inject_scope(request, call_next):
            request.state.dishka_container = FakeScope(store, storage, auth, deletion)
            return await call_next(request)

        app.include_router(router, prefix="/api/v1")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": "Bearer access-token"},
        ) as client:
            result = await client.post(
                "/api/v1/ingestion/documents",
                files={"file": ("test.txt", b"source", "text/plain")},
            )
            assert result.status_code == 202, result.text
            assert result.json()["status"] == "queued"
            assert result.headers["Location"].endswith(result.json()["id"])
            storage.upload_file.assert_awaited_once()
            store.submit.assert_awaited_once()
            assert store.submit.await_args.args[-1] == user.id

            documents = await client.get("/api/v1/ingestion/documents")
            assert documents.status_code == 200
            assert documents.json() == []
            store.list_documents.assert_awaited_once_with(user.id)

            for name, content, expected in [
                ("../file.txt", b"x", 422),
                ("file.exe", b"x", 415),
                ("file.txt", b"", 422),
                ("file.txt", b"x" * (1024**2 + 1), 413),
            ]:
                rejected = await client.post(
                    "/api/v1/ingestion/documents",
                    files={"file": (name, content, "application/octet-stream")},
                )
                assert rejected.status_code == expected, rejected.text
            assert storage.upload_file.await_count == 1
            job_id = uuid4()
            deletion.delete.return_value = True
            deleted = await client.delete(f"/api/v1/ingestion/jobs/{job_id}")
            assert deleted.status_code == 204
            deletion.delete.assert_awaited_once_with(job_id, user.id)

            monkeypatch.setattr(config.llm, "model_analyst", "")
            unavailable = await client.post(
                "/api/v1/ingestion/documents",
                files={"file": ("a.txt", b"source", "text/plain")},
            )
            assert unavailable.status_code == 503

    asyncio.run(scenario())
