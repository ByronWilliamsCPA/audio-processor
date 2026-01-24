"""Configuration settings for Audio Processor.

Settings are loaded from environment variables.
Pydantic-settings handles the parsing and validation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for the application.

    Settings are loaded from environment variables. Audio processing settings
    include Deepgram API configuration, Redis for job queue, and audio
    preprocessing parameters.

    Attributes:
        log_level: The logging level for the application.
        json_logs: Flag to enable or disable JSON formatted logs.
        include_timestamp: Flag to include timestamps in logs.
        environment: Deployment environment (development, staging, production).
    """

    model_config = SettingsConfigDict(
        env_prefix="",  # No prefix - use exact env var names
        case_sensitive=False,
        extra="ignore",
    )

    # ==========================================================================
    # General Settings
    # ==========================================================================
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    json_logs: bool = False
    include_timestamp: bool = True
    environment: Literal["development", "staging", "production"] = "development"

    # ==========================================================================
    # Deepgram API Configuration
    # ==========================================================================
    deepgram_api_key: SecretStr | None = Field(
        default=None,
        description="Deepgram API key for transcription services",
    )
    deepgram_model: str = Field(
        default="nova-2",
        description="Deepgram model to use (nova-2, nova, enhanced, base)",
    )
    deepgram_diarize: bool = Field(
        default=True,
        description="Enable speaker diarization",
    )
    deepgram_smart_format: bool = Field(
        default=True,
        description="Enable smart formatting (punctuation, casing)",
    )
    deepgram_summarize: bool = Field(
        default=True,
        description="Enable AI summarization",
    )
    deepgram_language: str = Field(
        default="en",
        description="Default language for transcription",
    )
    deepgram_timeout_seconds: int = Field(
        default=300,
        description="Timeout for Deepgram API calls in seconds",
    )

    # ==========================================================================
    # Redis Configuration
    # ==========================================================================
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for job queue and caching",
    )

    # ==========================================================================
    # Audio Processing Configuration
    # ==========================================================================
    audio_temp_dir: str = Field(
        default="/tmp/audio_processor",  # noqa: S108
        description="Temporary directory for audio file processing",
    )
    audio_max_file_size_mb: int = Field(
        default=500,
        ge=1,
        le=2000,
        description="Maximum audio file size in megabytes",
    )
    audio_max_duration_hours: float = Field(
        default=4.0,
        ge=0.1,
        le=24.0,
        description="Maximum audio duration in hours",
    )
    audio_target_sample_rate: int = Field(
        default=16000,
        description="Target sample rate for preprocessing (Hz)",
    )
    audio_target_channels: int = Field(
        default=1,
        description="Target number of channels (1=mono, 2=stereo)",
    )
    audio_target_rms_db: float = Field(
        default=-20.0,
        description="Target RMS level for normalization (dBFS)",
    )

    # ==========================================================================
    # VAD (Voice Activity Detection) Configuration
    # ==========================================================================
    vad_enabled: bool = Field(
        default=True,
        description="Enable Voice Activity Detection for silence removal",
    )
    vad_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="VAD threshold (0.0-1.0, higher = stricter)",
    )
    vad_min_silence_duration_ms: int = Field(
        default=500,
        description="Minimum silence duration to remove (milliseconds)",
    )
    vad_min_speech_duration_ms: int = Field(
        default=250,
        description="Minimum speech duration to keep (milliseconds)",
    )

    # ==========================================================================
    # Quality Assessment Configuration
    # ==========================================================================
    quality_snr_excellent_db: float = Field(
        default=25.0,
        description="SNR threshold for excellent quality (dB)",
    )
    quality_snr_good_db: float = Field(
        default=15.0,
        description="SNR threshold for good quality (dB)",
    )
    quality_snr_fair_db: float = Field(
        default=10.0,
        description="SNR threshold for fair quality (dB)",
    )
    quality_max_silence_ratio: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Maximum acceptable silence ratio before warning",
    )
    quality_max_clipping_ratio: float = Field(
        default=0.01,
        ge=0.0,
        le=1.0,
        description="Maximum acceptable clipping ratio before warning",
    )

    # ==========================================================================
    # Job Processing Configuration
    # ==========================================================================
    job_max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts for failed jobs",
    )
    job_timeout_seconds: int = Field(
        default=600,
        description="Job processing timeout in seconds",
    )
    job_result_ttl_seconds: int = Field(
        default=86400,
        description="Time to keep job results in Redis (seconds)",
    )

    # ==========================================================================
    # API Configuration
    # ==========================================================================
    api_host: str = Field(
        default="0.0.0.0",  # noqa: S104
        description="API server host",
    )
    api_port: int = Field(
        default=8000,
        description="API server port",
    )

    @property
    def max_file_size_bytes(self) -> int:
        """Maximum file size in bytes."""
        return self.audio_max_file_size_mb * 1024 * 1024

    @property
    def max_duration_seconds(self) -> float:
        """Maximum audio duration in seconds."""
        return self.audio_max_duration_hours * 3600


# A single, global instance of the settings
settings = Settings()
