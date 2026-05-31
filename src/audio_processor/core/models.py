"""Core data models for audio processing.

This module defines the Pydantic models used throughout the audio processing
pipeline for jobs, transcription results, speakers, and quality metrics.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal  # noqa: TC003 - Required at runtime for Pydantic
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    """Get current UTC time (timezone-aware).

    Returns:
        datetime: Current datetime in UTC with timezone info attached.
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
        model_config: Pydantic model configuration.
        word (str): The transcribed word text.
        start (float): Start time in seconds.
        end (float): End time in seconds.
        confidence (float): Confidence score (0.0 to 1.0).
        speaker (int | None): Speaker identifier (if diarization enabled).
        punctuated_word (str | None): Word with punctuation applied.
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
        model_config: Pydantic model configuration.
        id (str): Unique identifier for this utterance.
        speaker (int): Speaker identifier.
        start (float): Start time in seconds.
        end (float): End time in seconds.
        text (str): Full text of the utterance.
        confidence (float): Average confidence score.
        words (tuple[Word, ...]): List of words in this utterance.
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
            float: Elapsed time between start and end timestamps.
        """
        return self.end - self.start


# =============================================================================
# Speaker Model
# =============================================================================


class Speaker(BaseModel):
    """A speaker identified through diarization.

    Attributes:
        model_config: Pydantic model configuration.
        id (int): Numeric speaker identifier (0-indexed).
        label (str): Display label (e.g., "Speaker 1").
        total_duration (float): Total speaking time in seconds.
        utterance_count (int): Number of utterances from this speaker.
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
        model_config: Pydantic model configuration.
        snr_db (float): Signal-to-noise ratio in decibels.
        silence_ratio (float): Percentage of audio that is silence (0.0 to 1.0).
        clipping_ratio (float): Percentage of clipped samples (0.0 to 1.0).
        peak_amplitude (float): Maximum amplitude value.
        rms_level_db (float): RMS level in decibels.
        duration_seconds (float): Total duration of audio.
        sample_rate (int): Sample rate in Hz.
        channels (int): Number of audio channels.
        quality_score (float): Composite quality score (0.0 to 1.0).
        quality_level (QualityLevel): Qualitative assessment level.
        warnings (tuple[str, ...]): List of quality warnings.
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
        model_config: Pydantic model configuration.
        duration_seconds (float): Duration of the audio in seconds.
        word_count (int): Total number of words transcribed.
        confidence_mean (float): Average confidence across all words.
        confidence_min (float): Minimum confidence score.
        model (str): ASR model used for transcription.
        language (str): Detected or specified language code.
        processing_time_seconds (float | None): Time taken for transcription.
        cost_usd (Decimal | None): Estimated cost in USD.
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
        model_config: Pydantic model configuration.
        transcript (str): Full transcript text.
        utterances (tuple[Utterance, ...]): List of speaker-attributed utterances.
        speakers (tuple[Speaker, ...]): List of identified speakers.
        words (tuple[Word, ...]): Flat list of all words with timing.
        summary (str | None): AI-generated summary (if enabled).
        metadata (TranscriptionMetadata): Transcription metadata.
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
        model_config: Pydantic model configuration.
        file_path (str): Path to the input audio file.
        original_filename (str): Original name of uploaded file.
        file_size_bytes (int): Size of the file in bytes.
        content_type (str): MIME type of the file.
        enable_diarization (bool): Whether to enable speaker diarization.
        enable_summarization (bool): Whether to generate summary.
        language (str): Language code (e.g., "en", "es").
        callback_url (str | None): Optional webhook URL for completion notification.
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
        stage (str): Current processing stage.
        percent_complete (int): Percentage complete (0-100).
        message (str): Human-readable status message.
        started_at (datetime | None): When processing started.
        updated_at (datetime): Last progress update time.
    """

    stage: str
    percent_complete: int = Field(ge=0, le=100)
    message: str
    started_at: datetime | None = None
    updated_at: datetime


class AudioJob(BaseModel):
    """An audio processing job with full state.

    Attributes:
        id (UUID): Unique job identifier.
        status (JobStatus): Current job status.
        input (AudioJobInput): Job input parameters.
        progress (AudioJobProgress | None): Current progress (if processing).
        result (TranscriptionResult | None): Transcription result (if completed).
        quality (AudioQualityMetrics | None): Audio quality metrics (if assessed).
        error (str | None): Error message (if failed).
        created_at (datetime): Job creation timestamp.
        completed_at (datetime | None): Job completion timestamp.
        processing_time_seconds (float | None): Total processing time.
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
        enable_diarization (bool): Whether to enable speaker diarization.
        enable_summarization (bool): Whether to generate summary.
        language (str): Language code for transcription.
        callback_url (str | None): Optional webhook for completion notification.
    """

    enable_diarization: bool = True
    enable_summarization: bool = True
    language: str = "en"
    callback_url: str | None = None


class ProcessAudioResponse(BaseModel):
    """Response for successful audio submission.

    Attributes:
        job_id (UUID): Unique identifier for the submitted job.
        status (JobStatus): Initial job status.
        status_url (str): URL to check job status.
        message (str): Confirmation message.
    """

    job_id: UUID
    status: JobStatus
    status_url: str
    message: str


class JobStatusResponse(BaseModel):
    """Response for job status queries.

    Attributes:
        job_id (UUID): Job identifier.
        status (JobStatus): Current status.
        progress (AudioJobProgress | None): Progress information (if processing).
        result_url (str | None): URL to fetch results (if completed).
        error (str | None): Error message (if failed).
        created_at (datetime): Job creation time.
        completed_at (datetime | None): Job completion time (if done).
    """

    job_id: UUID
    status: JobStatus
    progress: AudioJobProgress | None = None
    result_url: str | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
