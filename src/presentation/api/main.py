from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dishka import make_async_container
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import APIRouter, FastAPI
from src.application.services.service_provider import ServiceProvider
from src.core.settings import get_settings
from src.infrastructure.clients.clients_provider import ClientsProvider
from src.infrastructure.database.database_provider import DBConnectionProvider
from src.infrastructure.taskiq.broker import broker
from src.presentation.api.v1.auth_routes import router as auth_router

config = get_settings()
container = make_async_container(
    DBConnectionProvider(config.postgres),
    ClientsProvider(config),
    ServiceProvider(config),
    FastapiProvider(),
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    if not broker.is_worker_process:
        await broker.startup()
    yield

    if not broker.is_worker_process:
        await broker.shutdown()
    container.close()


app = FastAPI(
    title="CoWo",
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True,
    },
)
setup_dishka(container=container, app=app)
router = APIRouter(prefix="/api/v1")

router.include_router(auth_router)

app.include_router(router)
