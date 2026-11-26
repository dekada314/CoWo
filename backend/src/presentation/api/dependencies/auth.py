from typing import Annotated

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.application.auth.contracts import InvalidToken
from src.application.auth.service import AuthService
from src.domain.entities.user import User

bearer = HTTPBearer(auto_error=False)


@inject
async def require_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer),
    ],
    service: FromDishka[AuthService],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise InvalidToken()
    return await service.authenticate_access(credentials.credentials)
