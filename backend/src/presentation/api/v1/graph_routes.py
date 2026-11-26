from typing import Annotated

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends

from src.application.graph.contracts import KnowledgeGraphView
from src.application.graph.service import KnowledgeGraphService
from src.application.ingestion.contracts import KnowledgeCardView
from src.domain.entities.user import User
from src.presentation.api.dependencies.auth import require_user

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("", response_model=KnowledgeGraphView)
@inject
async def get_graph(
    service: FromDishka[KnowledgeGraphService],
    user: Annotated[User, Depends(require_user)],
) -> KnowledgeGraphView:
    return await service.overview(user.id)


@router.get(
    "/concepts/{concept_id}/cards",
    response_model=list[KnowledgeCardView],
)
@inject
async def get_concept_cards(
    concept_id: str,
    service: FromDishka[KnowledgeGraphService],
    user: Annotated[User, Depends(require_user)],
) -> list[KnowledgeCardView]:
    return await service.concept_cards(concept_id, user.id)
