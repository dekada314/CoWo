from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dishka import make_async_container
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import APIRouter, FastAPI

from src.application.services.service_provider import ServiceProvider
from src.core.settings import get_settings
from src.infrastucture.database.database_provider import DatabaseProvider
from src.infrastucture.infrastructure_provider import InfrastructureProvider
from src.presentation.api.v1.auth_routes import router as auth_router

config = get_settings()
container = make_async_container(
    DatabaseProvider(config.postgres),
    InfrastructureProvider(config),
    ServiceProvider(config),
    FastapiProvider(),
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    yield

    container.close()


app = FastAPI(
    title="CoWo",
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True,
    },
)
router = APIRouter(prefix="/api/v1")

router.include_router(auth_router)

app.include_router(router)
setup_dishka(container=container, app=app)
