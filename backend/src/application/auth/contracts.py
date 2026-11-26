from dataclasses import dataclass


class AuthError(Exception):
    pass


class InvalidCredentials(AuthError):
    pass


class InvalidToken(AuthError):
    pass


class InactiveUser(AuthError):
    pass


class EmailAlreadyRegistered(AuthError):
    pass


class RefreshTokenReuse(AuthError):
    pass


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_in: int
