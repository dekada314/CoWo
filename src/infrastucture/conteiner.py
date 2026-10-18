from dependency_injector import containers, providers
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.application.services.file_storages.minio_storage import (
    MinioFileStorage,
)
from src.application.services.graph_storages.falkor_storage import (
    FalkorDBStorage,
)
from src.core.settings import Settings, get_settings
from src.infrastucture.falkor.falkor_client import ResourceFalkorClient
from src.infrastucture.minio.minio_client import ResourceMinioClient
from src.infrastucture.redis.redis_client import ResourceRedisClient


def _build_engine(url, pool_size, max_overflow, pool_pre_ping, echo):
    return create_async_engine(
        url=url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=pool_pre_ping,
        echo=echo,
    )


def _build_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=True)


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        packages=["src.presentation.api"]
    )
    config: Settings = providers.Configuration(  # Ради подсказок, реальным типом будет Configuration
        pydantic_settings=[get_settings()]
    )
    _engine = providers.Resource(
        _build_engine,
        url=config.postgres.url,
        pool_size=config.postgres.pool_size,
        max_overflow=config.postgres.max_overflow,
        pool_pre_ping=config.postgres.pool_pre_ping,
        echo=config.postgres.echo,
    )
    _session_factory = providers.ThreadSafeSingleton(
        _build_session_factory, engine=_engine
    )
    session = providers.Factory(_session_factory)

    _minio_client = providers.Resource(
        ResourceMinioClient,
        endpoint_url=config.minio.endpoint_url,
        access_key=config.minio.access_key.get_secret_value(),
        secret_key=config.minio.secret_key.get_secret_values(),
    )
    file_storage = providers.Factory(
        MinioFileStorage, client=_minio_client, config=config.minio
    )

    _redis_client = providers.Resource(
        ResourceRedisClient,
        host=config.redis.host,
        port=config.redis.port,
        db=config.redis.db,
        password=config.redis.password.get_secret_value(),
        ssl=config.redis.ssl,
        max_connections=config.redis.max_connections,
        socket_timeut=config.redis.socket_timeout,
    )

    _falkordb_client = providers.Resource(
        ResourceFalkorClient,
        host=config.falkordb.host,
        port=config.falkordb.port,
        username=config.falkordb.username,
        password=config.falkordb.password.get_secret_value(),
    )

    graph_storage = providers.Factory(
        FalkorDBStorage, client=_falkordb_client, config=config.falkordb
    )
