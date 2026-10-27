from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


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


class FileStorage(ABC):
    @abstractmethod
    async def upload(
        self,
        data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        prefix: str = "",
    ) -> StoredFile: ...
    @abstractmethod
    async def download(self, key: str) -> bytes: ...
    @abstractmethod
    async def stream(
        self, key: str, chunk_size: int = 64 * 1024
    ) -> AsyncIterator[bytes]: ...
    @abstractmethod
    async def delete(self, key: str) -> None: ...
    @abstractmethod
    async def exists(self, key: str) -> bool: ...
    @abstractmethod
    async def get_metadata(self, key: str) -> FileMetadata: ...
    @abstractmethod
    async def list_files(self, prefix: str = "") -> list[FileMetadata]: ...
    @abstractmethod
    async def get_presigned_url(
        self, key: str, expires_in: int = 3600
    ) -> str: ...
    @abstractmethod
    async def copy(self, source_key: str, destination_key: str) -> None: ...
