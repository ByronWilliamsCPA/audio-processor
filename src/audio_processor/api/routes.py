"""API routes for audio processing.

This module defines the REST API endpoints for:
- POST /api/v1/process - Submit audio for processing
- GET /api/v1/status/{job_id} - Check job status
- GET /api/v1/results/{job_id} - Get job results
- GET /api/v1/artifacts/{job_id}/{artifact_name} - Download artifacts
"""

from __future__ import annotations

import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response

from audio_processor.core.config import settings
from audio_processor.core.exceptions import ValidationError
from audio_processor.core.models import (
    AudioJobInput,
    AudioJobProgress,
    JobStatus,
    JobStatusResponse,
    ProcessAudioResponse,
)
from audio_processor.services.audio_converter import AudioConverter
from audio_processor.utils.logging import get_logger

# Python 3.10 compatibility: UTC was added in 3.11
if sys.version_info >= (3, 11):  # noqa: UP036
    from datetime import UTC
else:
    UTC = timezone.utc  # noqa: UP017

logger = get_logger(__name__)

# Create router with prefix
router = APIRouter(prefix="/api/v1", tags=["Audio Processing"])

# In-memory job store (replace with Redis in production)
# This is a simple dict for development; production uses Redis
_jobs: dict[str, dict[str, object]] = {}


def _get_job_store() -> dict[str, dict[str, object]]:
    """Get the job store.

    Returns:
        Dictionary of jobs keyed by job_id.
    """
    return _jobs


@router.post(
    "/process",
    response_model=ProcessAudioResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit audio for processing",
    description="Upload an audio or video file for transcription processing.",
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
    if content_length and int(content_length) > settings.max_file_size_bytes:
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

    try:
        # Save file to temp directory
        temp_dir = Path(settings.audio_temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Create temp file with original extension
        suffix = Path(file.filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            dir=temp_dir,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)

            # Write file content
            content = await file.read()
            temp_file.write(content)

        # Validate audio file
        converter = AudioConverter()
        try:
            audio_info = converter.validate_file(temp_path)
        except ValidationError as e:
            # Clean up temp file
            temp_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

        # Create job input
        job_input = AudioJobInput(
            file_path=str(temp_path),
            original_filename=file.filename,
            file_size_bytes=len(content),
            content_type=file.content_type or "application/octet-stream",
            enable_diarization=enable_diarization,
            enable_summarization=enable_summarization,
            language=language,
            callback_url=callback_url,
        )

        # Store job in memory (will be replaced with Redis queue)
        jobs = _get_job_store()
        jobs[job_id] = {
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

        # TODO: Enqueue job to ARQ worker
        # This will be implemented when we connect to Redis
        logger.info(
            "audio_job_queued",
            job_id=job_id,
            duration_seconds=audio_info.duration_seconds,
            is_video=audio_info.is_video,
        )

        # Build status URL
        base_url = str(request.base_url).rstrip("/")
        status_url = f"{base_url}/api/v1/status/{job_id}"

        return ProcessAudioResponse(
            job_id=uuid.UUID(job_id),
            status=JobStatus.QUEUED,
            status_url=status_url,
            message=f"Audio file queued for processing. Duration: {audio_info.duration_seconds:.1f}s",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("audio_upload_failed", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process audio upload",
        ) from e


@router.get(
    "/status/{job_id}",
    response_model=JobStatusResponse,
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
    jobs = _get_job_store()

    if job_id not in jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    job = jobs[job_id]

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

    # Parse dates
    created_at = job.get("created_at")
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at)
    elif not isinstance(created_at, datetime):
        created_at = datetime.now(UTC)

    completed_at = job.get("completed_at")
    if isinstance(completed_at, str):
        completed_at = datetime.fromisoformat(completed_at)
    elif completed_at is not None and not isinstance(completed_at, datetime):
        completed_at = None

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
    jobs = _get_job_store()

    if job_id not in jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    job = jobs[job_id]

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
    "transcript.txt": "text/plain; charset=utf-8",
    "transcript_simple.txt": "text/plain; charset=utf-8",
    "transcript.srt": "text/plain; charset=utf-8",
    "transcript.vtt": "text/vtt; charset=utf-8",
}


@router.get(
    "/artifacts/{job_id}/{artifact_name}",
    summary="Download artifact",
    description="Download a specific artifact from a completed job.",
)
async def get_artifact(
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
        job_id: Unique job identifier.
        artifact_name: Name of the artifact to download.

    Returns:
        Response with the artifact content.

    Raises:
        HTTPException: If job not found, not completed, or artifact unavailable.
    """
    jobs = _get_job_store()

    if job_id not in jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    job = jobs[job_id]

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
