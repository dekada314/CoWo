from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class Document:
    id: UUID
    uploaded_by: UUID | None
    doc_name: str
    doc_type: str
    is_deleted: bool = False
    versions: list["DocumentVersion"] = field(default_factory=list)

    def soft_delete(self) -> None:
        if self.is_deleted:
            raise ValueError("Document already deleted")
        self.is_deleted = True

    def restore(self) -> None:
        if not self.is_deleted:
            raise ValueError("Document is not deleted")
        self.is_deleted = False

    def add_version(self, version: "DocumentVersion") -> None:
        self.versions.append(version)


@dataclass
class DocumentVersion:
    id: UUID
    document_id: UUID
    version_number: int
    s3_file_key: str
    content_hash: str
    file_size_bytes: int | None = None

    def is_duplicate_of(self, other: "DocumentVersion") -> bool:
        return self.content_hash == other.content_hash
