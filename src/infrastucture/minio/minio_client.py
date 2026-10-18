from contextlib import AsyncExitStack

import aioboto3
from botocore.client import Config
from dependency_injector import resources


class ResourceMinioClient(resources.AsyncResource):
    async def init(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
    ):
        session = aioboto3.Session()
        self._exit_stack = AsyncExitStack()
        return await self._exit_stack.enter_async_context(
            session.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                config=Config(signature_version="s3v4"),
            )
        )

    async def shutdown(self, client):
        if self._exit_stack:
            await self._exit_stack.aclose()
