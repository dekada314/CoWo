from dataclasses import dataclass
from typing import AsyncIterator, Protocol


@dataclass(frozen=True)
class StoredFile:
    key: str
    bucket: str
    size: int
    content_type: str


@dataclass(frozen=True)
class FileMetadata:
    key: str
    size: int
    content_type: str
    etag: str


class FileStorage(Protocol):
    async def upload(
        self,
        data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        prefix: str = "",
    ) -> StoredFile: ...

    async def download(self, key: str) -> bytes: ...

    async def stream(
        self, key: str, chunk_size: int = 64 * 1024
    ) -> AsyncIterator[bytes]: ...

    async def delete(self, key: str) -> None: ...

    async def exists(self, key: str) -> bool: ...

    async def get_metadata(self, key: str) -> FileMetadata: ...

    async def list_files(self, prefix: str = "") -> list[FileMetadata]: ...

    async def get_presigned_url(
        self, key: str, expires_in: int = 3600
    ) -> str: ...

    async def copy(self, source_key: str, destination_key: str) -> None: ...
