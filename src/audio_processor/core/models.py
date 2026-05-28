"""Core data models for audio processing.

This module defines the Pydantic models used throughout the audio processing
pipeline for jobs, transcription results, speakers, and quality metrics.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal  # noqa: TC003 - Required at runtime for Pydantic
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

# Python 3.10 compatibility: UTC was added in 3.11
if sys.version_info >= (3, 11):  # noqa: UP036
    from datetime import UTC
else:
    UTC = timezone.utc  # noqa: UP017  # pyright: ignore[reportUnreachable]


def _utc_now() -> datetime:
    """Get current UTC time (timezone-aware).

    Returns:
        Current datetime in UTC with timezone info attached.
    """
    return datetime.now(UTC)


class JobStatus(StrEnum):
    """Status of an audio processing job."""

    PENDING = "pending"
    QUEUED = "queued"
    PREPROCESSING = "preprocessing"
    TRANSCRIBING = "transcribing"
    POSTPROCESSING = "postprocessing"
    COMPLETED = "completed"
    FAILED = "failed"


class AudioFormat(StrEnum):
    """Supported audio file formats."""

    MP3 = "mp3"
    WAV = "wav"
    M4A = "m4a"
    FLAC = "flac"
    OGG = "ogg"
    WEBM = "webm"
    # Video formats (audio extraction)
    MP4 = "mp4"
    MOV = "mov"
    AVI = "avi"
    MKV = "mkv"


class QualityLevel(StrEnum):
    """Audio quality assessment level."""

    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


# =============================================================================
# Word and Utterance Models
# =============================================================================


class Word(BaseModel):
    """A single transcribed word with timing information.

    Attributes:
        word: The transcribed word text.
        start: Start time in seconds.
        end: End time in seconds.
        confidence: Confidence score (0.0 to 1.0).
        speaker: Speaker identifier (if diarization enabled).
        punctuated_word: Word with punctuation applied.
    """

    model_config = ConfigDict(frozen=True)

    word: str
    start: float
    end: float
    confidence: float = Field(ge=0.0, le=1.0)
    speaker: int | None = None
    punctuated_word: str | None = None


class Utterance(BaseModel):
    """A continuous speech segment from a single speaker.

    Attributes:
        id: Unique identifier for this utterance.
        speaker: Speaker identifier.
        start: Start time in seconds.
        end: End time in seconds.
        text: Full text of the utterance.
        confidence: Average confidence score.
        words: List of words in this utterance.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    speaker: int
    start: float
    end: float
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    words: tuple[Word, ...] = Field(default_factory=tuple)

    @property
    def duration(self) -> float:
        """Duration of the utterance in seconds.

        Returns:
            Elapsed time between start and end timestamps.
        """
        return self.end - self.start


# =============================================================================
# Speaker Model
# =============================================================================


class Speaker(BaseModel):
    """A speaker identified through diarization.

    Attributes:
        id: Numeric speaker identifier (0-indexed).
        label: Display label (e.g., "Speaker 1").
        total_duration: Total speaking time in seconds.
        utterance_count: Number of utterances from this speaker.
    """

    model_config = ConfigDict(frozen=True)

    id: int
    label: str
    total_duration: float = 0.0
    utterance_count: int = 0


# =============================================================================
# Quality Assessment Models
# =============================================================================


class AudioQualityMetrics(BaseModel):
    """Audio quality assessment metrics.

    Attributes:
        snr_db: Signal-to-noise ratio in decibels.
        silence_ratio: Percentage of audio that is silence (0.0 to 1.0).
        clipping_ratio: Percentage of clipped samples (0.0 to 1.0).
        peak_amplitude: Maximum amplitude value.
        rms_level_db: RMS level in decibels.
        duration_seconds: Total duration of audio.
        sample_rate: Sample rate in Hz.
        channels: Number of audio channels.
        quality_score: Composite quality score (0.0 to 1.0).
        quality_level: Qualitative assessment level.
        warnings: List of quality warnings.
    """

    model_config = ConfigDict(frozen=True)

    snr_db: float
    silence_ratio: float = Field(ge=0.0, le=1.0)
    clipping_ratio: float = Field(ge=0.0, le=1.0)
    peak_amplitude: float
    rms_level_db: float
    duration_seconds: float
    sample_rate: int
    channels: int
    quality_score: float = Field(ge=0.0, le=1.0)
    quality_level: QualityLevel
    warnings: tuple[str, ...] = Field(default_factory=tuple)


# =============================================================================
# Transcription Result Models
# =============================================================================


