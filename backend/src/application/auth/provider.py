import redis.asyncio as redis
from dishka import Provider, Scope, provide

from src.application.auth.service import AuthService
from src.core.settings import Settings
from src.infrastructure.database.repositories.user_repository import UserRepository
from src.infrastructure.security.passwords import PasswordManager
from src.infrastructure.security.refresh_sessions import RefreshSessionStore
from src.infrastructure.security.tokens import JWTManager


class AuthProvider(Provider):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings

    @provide(scope=Scope.APP)
    def password_manager(self) -> PasswordManager:
        return PasswordManager()

    @provide(scope=Scope.APP)
    def token_manager(self) -> JWTManager:
        return JWTManager(self._settings.auth)

    @provide(scope=Scope.APP)
    def refresh_sessions(self, client: redis.Redis) -> RefreshSessionStore:
        return RefreshSessionStore(client, self._settings.auth)

    @provide(scope=Scope.REQUEST)
    def auth_service(
        self,
        users: UserRepository,
        passwords: PasswordManager,
        tokens: JWTManager,
        sessions: RefreshSessionStore,
    ) -> AuthService:
        return AuthService(users, passwords, tokens, sessions)
