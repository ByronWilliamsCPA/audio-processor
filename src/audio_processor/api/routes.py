"""API routes for audio processing.

This module defines the REST API endpoints for:
- POST /api/v1/process - Submit audio for processing
- GET /api/v1/status/{job_id} - Check job status
- GET /api/v1/results/{job_id} - Get job results
- GET /api/v1/artifacts/{job_id}/{artifact_name} - Download artifacts
"""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import anyio
import anyio.to_thread
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response

from audio_processor.api.security import rate_limit, require_api_key
from audio_processor.core.config import settings
from audio_processor.core.exceptions import ValidationError
from audio_processor.core.job_store import InMemoryJobStore, JobStore
from audio_processor.core.models import (
    AudioJobInput,
    AudioJobProgress,
    JobStatus,
    JobStatusResponse,
    ProcessAudioResponse,
)
from audio_processor.services.audio_converter import AudioConverter
from audio_processor.utils.logging import get_logger

logger = get_logger(__name__)

PLAIN_TEXT_CONTENT_TYPE = "text/plain; charset=utf-8"

# Create router with prefix. API-key authentication is enforced on every
# /api/v1 route (a no-op unless auth_required is enabled).
router = APIRouter(
    prefix="/api/v1",
    tags=["Audio Processing"],
    dependencies=[Depends(require_api_key)],
)

# Process-local fallback store. In production, a RedisJobStore is attached to
# ``app.state.job_store`` at startup (see api/__init__.py) so the API and the
# ARQ worker share job state. The in-memory store is used for development and
# tests, and is the single source of truth when no store is attached.
_default_store = InMemoryJobStore()


def _get_job_store() -> InMemoryJobStore:  # pyright: ignore[reportUnusedFunction]
    """Return the process-local in-memory job store.

    Exposed as a test seam for direct record injection/inspection; not called
    within this module (request handlers use :func:`get_job_store`).

    Returns:
        The module-level in-memory job store.
    """
    return _default_store


def get_job_store(request: Request) -> JobStore:
    """Resolve the job store for a request.

    Prefers a store attached to ``app.state`` (e.g. a Redis-backed store wired
    at startup); otherwise falls back to the process-local in-memory store.

    Args:
        request: The incoming request.

    Returns:
        The active job store.
    """
    store = getattr(request.app.state, "job_store", None)
    if isinstance(store, JobStore):
        return store
    return _default_store


