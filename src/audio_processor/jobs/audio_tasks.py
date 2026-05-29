"""Audio processing background tasks.

This module defines the ARQ tasks for processing audio files:
- Audio conversion/extraction
- Quality assessment
- Transcription via Deepgram
- Result storage
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import anyio

from audio_processor.core.exceptions import (
    AudioProcessorError,
    ConfigurationError,
    TranscriptionError,
    ValidationError,
)
from audio_processor.core.job_store import RedisJobStore
from audio_processor.core.models import JobStatus
from audio_processor.services.audio_converter import AudioConverter
from audio_processor.services.quality_assessor import QualityAssessor
from audio_processor.utils.logging import get_logger

if TYPE_CHECKING:
    from arq.connections import ArqRedis

    from audio_processor.core.models import TranscriptionResult

logger = get_logger(__name__)

# Type alias for ARQ job context
JobContext = dict[str, object]


def _progress(
    stage: str,
    percent: int,
    message: str,
    *,
    started: bool = False,
) -> dict[str, object]:
    """Build a job progress payload with a current timestamp.

    Args:
        stage: Machine-readable pipeline stage name.
        percent: Percent complete (0-100).
        message: Human-readable status message.
        started: Whether to include a ``started_at`` timestamp (first stage).

    Returns:
        Progress dictionary suitable for the job store.
    """
    now = datetime.now(UTC).isoformat()
    payload: dict[str, object] = {
        "stage": stage,
        "percent_complete": percent,
        "message": message,
        "updated_at": now,
    }
    if started:
        payload["started_at"] = now
    return payload


def _convert_audio(converter: AudioConverter, file_path: Path, job_id: str) -> Path:
    """Convert or extract the input into an ASR-ready audio file.

    Args:
        converter: The audio converter service.
        file_path: Path to the input media file.
        job_id: Job identifier (for logging).

    Returns:
        Path to the converted audio file.
    """
    if converter.is_video(file_path):
        logger.info(
            "extracting_audio_from_video", job_id=job_id, file_path=str(file_path)
        )
        return converter.extract_audio(file_path)
    return converter.convert_for_asr(file_path)


def _transcribe(
    converted_path: Path,
    input_data: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    job_id: str,
) -> TranscriptionResult | None:
    """Transcribe audio via Deepgram, tolerating a missing API key.

    Args:
        converted_path: Path to the ASR-ready audio file.
        input_data: Job input options (diarization/summarization/language).
        job_id: Job identifier (for logging).

    Returns:
        The transcription result, or ``None`` if Deepgram is not configured.
    """
    # Imported lazily to avoid importing the optional 'audio' extra at module
    # load and to surface a missing API key as a catchable ConfigurationError.
    from audio_processor.services.deepgram_client import (  # noqa: PLC0415
        DeepgramTranscriptionClient,
    )

    try:
        client = DeepgramTranscriptionClient()
        return client.transcribe(
            converted_path,
            enable_diarization=input_data.get("enable_diarization", True),
            enable_summarization=input_data.get("enable_summarization", True),
            language=input_data.get("language", "en"),
        )
    except ConfigurationError as e:
        logger.warning("deepgram_not_configured", job_id=job_id, error=str(e))
        return None


def _build_transcription_payload(result: TranscriptionResult) -> dict[str, object]:
    """Serialize a transcription result into the job result payload.

    Args:
        result: The transcription result.

    Returns:
        JSON-serializable transcription summary.
    """
    return {
        "transcript": result.transcript,
        "summary": result.summary,
        "speaker_count": len(result.speakers),
        "word_count": result.metadata.word_count,
        "duration_ms": int(result.metadata.duration_seconds * 1000),
        "duration_seconds": result.metadata.duration_seconds,
        "confidence_mean": result.metadata.confidence_mean,
        "cost_usd": str(result.metadata.cost_usd),
        "language": result.metadata.language,
        "speakers": [s.model_dump() for s in result.speakers],
        "utterances": [u.model_dump() for u in result.utterances],
    }


def _generate_artifacts(result: TranscriptionResult, job_id: str) -> dict[str, str]:
    """Generate transcript artifacts, tolerating generation failures.

    Args:
        result: The transcription result.
        job_id: Job identifier (for logging).

    Returns:
        Mapping of artifact name to content; empty if generation failed.
    """
    from audio_processor.services.transcript_formatter import (  # noqa: PLC0415
        ArtifactGenerator,
    )

    try:
        artifacts = ArtifactGenerator().generate_all(result)
    except (ValidationError, AudioProcessorError) as e:
        # Transcription still succeeded; continue without artifacts.
        logger.warning("artifact_generation_failed", job_id=job_id, error=str(e))
        return {}
    logger.info("artifacts_generated", job_id=job_id, artifact_count=len(artifacts))
    return artifacts


async def process_audio_job(
    ctx: JobContext,
    job_id: str,
    job_data: dict[str, Any],  # pyright: ignore[reportExplicitAny]
) -> dict[str, object]:
    """Process an audio file through the transcription pipeline.

    This is the main ARQ task that converts/extracts audio, assesses quality,
    transcribes via Deepgram, generates artifacts, and stores results. Each
    stage is delegated to a focused helper; this function orchestrates them and
    reports progress.

    Args:
        ctx: ARQ context with Redis connection.
        job_id: Unique job identifier.
        job_data: Job input data including file path and options.

    Returns:
        Dictionary with processing results.

    Raises:
        ValidationError: If the input file path is missing or unreadable.
        AudioProcessorError: If processing fails.
    """
    redis: ArqRedis = ctx["redis"]  # pyright: ignore[reportAssignmentType]

    logger.info("audio_job_started", job_id=job_id)
    await _update_job_status(
        redis,
        job_id,
        status=JobStatus.PREPROCESSING,
        progress=_progress(
            "preprocessing", 0, "Starting audio preprocessing...", started=True
        ),
    )

    try:
        input_data = job_data.get("input", {})
        file_path = Path(str(input_data.get("file_path", "")))

        if not await anyio.Path(file_path).exists():
            msg = f"Audio file not found: {file_path}"
            raise ValidationError(msg, field="file_path", value=str(file_path))  # noqa: TRY301

        converter = AudioConverter()
        assessor = QualityAssessor()

        # Step 1: Convert/extract audio.
        await _update_job_status(
            redis,
            job_id,
            progress=_progress("converting", 10, "Converting audio format..."),
        )
        converted_path = _convert_audio(converter, file_path, job_id)

        # Step 2: Assess audio quality.
        await _update_job_status(
            redis,
            job_id,
            progress=_progress("quality_assessment", 30, "Assessing audio quality..."),
        )
        quality_metrics = assessor.assess(converted_path)
        logger.info(
            "audio_quality_assessed",
            job_id=job_id,
            quality_level=quality_metrics.quality_level.value,
            snr_db=quality_metrics.snr_db,
        )

        # Step 3: Transcribe.
        await _update_job_status(
            redis,
            job_id,
            status=JobStatus.TRANSCRIBING,
            progress=_progress(
                "transcribing", 50, "Transcribing audio with Deepgram..."
            ),
        )
        transcription_result = _transcribe(converted_path, input_data, job_id)

        # Step 4: Post-process and clean up the converted temp file.
        await _update_job_status(
            redis,
            job_id,
            status=JobStatus.POSTPROCESSING,
            progress=_progress("postprocessing", 85, "Generating output artifacts..."),
        )
        if converted_path != file_path:
            converted_path.unlink(missing_ok=True)

        result: dict[str, object] = {
            "job_id": job_id,
            "status": "completed",
            "quality": quality_metrics.model_dump(),
        }

        artifacts: dict[str, str] = {}
        if transcription_result is not None:
            result["transcription"] = _build_transcription_payload(transcription_result)
            await _update_job_status(
                redis,
                job_id,
                progress=_progress(
                    "generating_artifacts", 95, "Generating transcript formats..."
                ),
            )
            artifacts = _generate_artifacts(transcription_result, job_id)
        else:
            result["transcription"] = None
            result["warning"] = (
                "Transcription skipped - Deepgram API key not configured"
            )

        await _update_job_status(
            redis,
            job_id,
            status=JobStatus.COMPLETED,
            progress=_progress("completed", 100, "Processing complete"),
            result=result,
            artifacts=artifacts,
            completed_at=datetime.now(UTC).isoformat(),
        )
        logger.info(
            "audio_job_completed",
            job_id=job_id,
            duration_seconds=quality_metrics.duration_seconds,
            has_transcription=transcription_result is not None,
        )
        return result  # noqa: TRY300

    except (ValidationError, AudioProcessorError, TranscriptionError) as e:
        logger.exception("audio_job_failed", job_id=job_id, error=str(e))
        await _update_job_status(
            redis,
            job_id,
            status=JobStatus.FAILED,
            error=str(e),
            completed_at=datetime.now(UTC).isoformat(),
        )
        raise

    except Exception as e:
        logger.exception("audio_job_unexpected_error", job_id=job_id, error=str(e))
        await _update_job_status(
            redis,
            job_id,
            status=JobStatus.FAILED,
            error=f"Unexpected error: {e}",
            completed_at=datetime.now(UTC).isoformat(),
        )
        msg = f"Processing failed: {e}"
        raise AudioProcessorError(msg) from e


async def _update_job_status(
    redis: ArqRedis,
    job_id: str,
    *,
    status: JobStatus | None = None,
    progress: dict[str, object] | None = None,
    result: dict[str, object] | None = None,
    artifacts: dict[str, str] | None = None,
    error: str | None = None,
    completed_at: str | None = None,
) -> None:
    """Update job status in Redis.

    Args:
        redis: ARQ Redis connection.
        job_id: Job identifier.
        status: New job status.
        progress: Progress update.
        result: Job result (when completed).
        artifacts: Generated artifacts (when completed).
        error: Error message (when failed).
        completed_at: Completion timestamp.
    """
    # Delegate to the shared RedisJobStore so the worker and the API use the
    # same key scheme and serialization (single source of truth for job state).
    store = RedisJobStore(redis)
    await store.update(
        job_id,
        status=status.value if status else None,
        progress=progress,
        result=result,
        artifacts=artifacts,
        error=error,
        completed_at=completed_at,
    )
