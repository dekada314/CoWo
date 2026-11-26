import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import configure_mappers

from src.application.auth.contracts import InvalidToken, RefreshTokenReuse
from src.application.auth.service import AuthService
from src.application.graph.service import KnowledgeGraphService
from src.core.settings import AuthSettings
from src.domain.entities.user import User
from src.domain.enums import JobStatus
from src.domain.value_objects.email import Email
from src.infrastructure.database import models
from src.infrastructure.database.models.base import Base
from src.infrastructure.security.passwords import PasswordManager
from src.infrastructure.security.refresh_sessions import RotationResult
from src.infrastructure.security.tokens import JWTManager
from src.pipelines.ingestion.parsing.parser_context import RAGDocumentParser
from src.pipelines.ingestion.parsing.strategies.parser_strategy import (
    ParsedChunk,
)
from src.presentation.api.main import app
from src.presentation.schemas.user import UserRegister


class StubParser:
    async def parse(self, content: bytes, filename: str = "") -> list[ParsedChunk]:
        return [
            ParsedChunk(
                text=content.decode(),
                raw_text=content.decode(),
                index=0,
                metadata={"filename": filename},
            )
        ]


def test_orm_mappers_and_metadata_are_valid() -> None:
    configure_mappers()
    assert models.DocumentORM.metadata is Base.metadata
    assert set(Base.metadata.tables) == {
        "agent_runs",
        "chat_sessions",
        "document_versions",
        "documents",
        "ingestion_jobs",
        "users",
        "knowledge_cards",
    }


def test_application_exposes_liveness_route() -> None:
    schema = app.openapi()
    paths = set(schema["paths"])
    assert "/api/v1/health/live" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/auth/refresh" in paths
    assert "/api/v1/auth/me" in paths
    assert "/api/v1/graph" in paths
    assert "/api/v1/graph/concepts/{concept_id}/cards" in paths
    assert "/api/v1/ingestion/documents" in paths
    assert "get" in schema["paths"]["/api/v1/ingestion/documents"]
    assert "/api/v1/ingestion/jobs/{job_id}" in paths
    assert "delete" in schema["paths"]["/api/v1/ingestion/jobs/{job_id}"]
    assert schema["paths"]["/api/v1/ingestion/documents"]["post"]["security"]


def test_user_registration_schema() -> None:
    registration = UserRegister(
        email="user@example.com",
        password="StrongPass",
    )
    assert registration.email == "user@example.com"
    assert registration.password == "StrongPass"
    for invalid_password in ("Short", "lowercase", "UPPERCASE"):
        with pytest.raises(ValidationError):
            UserRegister(
                email="user@example.com",
                password=invalid_password,
            )


def test_document_parser_dispatches_by_extension() -> None:
    parser = RAGDocumentParser()
    parser.register_strategy("txt", StubParser())

    chunks = asyncio.run(parser.parse(b"content", "note.txt"))

    assert chunks[0].text == "content"
    assert chunks[0].metadata == {"filename": "note.txt"}


def test_job_status_queued_value_is_spelled_correctly() -> None:
    assert JobStatus.QUEUED.value == "queued"


def test_auth_tokens_rotate_and_reject_type_confusion() -> None:
    async def scenario() -> None:
        config = AuthSettings(_env_file=None, secret_key="x" * 32)
        users = AsyncMock()
        sessions = AsyncMock()
        passwords = PasswordManager()
        tokens = JWTManager(config)
        service = AuthService(users, passwords, tokens, sessions)
        user = User(uuid4(), Email("auth@example.com"), True)
        password_hash = await passwords.hash("StrongPass1")
        users.find_by_email.return_value = (user, password_hash)
        users.find_by_id.return_value = user

        pair = await service.login("AUTH@example.com", "StrongPass1")
        assert tokens.decode_access(pair.access_token).user_id == user.id
        with pytest.raises(InvalidToken):
            tokens.decode_access(pair.refresh_token)

        sessions.rotate.return_value = RotationResult.ROTATED
        rotated = await service.refresh(pair.refresh_token)
        assert rotated.refresh_token != pair.refresh_token
        assert tokens.decode_access(rotated.access_token).user_id == user.id

        sessions.rotate.return_value = RotationResult.REUSED
        with pytest.raises(RefreshTokenReuse):
            await service.refresh(rotated.refresh_token)

    asyncio.run(scenario())


def test_graph_overview_keeps_only_user_owned_concepts() -> None:
    async def scenario() -> None:
        user_id = uuid4()
        owned_job_id = uuid4()
        foreign_job_id = uuid4()
        graph = AsyncMock()
        store = AsyncMock()
        graph.get_visual_graph.return_value = {
            "domains": [
                {
                    "id": "domain",
                    "name": "Домен",
                    "summary": "Описание домена",
                    "communities": [
                        {
                            "id": "community",
                            "name": "Сообщество",
                            "summary": "Описание сообщества",
                            "source": "analyst",
                            "active": True,
                        }
                    ],
                }
            ],
            "concepts": [
                {
                    "id": "owned",
                    "name": "Доступная концепция",
                    "summary": "Описание",
                    "card_ids": [str(owned_job_id)],
                    "domains": [{"id": "domain", "weight": 1}],
                },
                {
                    "id": "foreign",
                    "name": "Чужая концепция",
                    "summary": "Описание",
                    "card_ids": [str(foreign_job_id)],
                    "domains": [{"id": "domain", "weight": 1}],
                },
            ],
            "edges": [{"source_id": "owned", "target_id": "foreign", "weight": 1}],
        }
        store.cards.return_value = {owned_job_id: object()}

        result = await KnowledgeGraphService(graph, store).overview(user_id)

        assert [concept.id for concept in result.concepts] == ["owned"]
        assert [domain.id for domain in result.domains] == ["domain"]
        assert [community.id for community in result.communities] == ["community"]
        assert result.edges == []
        store.cards.assert_awaited_once()
        assert store.cards.await_args.args[1] == user_id

    asyncio.run(scenario())
