from dataclasses import dataclass
from typing import AsyncIterator
from uuid import uuid4

from src.core.settings import MinioSettings

from application.interfaces.storages.file_storage import (
    FileMetadata,
    StoredFile,
)


class MinioFileStorage:
    def __init__(self, client, config: MinioSettings) -> None:
        self._client = client
        self._config = config
        self._bucket = config.bucket

    async def upload(
        self,
        data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        prefix: str = "",
    ) -> StoredFile:
        key = self._build_key(filename, prefix)
        await self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return StoredFile(
            key=key,
            bucket=self._bucket,
            size=len(data),
            content_type=content_type,
        )

    async def download(self, key: str) -> bytes:
        response = await self._client.get_object(Bucket=self._bucket, Key=key)
        async with response["Body"] as stream:
            return await stream.read()

    async def stream(
        self,
        key: str,
        chunk_size: int = 64 * 1024,
    ) -> AsyncIterator[bytes]:
        response = await self._client.get_object(Bucket=self._bucket, Key=key)
        async with response["Body"] as stream:
            while True:
                chunk = await stream.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    async def delete(self, key: str) -> None:
        await self._client.delete_object(Bucket=self._bucket, Key=key)

    async def exists(self, key: str) -> bool:
        try:
            await self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except self._client.exceptions.ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in (
                "404",
                "NoSuchKey",
            ):
                return False
            raise

    async def get_metadata(self, key: str) -> FileMetadata:
        response = await self._client.head_object(Bucket=self._bucket, Key=key)
        return FileMetadata(
            key=key,
            size=response["ContentLength"],
            content_type=response.get(
                "ContentType", "application/octet-stream"
            ),
            etag=response.get("ETag", "").strip('"'),
        )

    async def list_files(self, prefix: str = "") -> list[FileMetadata]:
        result: list[FileMetadata] = []
        paginator = self._client.get_paginator("list_objects_v2")
        async for page in paginator.paginate(
            Bucket=self._bucket, Prefix=prefix
        ):
            for obj in page.get("Contents", []):
                result.append(
                    FileMetadata(
                        key=obj["Key"],
                        size=obj["Size"],
                        content_type="",
                        etag=obj.get("ETag", "").strip('"'),
                    )
                )
        return result

    async def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        return await self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    async def copy(self, source_key: str, destination_key: str) -> None:
        await self._client.copy_object(
            Bucket=self._bucket,
            CopySource={"Bucket": self._bucket, "Key": source_key},
            Key=destination_key,
        )

    @staticmethod
    def _build_key(filename: str, prefix: str) -> str:
        normalized = filename.replace(" ", "_")
        key = f"{uuid4()}_{normalized}"
        return f"{prefix}/{key}" if prefix else key
