from typing import AsyncIterable

import aioboto3
import redis.asyncio as redis
from botocore.client import Config
from dishka import Provider, Scope, provide
from falkordb.asyncio import FalkorDB
from types_aiobotocore_s3 import S3Client

from src.core.settings import Settings


class InfrastructureProvider(Provider):
    def __init__(self, config: Settings, scope=None, component=None, when=None):
        super().__init__(scope, component, when)
        self._config = config

    @provide(scope=Scope.APP)
    async def minio_client(self) -> AsyncIterable[S3Client]:
        conf = self._config.minio
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=conf.endpoint_url,
            aws_access_key_id=conf.access_key,
            aws_secret_access_key=conf.secret_key,
            config=Config(signature_version="s3v4"),
        ) as client:
            yield client

    @provide(scope=Scope.APP)
    async def redis_client(self) -> AsyncIterable[redis.Redis]:
        conf = self._config.redis
        client = redis.Redis(
            host=conf.host,
            port=conf.port,
            db=conf.db,
            password=conf.password,
            ssl=conf.ssl,
            max_connections=conf.max_connections,
            socket_timeout=conf.socket_timeout,
            decode_responses=True,
        )
        await client.ping()
        yield client
        await client.close()

    @provide(scope=Scope.APP)
    async def falkor_client(self) -> AsyncIterable[FalkorDB]:
        conf = self._config.falkordb
        client = FalkorDB(
            host=conf.host,
            port=conf.port,
            username=conf.username,
            password=conf.password,
        )
        await client.connection.ping()
        yield client
        await client.close()
