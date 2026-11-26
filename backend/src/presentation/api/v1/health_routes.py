from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/health", tags=["health"])


class HealthView(BaseModel):
    status: Literal["ok"]


@router.get("/live", response_model=HealthView)
async def liveness() -> HealthView:
    return HealthView(status="ok")
