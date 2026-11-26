from typing import Annotated

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends, Request, Response, status

from src.application.auth.contracts import InvalidToken
from src.application.auth.service import AuthService
from src.core.settings import get_settings
from src.domain.entities.user import User
from src.presentation.api.dependencies.auth import require_user
from src.presentation.schemas.user import (
    AccessTokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=str(user.email),
        is_active=user.is_active,
    )


def token_response(access_token: str, expires_in: int) -> AccessTokenResponse:
    return AccessTokenResponse(
        access_token=access_token,
        expires_in=expires_in,
    )


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    config = get_settings().auth
    response.set_cookie(
        key=config.refresh_cookie_name,
        value=refresh_token,
        max_age=config.refresh_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=config.cookie_secure,
        samesite=config.cookie_samesite,
        path=config.refresh_cookie_path,
        domain=config.cookie_domain,
    )


def delete_refresh_cookie(response: Response) -> None:
    config = get_settings().auth
    response.delete_cookie(
        key=config.refresh_cookie_name,
        path=config.refresh_cookie_path,
        domain=config.cookie_domain,
        secure=config.cookie_secure,
        httponly=True,
        samesite=config.cookie_samesite,
    )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
)
@inject
async def register(
    request: UserRegister,
    service: FromDishka[AuthService],
) -> UserResponse:
    return user_response(await service.register(str(request.email), request.password))


@router.post("/login", response_model=AccessTokenResponse)
@inject
async def login(
    request: UserLogin,
    response: Response,
    service: FromDishka[AuthService],
) -> AccessTokenResponse:
    pair = await service.login(str(request.email), request.password)
    set_refresh_cookie(response, pair.refresh_token)
    return token_response(pair.access_token, pair.access_expires_in)


@router.post("/refresh", response_model=AccessTokenResponse)
@inject
async def refresh(
    request: Request,
    response: Response,
    service: FromDishka[AuthService],
) -> AccessTokenResponse:
    cookie_name = get_settings().auth.refresh_cookie_name
    refresh_token = request.cookies.get(cookie_name)
    if not refresh_token:
        raise InvalidToken()
    pair = await service.refresh(refresh_token)
    set_refresh_cookie(response, pair.refresh_token)
    return token_response(pair.access_token, pair.access_expires_in)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
@inject
async def logout(
    request: Request,
    service: FromDishka[AuthService],
) -> Response:
    config = get_settings().auth
    await service.logout(request.cookies.get(config.refresh_cookie_name))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    delete_refresh_cookie(response)
    return response


@router.get("/me", response_model=UserResponse)
async def me(
    user: Annotated[User, Depends(require_user)],
) -> UserResponse:
    return user_response(user)
