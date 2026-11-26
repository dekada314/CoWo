"""Run inside app against the explicitly enabled llm-stub compose override."""

import asyncio
from uuid import UUID, uuid4

import httpx
from falkordb.asyncio import FalkorDB
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.application.interfaces.storages.file_storage import FileStorage
from src.core.settings import get_settings
from src.infrastructure.database.models.document import DocumentORM
from src.infrastructure.database.models.document_version import DocumentVersionORM
from src.infrastructure.database.models.ingestion_job import IngestionJobORM
from src.infrastructure.database.models.knowledge_card import KnowledgeCardORM
from src.infrastructure.database.models.user import UserORM
from src.infrastructure.taskiq.broker import broker
from src.infrastructure.taskiq.runtime import worker_runtime
from src.infrastructure.taskiq.tasks import ingestion
from src.presentation.api.main import container


async def main():
    config = get_settings()
    assert config.llm.model_analyst == "cowo-integration-stub", "test override required"
    engine = create_async_engine(config.postgres.url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    ids = []
    user_ids = []
    originals = {}
    try:
        async with httpx.AsyncClient(base_url="http://app:8000", timeout=10) as client:
            unauthorized = await client.get(f"/api/v1/ingestion/jobs/{uuid4()}")
            assert unauthorized.status_code == 401
            email = f"integration-{uuid4().hex}@example.com"
            registration = await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "StrongPass1"},
            )
            registration.raise_for_status()
            user_ids.append(UUID(registration.json()["id"]))
            duplicate = await client.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "StrongPass1"},
            )
            assert duplicate.status_code == 409
            invalid_login = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "WrongPass1"},
            )
            assert invalid_login.status_code == 401
            login = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "StrongPass1"},
            )
            login.raise_for_status()
            set_cookie = login.headers["set-cookie"].lower()
            assert "httponly" in set_cookie
            assert "samesite=lax" in set_cookie
            client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
            me = await client.get("/api/v1/auth/me")
            me.raise_for_status()
            assert me.json()["email"] == email
            for index in range(6):
                content = (
                    f"RAG test document {index}. Chunking preserves context.\n" * 300
                ).encode()
                response = await client.post(
                    "/api/v1/ingestion/documents",
                    files={"file": (f"test-{index}.txt", content, "text/plain")},
                )
                response.raise_for_status()
                job_id = response.json()["id"]
                ids.append(UUID(job_id))
                originals[job_id] = content
            async with asyncio.timeout(90):
                while True:
                    statuses = []
                    for job_id in ids:
                        response = await client.get(f"/api/v1/ingestion/jobs/{job_id}")
                        response.raise_for_status()
                        job = response.json()
                        assert job["status"] != "failed", job
                        statuses.append(job["status"])
                    if all(status == "completed" for status in statuses):
                        break
                    await asyncio.sleep(1)
            for job_id in ids:
                card = (
                    await client.get(f"/api/v1/ingestion/jobs/{job_id}/card")
                ).json()
                assert card["filename"] == f"test-{ids.index(job_id)}.txt"
                assert "stub model" in card["analysis"]["summary"]
                original = await client.get(card["original_url"])
                assert original.content == originals[str(job_id)]
            async with worker_runtime(config) as services:
                assert await services.community_agent.run() == 1
            answer = await client.post(
                "/api/v1/retrieval/answer",
                json={"question": "How does chunking preserve context?"},
            )
            answer.raise_for_status()
            payload = answer.json()
            assert payload["citations"]
            assert payload["evidence_paths"]
            graph = await client.get("/api/v1/graph")
            graph.raise_for_status()
            graph_payload = graph.json()
            assert graph_payload["domains"]
            assert graph_payload["concepts"]
            concept_cards = await client.get(
                f"/api/v1/graph/concepts/{graph_payload['concepts'][0]['id']}/cards"
            )
            concept_cards.raise_for_status()
            assert concept_cards.json()

            second_email = f"integration-{uuid4().hex}@example.com"
            async with httpx.AsyncClient(
                base_url="http://app:8000", timeout=10
            ) as second_client:
                second_registration = await second_client.post(
                    "/api/v1/auth/register",
                    json={"email": second_email, "password": "StrongPass1"},
                )
                second_registration.raise_for_status()
                user_ids.append(UUID(second_registration.json()["id"]))
                second_login = await second_client.post(
                    "/api/v1/auth/login",
                    json={"email": second_email, "password": "StrongPass1"},
                )
                second_login.raise_for_status()
                second_client.headers["Authorization"] = (
                    f"Bearer {second_login.json()['access_token']}"
                )
                hidden = await second_client.get(f"/api/v1/ingestion/jobs/{ids[0]}")
                assert hidden.status_code == 404
                hidden_graph = await second_client.get("/api/v1/graph")
                hidden_graph.raise_for_status()
                assert hidden_graph.json()["concepts"] == []
                hidden_answer = await second_client.post(
                    "/api/v1/retrieval/answer",
                    json={"question": "What is retrieval?"},
                )
                assert hidden_answer.status_code == 404
                assert (
                    await second_client.post("/api/v1/auth/logout")
                ).status_code == 204

            cookie_name = config.auth.refresh_cookie_name
            old_refresh = client.cookies.get(cookie_name)
            refreshed = await client.post("/api/v1/auth/refresh")
            refreshed.raise_for_status()
            client.headers["Authorization"] = (
                f"Bearer {refreshed.json()['access_token']}"
            )
            assert (await client.get("/api/v1/auth/me")).status_code == 200
            async with httpx.AsyncClient(
                base_url="http://app:8000", timeout=10
            ) as replay_client:
                replay_client.cookies.set(
                    cookie_name,
                    old_refresh,
                    path=config.auth.refresh_cookie_path,
                )
                replay = await replay_client.post("/api/v1/auth/refresh")
                assert replay.status_code == 401
                assert replay.json()["detail"] == "refresh_token_reused"
            assert (await client.post("/api/v1/auth/refresh")).status_code == 401

            relogin = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": "StrongPass1"},
            )
            relogin.raise_for_status()
            assert (await client.post("/api/v1/auth/logout")).status_code == 204
            assert (await client.post("/api/v1/auth/refresh")).status_code == 401

        await broker.startup()
        for job_id in ids:
            await ingestion.kiq(str(job_id))
        await asyncio.sleep(2)
        async with sessions() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(KnowledgeCardORM)
                .where(KnowledgeCardORM.job_id.in_(ids))
            )
            assert count == len(ids)
            attempts = (
                await session.scalars(
                    select(IngestionJobORM.attempt).where(IngestionJobORM.id.in_(ids))
                )
            ).all()
            assert attempts == [1] * len(ids)
        print(
            f"PASS: {len(ids)} jobs, multi-worker delivery, cards, original downloads, "
            "duplicate messages; one card and one attempt per job"
        )
    finally:
        if ids:
            async with sessions.begin() as session:
                rows = (
                    await session.execute(
                        select(
                            DocumentVersionORM.document_id,
                            DocumentVersionORM.s3_file_key,
                        )
                        .join(
                            IngestionJobORM,
                            IngestionJobORM.document_version_id
                            == DocumentVersionORM.id,
                        )
                        .where(IngestionJobORM.id.in_(ids))
                    )
                ).all()
                await session.execute(
                    delete(DocumentORM).where(
                        DocumentORM.id.in_([row[0] for row in rows])
                    )
                )
            storage = await container.get(FileStorage)
            for _, key in rows:
                await storage.delete(key)
        if user_ids:
            async with sessions.begin() as session:
                await session.execute(delete(UserORM).where(UserORM.id.in_(user_ids)))
        falkor = await container.get(FalkorDB)
        if config.falkordb.graph_name in await falkor.list_graphs():
            await falkor.select_graph(config.falkordb.graph_name).delete()
        await broker.shutdown()
        await container.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
