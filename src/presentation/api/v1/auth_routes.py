from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, status

router = APIRouter(prefix="/auth")


@router.get(path="/health_check")
@inject
async def health_check():
    return {"status": status.HTTP_200_OK}
