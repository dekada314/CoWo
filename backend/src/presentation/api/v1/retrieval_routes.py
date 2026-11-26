from typing import Annotated

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends

from src.application.retrieval.contracts import AnswerRequest, AnswerResponse
from src.application.retrieval.service import RetrievalService
from src.domain.entities.user import User
from src.presentation.api.dependencies.auth import require_user

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/answer", response_model=AnswerResponse)
@inject
async def answer_question(
    request: AnswerRequest,
    service: FromDishka[RetrievalService],
    user: Annotated[User, Depends(require_user)],
) -> AnswerResponse:
    return await service.answer(request.question, user.id)
