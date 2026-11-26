import hashlib
from pathlib import PurePath
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

import structlog
from dishka.integrations.fastapi import FromDishka, inject
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from src.application.ingestion.contracts import (
    DocumentJobView,
    IngestionError,
    JobView,
    KnowledgeCardView,
)
from src.application.ingestion.deletion import (
    DocumentDeletionService,
    DocumentDeletionUnavailable,
)
from src.application.interfaces.storages.file_storage import FileStorage
from src.core.settings import get_settings
from src.domain.entities.user import User
from src.infrastructure.database.repositories.ingestion_store import IngestionStore
from src.presentation.api.dependencies.auth import require_user

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/ingestion", tags=["ingestion"])


def validate_filename(filename: str) -> str:
    if (
        not filename
        or len(filename) > 255
        or PurePath(filename).name != filename
        or "\\" in filename
        or any(ord(c) < 32 for c in filename)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="invalid_filename",
        )
    extension = PurePath(filename).suffix.lower().lstrip(".")
    if extension not in get_settings().app.allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="unsupported_document_type",
        )
    return filename


def require_model() -> None:
    llm = get_settings().llm
    if not llm.model_analyst.strip() or not llm.model_embedding.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="llm_model_not_configured",
        )


async def submit_document(
    file: UploadFile,
    store: IngestionStore,
    storage: FileStorage,
    user_id: UUID,
) -> JobView:
    filename = validate_filename(file.filename or "")
    limit = get_settings().app.max_upload_size_mb * 1024 * 1024
    if file.size is not None and file.size > limit:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="document_file_limit_exceeded",
        )
    digest = hashlib.sha256()
    size = 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > limit:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="document_file_limit_exceeded",
            )
        digest.update(chunk)
    if size == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="empty_document",
        )
    await file.seek(0)
    stored = await storage.upload_file(
        file.file,
        filename,
        size,
        content_type=file.content_type or "application/octet-stream",
        prefix="originals",
    )
    try:
        job = await store.submit(
            filename,
            stored.key,
            digest.hexdigest(),
            size,
            user_id,
        )
    except Exception as exc:
        logger.exception("ingestion_submission_failed", object_key=stored.key)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ingestion_submission_unavailable",
        ) from exc
    logger.info(
        "ingestion_submitted",
        job_id=str(job.id),
        document_version_id=str(job.document_version_id),
        size_bytes=size,
    )
    return job


@router.post(
    "/documents",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobView,
)
@inject
async def upload_document(
    response: Response,
    store: FromDishka[IngestionStore],
    storage: FromDishka[FileStorage],
    file: Annotated[UploadFile, File()],
    user: Annotated[User, Depends(require_user)],
) -> JobView:
    require_model()
    job = await submit_document(file, store, storage, user.id)
    response.headers["Location"] = f"/api/v1/ingestion/jobs/{job.id}"
    return job


@router.post(
    "/documents/batch",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=list[JobView],
)
@inject
async def upload_documents(
    store: FromDishka[IngestionStore],
    storage: FromDishka[FileStorage],
    files: Annotated[list[UploadFile], File()],
    user: Annotated[User, Depends(require_user)],
) -> list[JobView]:
    require_model()
    if len(files) > get_settings().app.max_batch_files:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="document_batch_limit_exceeded",
        )
    for file in files:
        validate_filename(file.filename or "")
    jobs = []
    for file in files:
        jobs.append(await submit_document(file, store, storage, user.id))
    return jobs


@router.get("/jobs/{job_id}", response_model=JobView)
@inject
async def get_job(
    job_id: UUID,
    store: FromDishka[IngestionStore],
    user: Annotated[User, Depends(require_user)],
) -> JobView:
    job = await store.get(job_id, user.id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found"
        )
    return job


@router.get("/documents", response_model=list[DocumentJobView])
@inject
async def list_documents(
    store: FromDishka[IngestionStore],
    user: Annotated[User, Depends(require_user)],
) -> list[DocumentJobView]:
    return await store.list_documents(user.id)


@router.get("/jobs/{job_id}/card", response_model=KnowledgeCardView)
@inject
async def get_card(
    job_id: UUID,
    store: FromDishka[IngestionStore],
    user: Annotated[User, Depends(require_user)],
) -> KnowledgeCardView:
    card = await store.card(job_id, user.id)
    if card is None:
        if await store.get(job_id, user.id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found"
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="card_not_ready"
        )
    return card


@router.get("/jobs/{job_id}/original")
@inject
async def get_original(
    job_id: UUID,
    store: FromDishka[IngestionStore],
    storage: FromDishka[FileStorage],
    user: Annotated[User, Depends(require_user)],
) -> StreamingResponse:
    original = await store.original(job_id, user.id)
    if original is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found"
        )
    key, filename = original
    return StreamingResponse(
        storage.stream(key),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"
        },
    )


@router.post(
    "/jobs/{job_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobView,
)
@inject
async def retry_job(
    job_id: UUID,
    store: FromDishka[IngestionStore],
    user: Annotated[User, Depends(require_user)],
) -> JobView:
    require_model()
    try:
        job = await store.retry(job_id, user.id)
    except IngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found"
        )
    logger.info(
        "ingestion_retry_scheduled",
        job_id=str(job.id),
        document_version_id=str(job.document_version_id),
    )
    return job


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@inject
async def delete_document(
    job_id: UUID,
    service: FromDishka[DocumentDeletionService],
    user: Annotated[User, Depends(require_user)],
) -> Response:
    try:
        deleted = await service.delete(job_id, user.id)
    except IngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except DocumentDeletionUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="job_not_found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
