from typing import AsyncIterable

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.settings import PostgresSettings


class DBConnectionProvider(Provider):
    def __init__(
        self, config: PostgresSettings, scope=None, component=None, when=None
    ):
        super().__init__(scope, component, when)
        self._config = config

    @provide(scope=Scope.APP)
    async def engine(self) -> AsyncIterable[AsyncEngine]:
        engine = create_async_engine(
            url=self._config.url,
            pool_size=self._config.pool_size,
            max_overflow=self._config.max_overflow,
            pool_pre_ping=self._config.pool_pre_ping,
            echo=self._config.echo,
        )
        yield engine
        await engine.dispose()

    @provide(scope=Scope.APP)
    def session_factory(
        self,
        engine: AsyncEngine,
    ) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(engine, expire_on_commit=True)

    @provide(scope=Scope.REQUEST)
    async def session(
        self,
        factory: async_sessionmaker[AsyncSession],
    ) -> AsyncIterable[AsyncSession]:
        async with factory() as session:
            yield session
