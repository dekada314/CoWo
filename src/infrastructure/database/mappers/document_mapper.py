from src.domain.entities.document import Document, DocumentVersion
from src.infrastructure.database.models.document import DocumentORM
from src.infrastructure.database.models.document_version import (
    DocumentVersionORM,
)


class DocumentMapper:
    @staticmethod
    def to_domain(orm: DocumentORM) -> Document:
        return Document(
            id=orm.id,
            uploaded_by=orm.uploaded_by,
            doc_name=orm.doc_name,
            doc_type=orm.doc_type,
            is_deleted=orm.is_deleted,
            versions=[
                DocumentMapper.version_to_domain(v) for v in orm.versions
            ],
        )

    @staticmethod
    def to_orm(document: Document) -> DocumentORM:
        return DocumentORM(
            id=document.id,
            uploaded_by=document.uploaded_by,
            doc_name=document.doc_name,
            doc_type=document.doc_type,
            is_deleted=document.is_deleted,
        )

    @staticmethod
    def update_orm(orm: DocumentORM, document: Document) -> None:
        orm.doc_name = document.doc_name
        orm.doc_type = document.doc_type
        orm.is_deleted = document.is_deleted

    @staticmethod
    def version_to_domain(orm: DocumentVersionORM) -> DocumentVersion:
        return DocumentVersion(
            id=orm.id,
            document_id=orm.document_id,
            version_number=orm.version_number,
            s3_file_key=orm.s3_file_key,
            content_hash=orm.content_hash,
            file_size_bytes=orm.file_size_bytes,
        )

    @staticmethod
    def version_to_orm(version: DocumentVersion) -> DocumentVersionORM:
        return DocumentVersionORM(
            id=version.id,
            document_id=version.document_id,
            version_number=version.version_number,
            s3_file_key=version.s3_file_key,
            content_hash=version.content_hash,
            file_size_bytes=version.file_size_bytes,
        )
