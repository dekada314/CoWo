from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt

from src.application.auth.contracts import InvalidToken
from src.core.settings import AuthSettings


@dataclass(frozen=True)
class TokenClaims:
    user_id: UUID
    token_type: str
    jti: str
    session_id: str | None


class JWTManager:
    def __init__(self, config: AuthSettings) -> None:
        self._config = config
        self._secret = config.secret_key.get_secret_value()

    @property
    def access_expires_in(self) -> int:
        return self._config.access_ttl_minutes * 60

    @property
    def refresh_expires_in(self) -> int:
        return self._config.refresh_ttl_days * 24 * 60 * 60

    def create_access(self, user_id: UUID, session_id: str) -> str:
        return self._encode(
            user_id,
            "access",
            timedelta(minutes=self._config.access_ttl_minutes),
            session_id,
        )[0]

    def create_refresh(
        self,
        user_id: UUID,
        session_id: str,
    ) -> tuple[str, str]:
        return self._encode(
            user_id,
            "refresh",
            timedelta(days=self._config.refresh_ttl_days),
            session_id,
        )

    def decode_access(self, token: str) -> TokenClaims:
        return self._decode(token, "access")

    def decode_refresh(self, token: str) -> TokenClaims:
        claims = self._decode(token, "refresh")
        if claims.session_id is None:
            raise InvalidToken()
        return claims

    def _encode(
        self,
        user_id: UUID,
        token_type: str,
        lifetime: timedelta,
        session_id: str,
    ) -> tuple[str, str]:
        now = datetime.now(UTC)
        jti = uuid4().hex
        payload = {
            "sub": str(user_id),
            "type": token_type,
            "jti": jti,
            "sid": session_id,
            "iat": now,
            "nbf": now,
            "exp": now + lifetime,
            "iss": self._config.issuer,
            "aud": self._config.audience,
        }
        return (
            jwt.encode(
                payload,
                self._secret,
                algorithm=self._config.algorithm,
            ),
            jti,
        )

    def _decode(self, token: str, expected_type: str) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._config.algorithm],
                audience=self._config.audience,
                issuer=self._config.issuer,
                leeway=self._config.clock_skew_seconds,
                options={
                    "require": [
                        "sub",
                        "type",
                        "jti",
                        "iat",
                        "nbf",
                        "exp",
                        "iss",
                        "aud",
                    ]
                },
            )
            if payload["type"] != expected_type:
                raise InvalidToken()
            user_id = UUID(payload["sub"])
            jti = payload["jti"]
            session_id = payload.get("sid")
            if not isinstance(jti, str) or not jti:
                raise InvalidToken()
            if session_id is not None and not isinstance(session_id, str):
                raise InvalidToken()
            return TokenClaims(user_id, expected_type, jti, session_id)
        except InvalidToken:
            raise
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
            raise InvalidToken() from exc
