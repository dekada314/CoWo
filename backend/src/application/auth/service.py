from uuid import uuid4

import structlog

from src.application.auth.contracts import (
    EmailAlreadyRegistered,
    InactiveUser,
    InvalidCredentials,
    InvalidToken,
    RefreshTokenReuse,
    TokenPair,
)
from src.domain.entities.user import User
from src.domain.exceptions import UserAlreadyExists
from src.domain.value_objects.email import Email
from src.infrastructure.database.repositories.user_repository import UserRepository
from src.infrastructure.security.passwords import PasswordManager
from src.infrastructure.security.refresh_sessions import (
    RefreshSessionStore,
    RotationResult,
)
from src.infrastructure.security.tokens import JWTManager

logger = structlog.get_logger(__name__)


class AuthService:
    def __init__(
        self,
        users: UserRepository,
        passwords: PasswordManager,
        tokens: JWTManager,
        sessions: RefreshSessionStore,
    ) -> None:
        self._users = users
        self._passwords = passwords
        self._tokens = tokens
        self._sessions = sessions

    async def register(self, email: str, password: str) -> User:
        user = User(id=uuid4(), email=Email(email), is_active=True)
        password_hash = await self._passwords.hash(password)
        try:
            saved = await self._users.save(user, password_hash)
        except UserAlreadyExists as exc:
            raise EmailAlreadyRegistered() from exc
        logger.info("auth_user_registered", user_id=str(saved.id))
        return saved

    async def login(self, email: str, password: str) -> TokenPair:
        found = await self._users.find_by_email(str(Email(email)))
        if found is None:
            await self._passwords.verify_unknown(password)
            raise InvalidCredentials()
        user, password_hash = found
        if not await self._passwords.verify(password, password_hash):
            raise InvalidCredentials()
        self._ensure_active(user)
        session_id = uuid4().hex
        refresh_token, refresh_jti = self._tokens.create_refresh(
            user.id,
            session_id,
        )
        await self._sessions.create(
            session_id,
            refresh_jti,
            self._tokens.refresh_expires_in,
        )
        logger.info(
            "auth_session_created",
            user_id=str(user.id),
            auth_session_id=session_id,
        )
        return TokenPair(
            access_token=self._tokens.create_access(user.id, session_id),
            refresh_token=refresh_token,
            access_expires_in=self._tokens.access_expires_in,
        )

    async def refresh(self, refresh_token: str) -> TokenPair:
        claims = self._tokens.decode_refresh(refresh_token)
        user = await self._users.find_by_id(claims.user_id)
        if user is None:
            raise InvalidToken()
        self._ensure_active(user)
        session_id = claims.session_id
        if session_id is None:
            raise InvalidToken()
        next_refresh, next_jti = self._tokens.create_refresh(user.id, session_id)
        result = await self._sessions.rotate(
            session_id,
            claims.jti,
            next_jti,
            self._tokens.refresh_expires_in,
        )
        if result == RotationResult.REUSED:
            logger.warning(
                "auth_refresh_reuse_detected",
                user_id=str(user.id),
                auth_session_id=session_id,
            )
            raise RefreshTokenReuse()
        if result == RotationResult.MISSING:
            raise InvalidToken()
        logger.info(
            "auth_session_refreshed",
            user_id=str(user.id),
            auth_session_id=session_id,
        )
        return TokenPair(
            access_token=self._tokens.create_access(user.id, session_id),
            refresh_token=next_refresh,
            access_expires_in=self._tokens.access_expires_in,
        )

    async def logout(self, refresh_token: str | None) -> None:
        if not refresh_token:
            return
        try:
            claims = self._tokens.decode_refresh(refresh_token)
        except InvalidToken:
            return
        if claims.session_id is not None:
            await self._sessions.revoke(claims.session_id)
            logger.info(
                "auth_session_revoked",
                user_id=str(claims.user_id),
                auth_session_id=claims.session_id,
            )

    async def authenticate_access(self, access_token: str) -> User:
        claims = self._tokens.decode_access(access_token)
        user = await self._users.find_by_id(claims.user_id)
        if user is None:
            raise InvalidToken()
        self._ensure_active(user)
        return user

    @staticmethod
    def _ensure_active(user: User) -> None:
        if not user.is_active:
            raise InactiveUser()
