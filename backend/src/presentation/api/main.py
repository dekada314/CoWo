from contextlib import asynccontextmanager
from time import perf_counter
from typing import AsyncGenerator
from uuid import uuid4

import structlog
from dishka import make_async_container
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import APIRouter, FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.application.auth.contracts import (
    AuthError,
    EmailAlreadyRegistered,
    InactiveUser,
    InvalidCredentials,
    RefreshTokenReuse,
)
from src.application.auth.provider import AuthProvider
from src.application.graph.contracts import GraphConceptNotFound, GraphUnavailable
from src.application.graph.provider import GraphProvider
from src.application.ingestion.provider import IngestionProvider
from src.application.retrieval.contracts import (
    KnowledgeNotFound,
    RetrievalUnavailable,
)
from src.application.retrieval.provider import RetrievalProvider
from src.application.services.service_provider import ServiceProvider
from src.core.logging import configure_logging, reset_log_context, start_log_context
from src.core.settings import get_settings
from src.infrastructure.clients.clients_provider import ClientsProvider
from src.infrastructure.database.database_provider import DBConnectionProvider
from src.infrastructure.database.repositories.repository_provider import (
    RepositoryProvider,
)
from src.infrastructure.taskiq.broker import broker
from src.presentation.api.v1.auth_routes import router as auth_router
from src.presentation.api.v1.graph_routes import router as graph_router
from src.presentation.api.v1.health_routes import router as health_router
from src.presentation.api.v1.ingestion_routes import router as ingestion_router
from src.presentation.api.v1.retrieval_routes import router as retrieval_router

config = get_settings()
configure_logging("api", config.logging)
logger = structlog.get_logger(__name__)
container = make_async_container(
    DBConnectionProvider(config.postgres),
    ClientsProvider(config),
    ServiceProvider(config),
    RepositoryProvider(),
    AuthProvider(config),
    IngestionProvider(config),
    RetrievalProvider(config),
    GraphProvider(),
    FastapiProvider(),
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    broker_started = False
    try:
        await broker.startup()
        broker_started = True
        yield
    finally:
        try:
            if broker_started:
                await broker.shutdown()
        finally:
            await container.close()


app = FastAPI(
    title=config.app.name,
    version=config.app.version,
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True,
    },
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.app.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError) -> JSONResponse:
    if isinstance(exc, EmailAlreadyRegistered):
        code = status.HTTP_409_CONFLICT
        detail = "email_already_registered"
    elif isinstance(exc, InactiveUser):
        code = status.HTTP_403_FORBIDDEN
        detail = "user_inactive"
    elif isinstance(exc, InvalidCredentials):
        code = status.HTTP_401_UNAUTHORIZED
        detail = "invalid_credentials"
    elif isinstance(exc, RefreshTokenReuse):
        code = status.HTTP_401_UNAUTHORIZED
        detail = "refresh_token_reused"
    else:
        code = status.HTTP_401_UNAUTHORIZED
        detail = "invalid_token"
    headers = {"WWW-Authenticate": "Bearer"} if code == 401 else None
    response = JSONResponse(
        status_code=code,
        content={"detail": detail},
        headers=headers,
    )
    if code == status.HTTP_401_UNAUTHORIZED and request.url.path == (
        "/api/v1/auth/refresh"
    ):
        response.delete_cookie(
            key=config.auth.refresh_cookie_name,
            path=config.auth.refresh_cookie_path,
            domain=config.auth.cookie_domain,
            secure=config.auth.cookie_secure,
            httponly=True,
            samesite=config.auth.cookie_samesite,
        )
    return response


@app.exception_handler(KnowledgeNotFound)
async def knowledge_not_found_handler(
    request: Request, exc: KnowledgeNotFound
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


@app.exception_handler(RetrievalUnavailable)
async def retrieval_unavailable_handler(
    request: Request, exc: RetrievalUnavailable
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": str(exc)},
    )


@app.exception_handler(GraphConceptNotFound)
async def graph_concept_not_found_handler(
    request: Request, exc: GraphConceptNotFound
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


@app.exception_handler(GraphUnavailable)
async def graph_unavailable_handler(
    request: Request, exc: GraphUnavailable
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": str(exc)},
    )


@app.middleware("http")
async def request_logging(request: Request, call_next) -> Response:
    request_id = str(uuid4())
    trace_id = uuid4().hex
    context_tokens = start_log_context(
        trace_id=trace_id,
        request_id=request_id,
    )
    started = perf_counter()
    try:
        response = await call_next(request)
        elapsed_ms = round((perf_counter() - started) * 1000, 2)
        if response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            logger.error(
                "http_request_failed",
                http_method=request.method,
                http_path=request.url.path,
                status_code=response.status_code,
                duration_ms=elapsed_ms,
            )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Trace-ID"] = trace_id
        return response
    except Exception:
        logger.exception(
            "http_request_failed",
            http_method=request.method,
            http_path=request.url.path,
            duration_ms=round((perf_counter() - started) * 1000, 2),
        )
        raise
    finally:
        reset_log_context(context_tokens)


setup_dishka(container=container, app=app)
router = APIRouter(prefix="/api/v1")

router.include_router(auth_router)
router.include_router(health_router)
router.include_router(ingestion_router)
router.include_router(retrieval_router)
router.include_router(graph_router)

app.include_router(router)
