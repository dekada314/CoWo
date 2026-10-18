from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import APIRouter, FastAPI

from src.infrastucture.conteiner import Container
from src.presentation.api.v1.auth_routes import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    container = Container()  # Внутри объявление глоб конфига
    container.init_resources()
    yield

    container.shutdown_resources()


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
