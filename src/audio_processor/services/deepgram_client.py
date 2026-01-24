"""Deepgram transcription client service.

This module provides integration with Deepgram's Nova-2 ASR API for:
- Speech-to-text transcription
- Speaker diarization
- Automatic summarization

Compatible with Deepgram SDK v5.x.
"""

from __future__ import annotations

import time
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from audio_processor.core.config import settings
from audio_processor.core.exceptions import (
    ConfigurationError,
    TranscriptionError,
    ValidationError,
)
from audio_processor.core.models import (
    Speaker,
    TranscriptionMetadata,
    TranscriptionResult,
    Utterance,
    Word,
)
from audio_processor.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Deepgram pricing per hour (Nova-2 with features)
# Base: $0.0043/min, Diarization: +$0.0017/min, Summarization: ~$0.01/min
DEEPGRAM_COST_PER_MINUTE_BASE = Decimal("0.0043")
DEEPGRAM_COST_PER_MINUTE_DIARIZATION = Decimal("0.0017")
DEEPGRAM_COST_PER_MINUTE_SUMMARIZATION = Decimal("0.01")


class DeepgramTranscriptionClient:
    """Client for Deepgram transcription services.

    Provides methods for transcribing audio files using Deepgram's Nova-2
    model with optional speaker diarization and summarization.

    Example:
        >>> client = DeepgramTranscriptionClient()
        >>> result = client.transcribe("/path/to/audio.wav")
        >>> print(f"Transcript: {result.transcript}")
        >>> for speaker in result.speakers:
        ...     print(f"{speaker.label}: {speaker.total_duration}s")
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        language: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        """Initialize the Deepgram client.

        Args:
            api_key: Deepgram API key. Defaults to settings.
            model: Model to use (nova-2, nova, enhanced, base).
            language: Default language code.
            timeout_seconds: API timeout in seconds.

        Raises:
            ConfigurationError: If API key is not provided or configured.
        """
        self.api_key = api_key
        if self.api_key is None and settings.deepgram_api_key:
            self.api_key = settings.deepgram_api_key.get_secret_value()

        if not self.api_key:
            msg = "Deepgram API key not configured. Set DEEPGRAM_API_KEY environment variable."
            raise ConfigurationError(msg)

        self.model = model or settings.deepgram_model
        self.language = language or settings.deepgram_language
        self.timeout_seconds = timeout_seconds or settings.deepgram_timeout_seconds

        # Initialize Deepgram client (v5 SDK)
        try:
            from deepgram import DeepgramClient

            self._client = DeepgramClient(api_key=self.api_key)
        except Exception as e:
            msg = f"Failed to initialize Deepgram client: {e}"
            raise ConfigurationError(msg) from e

    def transcribe(
        self,
        file_path: str | Path,
        *,
        enable_diarization: bool | None = None,
        enable_summarization: bool | None = None,
        language: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe an audio file using Deepgram.

        Args:
            file_path: Path to the audio file.
            enable_diarization: Enable speaker diarization. Defaults to settings.
            enable_summarization: Enable AI summarization. Defaults to settings.
            language: Language code for transcription.

        Returns:
            TranscriptionResult with transcript, speakers, and metadata.

        Raises:
            ValidationError: If file doesn't exist or can't be read.
            TranscriptionError: If transcription fails.
        """
        file_path = Path(file_path)

        if not file_path.exists():
            msg = f"Audio file not found: {file_path}"
            raise ValidationError(msg, field="file_path", value=str(file_path))

        # Use settings defaults if not specified
        diarize = enable_diarization if enable_diarization is not None else settings.deepgram_diarize
        summarize = enable_summarization if enable_summarization is not None else settings.deepgram_summarize
        lang = language or self.language

        logger.info(
            "starting_transcription",
            file_path=str(file_path),
            model=self.model,
            diarization=diarize,
            summarization=summarize,
            language=lang,
        )

        start_time = time.time()

        try:
            # Read audio file
            with file_path.open("rb") as audio_file:
                audio_data = audio_file.read()

            # Build options for Deepgram v5 SDK
            options: dict[str, Any] = {  # pyright: ignore[reportExplicitAny]
                "model": self.model,
                "language": lang,
                "smart_format": settings.deepgram_smart_format,
                "punctuate": True,
                "diarize": diarize,
                "utterances": diarize,  # Get utterance-level data when diarizing
            }

            if summarize:
                options["summarize"] = "v2"

            # Call Deepgram API using v5 SDK
            # The v5 SDK uses listen.rest.transcribe_file
            response = self._client.listen.rest.v("1").transcribe_file(
                {"buffer": audio_data},
                options,
            )

            processing_time = time.time() - start_time

            # Parse response
            result = self._parse_response(
                response,
                diarize=diarize,
                summarize=summarize,
                processing_time=processing_time,
            )

            logger.info(
                "transcription_completed",
                file_path=str(file_path),
                duration_seconds=result.metadata.duration_seconds,
                word_count=result.metadata.word_count,
                speaker_count=len(result.speakers),
                processing_time=round(processing_time, 2),
            )

            return result

        except Exception as e:
            processing_time = time.time() - start_time
            logger.exception(
                "transcription_failed",
                file_path=str(file_path),
                error=str(e),
                processing_time=round(processing_time, 2),
            )

            # Handle specific error types
            error_str = str(e).lower()
            if "unauthorized" in error_str or "401" in error_str:
                msg = "Deepgram API authentication failed. Check your API key."
                raise TranscriptionError(msg, status_code=401) from e
            if "rate limit" in error_str or "429" in error_str:
                msg = "Deepgram API rate limit exceeded. Try again later."
                raise TranscriptionError(msg, status_code=429) from e
            if "timeout" in error_str:
                msg = f"Deepgram API timeout after {self.timeout_seconds}s"
                raise TranscriptionError(msg, status_code=504) from e

            msg = f"Transcription failed: {e}"
            raise TranscriptionError(msg) from e

    def _parse_response(
        self,
        response: Any,  # pyright: ignore[reportExplicitAny]
        *,
        diarize: bool,
        summarize: bool,
        processing_time: float,
    ) -> TranscriptionResult:
        """Parse Deepgram response into TranscriptionResult.

        Args:
            response: Deepgram API response.
            diarize: Whether diarization was enabled.
            summarize: Whether summarization was enabled.
            processing_time: Time taken for API call.

        Returns:
            Parsed TranscriptionResult.
        """
        # Handle response object - v5 SDK returns ListenV1Response
        # Access results through the response object
        results = getattr(response, "results", None)
        if not results:
            return self._empty_result(processing_time)

        channels = getattr(results, "channels", None)
        if not channels or len(channels) == 0:
            return self._empty_result(processing_time)

        channel = channels[0]
        alternatives = getattr(channel, "alternatives", None)
        if not alternatives or len(alternatives) == 0:
            return self._empty_result(processing_time)

        alternative = alternatives[0]

        # Extract full transcript
        transcript = getattr(alternative, "transcript", "") or ""

        # Extract words with timing
        words: list[Word] = []
        alt_words = getattr(alternative, "words", None) or []
        for w in alt_words:
            words.append(
                Word(
                    word=getattr(w, "word", "") or "",
                    start=getattr(w, "start", 0.0) or 0.0,
                    end=getattr(w, "end", 0.0) or 0.0,
                    confidence=getattr(w, "confidence", 0.0) or 0.0,
                    speaker=getattr(w, "speaker", None) if diarize else None,
                    punctuated_word=getattr(w, "punctuated_word", None),
                )
            )

        # Extract utterances if diarization enabled
        utterances: list[Utterance] = []
        speakers_dict: dict[int, Speaker] = {}

        result_utterances = getattr(results, "utterances", None)
        if diarize and result_utterances:
            for utt in result_utterances:
                speaker_id = getattr(utt, "speaker", 0) or 0
                utt_words_list = getattr(utt, "words", None) or []
                utt_words = [
                    Word(
                        word=getattr(w, "word", "") or "",
                        start=getattr(w, "start", 0.0) or 0.0,
                        end=getattr(w, "end", 0.0) or 0.0,
                        confidence=getattr(w, "confidence", 0.0) or 0.0,
                        speaker=getattr(w, "speaker", None),
                        punctuated_word=getattr(w, "punctuated_word", None),
                    )
                    for w in utt_words_list
                ]

                utterance = Utterance(
                    speaker=speaker_id,
                    start=getattr(utt, "start", 0.0) or 0.0,
                    end=getattr(utt, "end", 0.0) or 0.0,
                    text=getattr(utt, "transcript", "") or "",
                    confidence=getattr(utt, "confidence", 0.0) or 0.0,
                    words=tuple(utt_words),
                )
                utterances.append(utterance)

                # Track speaker statistics
                if speaker_id not in speakers_dict:
                    speakers_dict[speaker_id] = Speaker(
                        id=speaker_id,
                        label=f"Speaker {speaker_id + 1}",
                        total_duration=0.0,
                        utterance_count=0,
                    )

                # Update speaker stats (need to create new instance since frozen)
                existing = speakers_dict[speaker_id]
                speakers_dict[speaker_id] = Speaker(
                    id=existing.id,
                    label=existing.label,
                    total_duration=existing.total_duration + utterance.duration,
                    utterance_count=existing.utterance_count + 1,
                )

        speakers = list(speakers_dict.values())

        # Extract summary if available
        summary: str | None = None
        if summarize:
            result_summary = getattr(results, "summary", None)
            if result_summary:
                summary = getattr(result_summary, "short", None)

        # Calculate metadata
        result_metadata = getattr(results, "metadata", None)
        duration = getattr(result_metadata, "duration", 0.0) if result_metadata else 0.0
        word_count = len(words)
        confidences = [w.confidence for w in words]
        confidence_mean = sum(confidences) / len(confidences) if confidences else 0.0
        confidence_min = min(confidences) if confidences else 0.0

        # Estimate cost
        duration_minutes = duration / 60
        cost = DEEPGRAM_COST_PER_MINUTE_BASE * Decimal(str(duration_minutes))
        if diarize:
            cost += DEEPGRAM_COST_PER_MINUTE_DIARIZATION * Decimal(str(duration_minutes))
        if summarize:
            cost += DEEPGRAM_COST_PER_MINUTE_SUMMARIZATION * Decimal(str(duration_minutes))

        metadata = TranscriptionMetadata(
            duration_seconds=duration,
            word_count=word_count,
            confidence_mean=confidence_mean,
            confidence_min=confidence_min,
            model=self.model,
            language=self.language,
            processing_time_seconds=processing_time,
            cost_usd=cost.quantize(Decimal("0.0001")),
        )

        return TranscriptionResult(
            transcript=transcript,
            utterances=tuple(utterances),
            speakers=tuple(speakers),
            words=tuple(words),
            summary=summary,
            metadata=metadata,
        )

    def _empty_result(self, processing_time: float) -> TranscriptionResult:
        """Create an empty result for edge cases.

        Args:
            processing_time: Time taken for API call.

        Returns:
            Empty TranscriptionResult.
        """
        return TranscriptionResult(
            transcript="",
            utterances=(),
            speakers=(),
            words=(),
            summary=None,
            metadata=TranscriptionMetadata(
                duration_seconds=0.0,
                word_count=0,
                confidence_mean=0.0,
                confidence_min=0.0,
                model=self.model,
                language=self.language,
                processing_time_seconds=processing_time,
                cost_usd=Decimal("0"),
            ),
        )

    def estimate_cost(
        self,
        duration_seconds: float,
        *,
        enable_diarization: bool = True,
        enable_summarization: bool = True,
    ) -> Decimal:
        """Estimate the cost of transcribing audio.

        Args:
            duration_seconds: Audio duration in seconds.
            enable_diarization: Include diarization cost.
            enable_summarization: Include summarization cost.

        Returns:
            Estimated cost in USD.
        """
        duration_minutes = Decimal(str(duration_seconds / 60))
        cost = DEEPGRAM_COST_PER_MINUTE_BASE * duration_minutes

        if enable_diarization:
            cost += DEEPGRAM_COST_PER_MINUTE_DIARIZATION * duration_minutes
        if enable_summarization:
            cost += DEEPGRAM_COST_PER_MINUTE_SUMMARIZATION * duration_minutes

        return cost.quantize(Decimal("0.0001"))