def _parse_iso(value: object) -> datetime | None:
    """Best-effort parse of a stored timestamp.

    Args:
        value: A datetime, an ISO-8601 string, or anything else.

    Returns:
        The parsed datetime, or ``None`` if absent/unparseable.
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


async def _maybe_enqueue(
    request: Request,
    job_id: str,
    record: dict[str, object],
) -> None:
    """Enqueue a job to the ARQ worker when enqueueing is enabled.

    No-op when ``enqueue_enabled`` is false or no ARQ pool is attached to the
    application (e.g. in-memory/dev deployments), leaving the job queued in the
    store for later processing.

    Args:
        request: The incoming request (source of the ARQ pool on app state).
        job_id: Unique job identifier.
        record: The job record to hand to the worker (carries the ``input``).
    """
    if not settings.enqueue_enabled:
        return
    pool = getattr(request.app.state, "arq_pool", None)
    if pool is None:
        # Enqueueing is enabled but no pool is configured: the job would be
        # stranded QUEUED forever. Fail loudly rather than silently accept it.
        logger.error("enqueue_pool_missing", job_id=job_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Job enqueueing is enabled but no worker pool is configured",
        )
    # Imported lazily so the API does not hard-depend on the 'jobs' (arq) extra
    # unless enqueueing is actually used.
    from audio_processor.jobs.worker import enqueue_task  # noqa: PLC0415

    await enqueue_task(pool, "process_audio_job", job_id, record)


# Upload streaming chunk size (1 MiB).
UPLOAD_CHUNK_SIZE = 1024 * 1024


async def _stream_upload_to_temp(
    file: UploadFile,
    temp_path: Path,
    max_bytes: int,
) -> int:
    """Stream an upload to disk in bounded chunks, enforcing a hard size cap.

    Avoids buffering the entire body in memory and does not trust the
    client-supplied ``Content-Length``: the cap is enforced on bytes actually
    read.

    Args:
        file: The incoming upload.
        temp_path: Destination path (already created).
        max_bytes: Maximum permitted size in bytes.

    Returns:
        Number of bytes written.

    Raises:
        HTTPException: 413 if the stream exceeds ``max_bytes``.
    """
    bytes_written = 0
    async with await anyio.open_file(temp_path, "wb") as out:
        while chunk := await file.read(UPLOAD_CHUNK_SIZE):
            bytes_written += len(chunk)
            if bytes_written > max_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=(
                        "File too large. Maximum size is "
                        f"{settings.audio_max_file_size_mb} MB"
                    ),
                )
            await out.write(chunk)
    return bytes_written


@router.post(
    "/process",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit audio for processing",
    description="Upload an audio or video file for transcription processing.",
    dependencies=[Depends(rate_limit)],
)
async def process_audio(
    request: Request,
    file: Annotated[UploadFile, File(description="Audio or video file to process")],
    enable_diarization: Annotated[
        bool,
        Form(description="Enable speaker diarization"),
    ] = True,
    enable_summarization: Annotated[
        bool,
        Form(description="Enable AI summarization"),
    ] = True,
    language: Annotated[
        str,
        Form(description="Language code (e.g., 'en', 'es')"),
    ] = "en",
    callback_url: Annotated[
        str | None,
        Form(description="Webhook URL for completion notification"),
    ] = None,
) -> ProcessAudioResponse:
    """Submit an audio file for transcription processing.

    The file is validated and queued for asynchronous processing.
    Returns a job ID that can be used to check status and retrieve results.

    Args:
        request: FastAPI request object.
        file: Uploaded audio or video file.
        enable_diarization: Whether to identify speakers.
        enable_summarization: Whether to generate a summary.
        language: Language code for transcription.
        callback_url: Optional webhook URL for completion notification.

    Returns:
        ProcessAudioResponse with job_id and status URL.

    Raises:
        HTTPException: If validation fails or file is too large.
    """
    # Validate file
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )

    # Check file size (read content length from headers if available)
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            size = int(content_length)
        except ValueError:
            size = 0
        if size > settings.max_file_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size is {settings.audio_max_file_size_mb} MB",
            )

    # Generate job ID
    job_id = str(uuid.uuid4())

    logger.info(
        "audio_upload_received",
        job_id=job_id,
        filename=file.filename,
        content_type=file.content_type,
        enable_diarization=enable_diarization,
        enable_summarization=enable_summarization,
    )

    temp_path: Path | None = None
    success = False
    try:
        # Save file to temp directory
        temp_dir = Path(settings.audio_temp_dir)
        await anyio.Path(temp_dir).mkdir(parents=True, exist_ok=True)

        # Create temp file with original extension using mkstemp to avoid
        # blocking the event loop (sync NamedTemporaryFile is not async-safe).
        suffix = Path(file.filename).suffix or ".wav"
        fd, temp_name = await anyio.to_thread.run_sync(
            lambda: tempfile.mkstemp(suffix=suffix, dir=temp_dir)
        )
        os.close(fd)
        temp_path = Path(temp_name)

        # Stream the upload to disk with a hard size cap (do not buffer the
        # entire body in memory or trust the client Content-Length header).
        file_size_bytes = await _stream_upload_to_temp(
            file, temp_path, settings.max_file_size_bytes
        )

        # Validate audio file
        converter = AudioConverter()
        try:
            audio_info = converter.validate_file(temp_path)
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

        # Create job input
        job_input = AudioJobInput(
            file_path=str(temp_path),
            original_filename=file.filename,
            file_size_bytes=file_size_bytes,
            content_type=file.content_type or "application/octet-stream",
            enable_diarization=enable_diarization,
            enable_summarization=enable_summarization,
            language=language,
            callback_url=callback_url,
        )

        # Persist the job record to the shared store (single source of truth
        # for both the API and the worker).
        record: dict[str, object] = {
            "id": job_id,
            "status": JobStatus.QUEUED.value,
            "input": job_input.model_dump(),
            "progress": None,
            "result": None,
            "error": None,
            "created_at": datetime.now(UTC).isoformat(),
            "completed_at": None,
            "audio_info": {
                "duration_seconds": audio_info.duration_seconds,
                "sample_rate": audio_info.sample_rate,
                "channels": audio_info.channels,
                "codec": audio_info.codec,
                "is_video": audio_info.is_video,
            },
        }
        store = get_job_store(request)
        await store.create(job_id, record)

        # Enqueue to the ARQ worker when enabled. Requires a Redis-backed store
        # and an ARQ pool attached at startup so the worker observes the record.
        try:
            await _maybe_enqueue(request, job_id, record)
        except Exception:
            # Mark the orphaned record FAILED, then surface the error.
            await store.update(
                job_id,
                status=JobStatus.FAILED.value,
                error="Failed to enqueue job for processing",
            )
            raise

        logger.info(
            "audio_job_queued",
            job_id=job_id,
            duration_seconds=audio_info.duration_seconds,
            is_video=audio_info.is_video,
            enqueued=settings.enqueue_enabled,
        )

        # Build status URL
        base_url = str(request.base_url).rstrip("/")
        status_url = f"{base_url}/api/v1/status/{job_id}"

        response = ProcessAudioResponse(
            job_id=uuid.UUID(job_id),
            status=JobStatus.QUEUED,
            status_url=status_url,
            message=f"Audio file queued for processing. Duration: {audio_info.duration_seconds:.1f}s",
        )
        success = True
        return response  # noqa: TRY300

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("audio_upload_failed", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process audio upload",
        ) from e
    finally:
        # On any failure path the upload is orphaned: remove it. On success the
        # worker takes ownership of the temp file and deletes it when done.
        if temp_path is not None and not success:
            await anyio.Path(temp_path).unlink(missing_ok=True)


@router.get(
    "/status/{job_id}",
    summary="Check job status",
    description="Get the current status of an audio processing job.",
)
async def get_job_status(
    request: Request,
    job_id: str,
) -> JobStatusResponse:
    """Get the status of an audio processing job.

    Args:
        request: FastAPI request object.
        job_id: Unique job identifier.

    Returns:
        JobStatusResponse with current status and progress.

    Raises:
        HTTPException: If job is not found.
    """
    store = get_job_store(request)
    job = await store.get(job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    # Build result URL if completed
    result_url: str | None = None
    if job["status"] == JobStatus.COMPLETED.value:
        base_url = str(request.base_url).rstrip("/")
        result_url = f"{base_url}/api/v1/results/{job_id}"

    # Parse progress if available
    progress: AudioJobProgress | None = None
    if job.get("progress"):
        progress_data = job["progress"]
        if isinstance(progress_data, dict):
            progress = AudioJobProgress(
                stage=str(progress_data.get("stage", "unknown")),
                percent_complete=int(progress_data.get("percent_complete", 0)),
                message=str(progress_data.get("message", "")),
                started_at=progress_data.get("started_at"),  # type: ignore[arg-type]
                updated_at=datetime.now(UTC),
            )

    # Parse dates defensively: a corrupt/legacy timestamp must not 500 a status
    # check (created_at falls back to now; completed_at falls back to None).
    created_at = _parse_iso(job.get("created_at")) or datetime.now(UTC)
    completed_at = _parse_iso(job.get("completed_at"))

    return JobStatusResponse(
        job_id=uuid.UUID(job_id),
        status=JobStatus(str(job["status"])),
        progress=progress,
        result_url=result_url,
        error=str(job["error"]) if job.get("error") else None,
        created_at=created_at,
        completed_at=completed_at,
    )


@router.get(
    "/results/{job_id}",
    summary="Get job results",
    description="Get the complete results of a finished audio processing job.",
)
async def get_job_results(
    request: Request,
    job_id: str,
) -> dict[str, object]:
    """Get the complete results of a finished job.

    Args:
        request: FastAPI request object.
        job_id: Unique job identifier.

    Returns:
        Dictionary with transcription results and artifact URLs.

    Raises:
        HTTPException: If job not found or not completed.
    """
    store = get_job_store(request)
    job = await store.get(job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    if job["status"] != JobStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job not completed. Current status: {job['status']}",
        )

    result = job.get("result")
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Results not available",
        )

    # Build artifact URLs
    base_url = str(request.base_url).rstrip("/")
    artifact_base = f"{base_url}/api/v1/artifacts/{job_id}"

    # Available artifact formats
    artifacts = {
        "docling_dom": f"{artifact_base}/docling_dom.json",
        "transcript_txt": f"{artifact_base}/transcript.txt",
        "transcript_simple": f"{artifact_base}/transcript_simple.txt",
        "transcript_srt": f"{artifact_base}/transcript.srt",
        "transcript_vtt": f"{artifact_base}/transcript.vtt",
    }

    # Extract transcription metadata from result
    transcription_meta = {}
    if isinstance(result, dict):
        transcription_meta = {
            "language": result.get("language", "en"),
            "word_count": result.get("word_count", 0),
            "speaker_count": result.get("speaker_count", 0),
            "duration_ms": result.get("duration_ms", 0),
        }

    return {
        "job_id": job_id,
        "status": job["status"],
        "processing": {
            "created_at": job.get("created_at"),
            "completed_at": job.get("completed_at"),
        },
        "transcription": transcription_meta,
        "quality": job.get("quality"),
        "artifacts": artifacts,
        "result": result,
    }


# Supported artifact formats with their content types
ARTIFACT_CONTENT_TYPES: dict[str, str] = {
    "docling_dom.json": "application/json",
    "transcript.txt": PLAIN_TEXT_CONTENT_TYPE,
    "transcript_simple.txt": PLAIN_TEXT_CONTENT_TYPE,
    "transcript.srt": PLAIN_TEXT_CONTENT_TYPE,
    "transcript.vtt": "text/vtt; charset=utf-8",
}


@router.get(
    "/artifacts/{job_id}/{artifact_name}",
    summary="Download artifact",
    description="Download a specific artifact from a completed job.",
)
async def get_artifact(
    request: Request,
    job_id: str,
    artifact_name: str,
) -> Response:
    """Download a specific artifact from a completed job.

    Available artifacts:
    - docling_dom.json: Docling DOM document format
    - transcript.txt: Plain text with timestamps and speakers
    - transcript_simple.txt: Plain text without timestamps
    - transcript.srt: SRT subtitle format
    - transcript.vtt: WebVTT subtitle format

    Args:
        request: FastAPI request object.
        job_id: Unique job identifier.
        artifact_name: Name of the artifact to download.

    Returns:
        Response with the artifact content.

    Raises:
        HTTPException: If job not found, not completed, or artifact unavailable.
    """
    store = get_job_store(request)
    job = await store.get(job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    if job["status"] != JobStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job not completed. Current status: {job['status']}",
        )

    # Check if artifact name is valid
    if artifact_name not in ARTIFACT_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown artifact: {artifact_name}. Available: {list(ARTIFACT_CONTENT_TYPES.keys())}",
        )

    # Get artifacts from job (generated during processing)
    artifacts = job.get("artifacts")
    if not artifacts or not isinstance(artifacts, dict):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifacts not available for this job",
        )

    if artifact_name not in artifacts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{artifact_name}' not found",
        )

    content = artifacts[artifact_name]
    content_type = ARTIFACT_CONTENT_TYPES[artifact_name]

    logger.info(
        "artifact_downloaded",
        job_id=job_id,
        artifact_name=artifact_name,
        content_length=len(content),
    )

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact_name}"',
        },
    )
