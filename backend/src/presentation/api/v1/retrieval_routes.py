from typing import Annotated
from uuid import UUID, uuid4

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends, HTTPException, status

from src.application.retrieval.contracts import (
    AnswerRequest, AnswerResponse, ChatMessageResponse, ChatSessionResponse,
)
from src.application.retrieval.service import RetrievalService
from src.domain.entities.user import User
from src.infrastructure.database.repositories.chat_session_repository import ChatSessionRepository
from src.presentation.api.dependencies.auth import require_user

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/answer", response_model=AnswerResponse)
@inject
async def answer_question(
    request: AnswerRequest,
    service: FromDishka[RetrievalService],
    user: Annotated[User, Depends(require_user)],
    chats: FromDishka[ChatSessionRepository],
) -> AnswerResponse:
    session = await chats.find_by_id(request.session_id) if request.session_id else None
    if session is not None and session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="chat_not_found")
    result = await service.answer(request.question, user.id)
    if session is None:
        from src.domain.entities.chat_session import ChatSession
        session = await chats.save(ChatSession(uuid4(), user.id))
    await chats.add_message(session.id, "user", request.question)
    await chats.add_message(
        session.id,
        "assistant",
        result.answer,
        {"citations": [citation.model_dump(mode="json") for citation in result.citations]},
    )
    if session.title is None:
        session.auto_title_from_question(request.question)
        # save() is intentionally avoided here: title update is handled by a tiny repository method below.
        await chats.rename(session.id, session.title or request.question[:50])
    result.session_id = session.id
    return result


@router.get("/sessions", response_model=list[ChatSessionResponse])
@inject
async def list_sessions(
    chats: FromDishka[ChatSessionRepository],
    user: Annotated[User, Depends(require_user)],
) -> list[ChatSessionResponse]:
    result = []
    for session in await chats.find_by_user(user.id):
        result.append(ChatSessionResponse(
            id=session.id, title=session.title, updated_at=session.updated_at.isoformat() if session.updated_at else "",
            messages=[ChatMessageResponse(id=m.id, role=m.role, content=m.content, created_at=m.created_at.isoformat()) for m in await chats.messages(session.id)],
        ))
    return result


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_session(
    session_id: UUID,
    chats: FromDishka[ChatSessionRepository],
    user: Annotated[User, Depends(require_user)],
) -> None:
    if not await chats.delete(session_id, user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="chat_not_found")
