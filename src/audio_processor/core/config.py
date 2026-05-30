"""Configuration settings for Audio Processor.

Settings are loaded from environment variables.
Pydantic-settings handles the parsing and validation.
"""

from __future__ import annotations

from typing import Literal

import platformdirs
from pydantic import Field, SecretStr, model_validator
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
        default=platformdirs.user_cache_dir("audio_processor"),
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
    job_store_backend: Literal["memory", "redis"] = Field(
        default="memory",
        description=(
            "Backend for job state. 'memory' is process-local (dev/single "
            "process); 'redis' shares state between the API and the worker."
        ),
    )
    enqueue_enabled: bool = Field(
        default=False,
        description=(
            "Enqueue submitted jobs to the ARQ worker. Requires the 'redis' "
            "job store backend so the worker and API share job state."
        ),
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

    # ==========================================================================
    # API Security
    # ==========================================================================
    auth_required: bool = Field(
        default=False,
        description="Require a valid X-API-Key header on /api/v1 endpoints",
    )
    api_keys: SecretStr = Field(
        default=SecretStr(""),
        description=(
            "Comma-separated API keys accepted when auth_required is true. "
            "Provide via the API_KEYS environment variable / secret."
        ),
    )
    rate_limit_enabled: bool = Field(
        default=False,
        description="Enable per-client rate limiting on expensive endpoints",
    )
    rate_limit_requests: int = Field(
        default=60,
        ge=1,
        description="Maximum requests allowed per rate-limit window",
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        ge=1,
        description="Length of the rate-limit window in seconds",
    )

    @property
    def max_file_size_bytes(self) -> int:
        """Maximum file size in bytes.

        Returns:
            File size limit converted from megabytes to bytes.
        """
        return self.audio_max_file_size_mb * 1024 * 1024

    @property
    def max_duration_seconds(self) -> float:
        """Maximum audio duration in seconds.

        Returns:
            Duration limit converted from hours to seconds.
        """
        return self.audio_max_duration_hours * 3600

    @property
    def api_key_set(self) -> frozenset[str]:
        """Configured API keys as a set.

        Returns:
            Frozenset of non-empty, stripped API keys parsed from ``api_keys``.
        """
        raw = self.api_keys.get_secret_value()
        return frozenset(key.strip() for key in raw.split(",") if key.strip())

    @model_validator(mode="after")
    def _check_auth_has_keys(self) -> Settings:
        """Ensure authentication is configured with at least one key.

        Returns:
            The validated settings instance.

        Raises:
            ValueError: If ``auth_required`` is set with no API keys, which
                would reject every request at runtime.
        """
        if self.auth_required and not self.api_key_set:
            msg = "auth_required=True requires at least one key in api_keys"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _check_enqueue_requires_redis(self) -> Settings:
        """Ensure enqueueing is only enabled with a shared Redis store.

        Returns:
            The validated settings instance.

        Raises:
            ValueError: If ``enqueue_enabled`` is set without the Redis backend
                (jobs would otherwise be enqueued where the worker cannot see
                them, and never processed).
        """
        if self.enqueue_enabled and self.job_store_backend != "redis":
            msg = "enqueue_enabled requires job_store_backend='redis'"
            raise ValueError(msg)
        return self


# A single, global instance of the settings
settings = Settings()
