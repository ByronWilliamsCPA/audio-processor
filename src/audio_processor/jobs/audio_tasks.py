"""Audio processing background tasks.

This module defines the ARQ tasks for processing audio files:
- Audio conversion/extraction
- Quality assessment
- Transcription via Deepgram
- Result storage
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import anyio

from audio_processor.core.config import settings
from audio_processor.core.exceptions import (
    AudioProcessorError,
    ConfigurationError,
    TranscriptionError,
    ValidationError,
)
from audio_processor.core.models import JobStatus
from audio_processor.services.audio_converter import AudioConverter
from audio_processor.services.quality_assessor import QualityAssessor
from audio_processor.utils.logging import get_logger

if TYPE_CHECKING:
    from arq.connections import ArqRedis

# Python 3.10 compatibility: UTC was added in 3.11
if sys.version_info >= (3, 11):  # noqa: UP036
    from datetime import UTC
else:
    UTC = timezone.utc  # noqa: UP017  # pyright: ignore[reportUnreachable]

logger = get_logger(__name__)

# Type alias for ARQ job context
JobContext = dict[str, object]


async def process_audio_job(
    ctx: JobContext,
    job_id: str,
    job_data: dict[str, Any],  # pyright: ignore[reportExplicitAny]
) -> dict[str, object]:
    """Process an audio file through the transcription pipeline.

    This is the main ARQ task that:
    1. Converts/extracts audio if needed
    2. Assesses audio quality
    3. Transcribes via Deepgram
    4. Stores results

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

    # Update status to preprocessing
    await _update_job_status(
        redis,
        job_id,
        status=JobStatus.PREPROCESSING,
        progress={
            "stage": "preprocessing",
            "percent_complete": 0,
            "message": "Starting audio preprocessing...",
            "started_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )

    try:
        input_data = job_data.get("input", {})
        file_path = Path(str(input_data.get("file_path", "")))

        if not await anyio.Path(file_path).exists():
            msg = f"Audio file not found: {file_path}"
            raise ValidationError(msg, field="file_path", value=str(file_path))  # noqa: TRY301

        # Initialize services
        converter = AudioConverter()
        assessor = QualityAssessor()

        # Step 1: Convert/extract audio if needed
        await _update_job_status(
            redis,
            job_id,
            progress={
                "stage": "converting",
                "percent_complete": 10,
                "message": "Converting audio format...",
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )

        # Check if video and extract audio
        if converter.is_video(file_path):
            logger.info(
                "extracting_audio_from_video", job_id=job_id, file_path=str(file_path)
            )
            converted_path = converter.extract_audio(file_path)
        else:
            # Convert to optimal format for ASR
            converted_path = converter.convert_for_asr(file_path)

        # Step 2: Assess audio quality
        await _update_job_status(
            redis,
            job_id,
            progress={
                "stage": "quality_assessment",
                "percent_complete": 30,
                "message": "Assessing audio quality...",
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )

        quality_metrics = assessor.assess(converted_path)
        logger.info(
            "audio_quality_assessed",
            job_id=job_id,
            quality_level=quality_metrics.quality_level.value,
            snr_db=quality_metrics.snr_db,
        )

        # Step 3: Transcribe with Deepgram
        await _update_job_status(
            redis,
            job_id,
            status=JobStatus.TRANSCRIBING,
            progress={
                "stage": "transcribing",
                "percent_complete": 50,
                "message": "Transcribing audio with Deepgram...",
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )

        # Import here to avoid circular imports and allow for missing API key
        try:
            from audio_processor.services.deepgram_client import (  # noqa: PLC0415
                DeepgramTranscriptionClient,
            )

            transcription_client = DeepgramTranscriptionClient()
            transcription_result = transcription_client.transcribe(
                converted_path,
                enable_diarization=input_data.get("enable_diarization", True),
                enable_summarization=input_data.get("enable_summarization", True),
                language=input_data.get("language", "en"),
            )
        except ConfigurationError as e:
            # Deepgram not configured - log and continue with placeholder
            logger.warning("deepgram_not_configured", job_id=job_id, error=str(e))
            transcription_result = None

        # Step 4: Post-processing
        await _update_job_status(
            redis,
            job_id,
            status=JobStatus.POSTPROCESSING,
            progress={
                "stage": "postprocessing",
                "percent_complete": 85,
                "message": "Generating output artifacts...",
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )

        # Clean up temporary files
        if converted_path != file_path:
            converted_path.unlink(missing_ok=True)

        # Build result
        result: dict[str, object] = {
            "job_id": job_id,
            "status": "completed",
            "quality": quality_metrics.model_dump(),
        }

        # Generate artifacts if transcription was successful
        artifacts: dict[str, str] = {}
        if transcription_result:
            result["transcription"] = {
                "transcript": transcription_result.transcript,
                "summary": transcription_result.summary,
                "speaker_count": len(transcription_result.speakers),
                "word_count": transcription_result.metadata.word_count,
                "duration_ms": int(
                    transcription_result.metadata.duration_seconds * 1000
                ),
                "duration_seconds": transcription_result.metadata.duration_seconds,
                "confidence_mean": transcription_result.metadata.confidence_mean,
                "cost_usd": str(transcription_result.metadata.cost_usd),
                "language": transcription_result.metadata.language,
                "speakers": [s.model_dump() for s in transcription_result.speakers],
                "utterances": [u.model_dump() for u in transcription_result.utterances],
            }

            # Generate all artifact formats
            await _update_job_status(
                redis,
                job_id,
                progress={
                    "stage": "generating_artifacts",
                    "percent_complete": 95,
                    "message": "Generating transcript formats...",
                    "updated_at": datetime.now(UTC).isoformat(),
                },
            )

            try:
                from audio_processor.services.transcript_formatter import (  # noqa: PLC0415
                    ArtifactGenerator,
                )

                generator = ArtifactGenerator()
                artifacts = generator.generate_all(transcription_result)
                logger.info(
                    "artifacts_generated",
                    job_id=job_id,
                    artifact_count=len(artifacts),
                )
            except (ValidationError, AudioProcessorError) as e:
                logger.warning(
                    "artifact_generation_failed",
                    job_id=job_id,
                    error=str(e),
                )
                # Continue without artifacts - transcription still succeeded
        else:
            result["transcription"] = None
            result["warning"] = (
                "Transcription skipped - Deepgram API key not configured"
            )

        # Update final status
        await _update_job_status(
            redis,
            job_id,
            status=JobStatus.COMPLETED,
            progress={
                "stage": "completed",
                "percent_complete": 100,
                "message": "Processing complete",
                "updated_at": datetime.now(UTC).isoformat(),
            },
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
    key = f"job:{job_id}"

    # Get existing job data
    existing = await redis.get(key)
    if existing:
        if isinstance(existing, bytes):
            job_data = json.loads(existing.decode())
        else:
            job_data = json.loads(str(existing))
    else:
        job_data = {}

    # Update fields
    if status:
        job_data["status"] = status.value
    if progress:
        job_data["progress"] = progress
    if result:
        job_data["result"] = result
    if artifacts:
        job_data["artifacts"] = artifacts
    if error:
        job_data["error"] = error
    if completed_at:
        job_data["completed_at"] = completed_at

    # Store updated data
    await redis.set(
        key,
        json.dumps(job_data),
        ex=settings.job_result_ttl_seconds,
    )
