from fastapi import APIRouter, status

router = APIRouter(prefix="/auth")


@router.get(path="/health_check")
async def health_check():
    return {"status": status.HTTP_200_OK}