class TranscriptionMetadata(BaseModel):
    """Metadata about a transcription result.

    Attributes:
        duration_seconds: Duration of the audio in seconds.
        word_count: Total number of words transcribed.
        confidence_mean: Average confidence across all words.
        confidence_min: Minimum confidence score.
        model: ASR model used for transcription.
        language: Detected or specified language code.
        processing_time_seconds: Time taken for transcription.
        cost_usd: Estimated cost in USD.
    """

    model_config = ConfigDict(frozen=True)

    duration_seconds: float
    word_count: int
    confidence_mean: float = Field(ge=0.0, le=1.0)
    confidence_min: float = Field(ge=0.0, le=1.0)
    model: str = "nova-2"
    language: str = "en"
    processing_time_seconds: float | None = None
    cost_usd: Decimal | None = None


class TranscriptionResult(BaseModel):
    """Complete transcription result from ASR processing.

    Attributes:
        transcript: Full transcript text.
        utterances: List of speaker-attributed utterances.
        speakers: List of identified speakers.
        words: Flat list of all words with timing.
        summary: AI-generated summary (if enabled).
        metadata: Transcription metadata.
    """

    model_config = ConfigDict(frozen=True)

    transcript: str
    utterances: tuple[Utterance, ...] = Field(default_factory=tuple)
    speakers: tuple[Speaker, ...] = Field(default_factory=tuple)
    words: tuple[Word, ...] = Field(default_factory=tuple)
    summary: str | None = None
    metadata: TranscriptionMetadata


# =============================================================================
# Job Models
# =============================================================================


class AudioJobInput(BaseModel):
    """Input parameters for an audio processing job.

    Attributes:
        file_path: Path to the input audio file.
        original_filename: Original name of uploaded file.
        file_size_bytes: Size of the file in bytes.
        content_type: MIME type of the file.
        enable_diarization: Whether to enable speaker diarization.
        enable_summarization: Whether to generate summary.
        language: Language code (e.g., "en", "es").
        callback_url: Optional webhook URL for completion notification.
    """

    model_config = ConfigDict(frozen=True)

    file_path: str
    original_filename: str
    file_size_bytes: int
    content_type: str
    enable_diarization: bool = True
    enable_summarization: bool = True
    language: str = "en"
    callback_url: str | None = None


class AudioJobProgress(BaseModel):
    """Progress information for a running job.

    Attributes:
        stage: Current processing stage.
        percent_complete: Percentage complete (0-100).
        message: Human-readable status message.
        started_at: When processing started.
        updated_at: Last progress update time.
    """

    stage: str
    percent_complete: int = Field(ge=0, le=100)
    message: str
    started_at: datetime | None = None
    updated_at: datetime


class AudioJob(BaseModel):
    """An audio processing job with full state.

    Attributes:
        id: Unique job identifier.
        status: Current job status.
        input: Job input parameters.
        progress: Current progress (if processing).
        result: Transcription result (if completed).
        quality: Audio quality metrics (if assessed).
        error: Error message (if failed).
        created_at: Job creation timestamp.
        completed_at: Job completion timestamp.
        processing_time_seconds: Total processing time.
    """

    id: UUID = Field(default_factory=uuid4)
    status: JobStatus = JobStatus.PENDING
    input: AudioJobInput
    progress: AudioJobProgress | None = None
    result: TranscriptionResult | None = None
    quality: AudioQualityMetrics | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=_utc_now)
    completed_at: datetime | None = None
    processing_time_seconds: float | None = None


# =============================================================================
# API Request/Response Models
# =============================================================================


class ProcessAudioRequest(BaseModel):
    """Request body for audio processing submission.

    Attributes:
        enable_diarization: Whether to enable speaker diarization.
        enable_summarization: Whether to generate summary.
        language: Language code for transcription.
        callback_url: Optional webhook for completion notification.
    """

    enable_diarization: bool = True
    enable_summarization: bool = True
    language: str = "en"
    callback_url: str | None = None


class ProcessAudioResponse(BaseModel):
    """Response for successful audio submission.

    Attributes:
        job_id: Unique identifier for the submitted job.
        status: Initial job status.
        status_url: URL to check job status.
        message: Confirmation message.
    """

    job_id: UUID
    status: JobStatus
    status_url: str
    message: str


class JobStatusResponse(BaseModel):
    """Response for job status queries.

    Attributes:
        job_id: Job identifier.
        status: Current status.
        progress: Progress information (if processing).
        result_url: URL to fetch results (if completed).
        error: Error message (if failed).
        created_at: Job creation time.
        completed_at: Job completion time (if done).
    """

    job_id: UUID
    status: JobStatus
    progress: AudioJobProgress | None = None
    result_url: str | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
