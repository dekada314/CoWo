from typing import AsyncIterable

from dishka import Provider, Scope, provide
from falkordb.asyncio import FalkorDB
from types_aiobotocore_s3 import S3Client

from src.application.interfaces.file_storage import FileStorage
from src.application.interfaces.graph_storage import GraphStorage
from src.application.services.file_storages.minio_storage import (
    MinioFileStorage,
)
from src.application.services.graph_storages.falkor_storage import (
    FalkorDBStorage,
)
from src.core.settings import Settings


class ServiceProvider(Provider):
    def __init__(self, config: Settings, scope=None, component=None, when=None):
        super().__init__(scope, component, when)
        self._config = config

    @provide(scope=Scope.APP)
    async def file_service(self, minio_client: S3Client) -> FileStorage:
        return MinioFileStorage(client=minio_client, config=self._config.minio)

    @provide(scope=Scope.APP)
    async def graph_storage(self, falkor_client: FalkorDB) -> GraphStorage:
        return FalkorDBStorage(
            client=falkor_client, config=self._config.falkordb
        )
