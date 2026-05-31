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
from typing import Any

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

# Optional dependency: deepgram-sdk is in the 'audio' extras group.
# The module-level try/except keeps module import safe when the extra isn't installed;
# ConfigurationError is raised at instantiation time (not import time) so callers can
# catch it gracefully (see audio_tasks.py).
try:
    from deepgram import DeepgramClient as _DeepgramClient

    _deepgram_available: bool = True
except ImportError:
    _deepgram_available = False

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

    Args:
        api_key (str | None): Deepgram API key. Defaults to settings.
        model (str | None): Model to use (nova-2, nova, enhanced, base).
        language (str | None): Default language code.
        timeout_seconds (int | None): API timeout in seconds.

    Raises:
        ConfigurationError: If API key is not provided or configured.

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
        if not _deepgram_available:
            msg = "deepgram package not installed. Install the 'audio' extras: uv sync --extra audio"
            raise ConfigurationError(msg)
        try:
            self._client = _DeepgramClient(api_key=self.api_key)  # pyright: ignore[reportPossiblyUnboundVariable]
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
            file_path (str | Path): Path to the audio file.
            enable_diarization (bool | None): Enable speaker diarization. Defaults to settings.
            enable_summarization (bool | None): Enable AI summarization. Defaults to settings.
            language (str | None): Language code for transcription.

        Returns:
            TranscriptionResult: TranscriptionResult with transcript, speakers, and metadata.

        Raises:
            ValidationError: If file doesn't exist or can't be read.
            TranscriptionError: If transcription fails.
        """
        file_path = Path(file_path)

        if not file_path.exists():
            msg = f"Audio file not found: {file_path}"
            raise ValidationError(msg, field="file_path", value=str(file_path))

        # Use settings defaults if not specified
        diarize = (
            enable_diarization
            if enable_diarization is not None
            else settings.deepgram_diarize
        )
        summarize = (
            enable_summarization
            if enable_summarization is not None
            else settings.deepgram_summarize
        )
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

            # #CRITICAL: ExternalResources: Deepgram API must be reachable and return a valid response.
            # #VERIFY: Ensure timeout is configured and ExternalServiceError is raised on network failure.
            response = self._client.listen.rest.v("1").transcribe_file(  # pyright: ignore[reportAttributeAccessIssue]
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

        else:
            logger.info(
                "transcription_completed",
                file_path=str(file_path),
                duration_seconds=result.metadata.duration_seconds,
                word_count=result.metadata.word_count,
                speaker_count=len(result.speakers),
                processing_time=round(processing_time, 2),
            )
            return result

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
            response (Any): Deepgram API response.
            diarize (bool): Whether diarization was enabled.
            summarize (bool): Whether summarization was enabled.
            processing_time (float): Time taken for API call.

        Returns:
            TranscriptionResult: Parsed TranscriptionResult.
        """
        alternative = self._extract_alternative(response)
        if alternative is None:
            return self._empty_result(processing_time)

        results = getattr(response, "results", None)
        transcript = getattr(alternative, "transcript", "") or ""
        words = self._build_word_list(alternative, diarize=diarize)

        result_utterances = getattr(results, "utterances", None)
        utterances, speakers = self._parse_utterances_and_speakers(
            result_utterances if diarize else None
        )

        summary = self._extract_summary(results, summarize=summarize)

        result_metadata = getattr(results, "metadata", None)
        duration = getattr(result_metadata, "duration", 0.0) if result_metadata else 0.0
        confidence_mean, confidence_min = self._calculate_confidence(words)
        cost = self._calculate_cost(duration / 60, diarize=diarize, summarize=summarize)

        metadata = TranscriptionMetadata(
            duration_seconds=duration,
            word_count=len(words),
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

    def _extract_alternative(
        self,
        response: Any,  # pyright: ignore[reportExplicitAny]
    ) -> Any:  # pyright: ignore[reportExplicitAny]
        """Extract the first transcription alternative from a Deepgram response.

        Args:
            response (Any): Deepgram API response object.

        Returns:
            Any: The first alternative object, or None if the response is empty or
            does not contain usable data.
        """
        results = getattr(response, "results", None)
        if not results:
            return None
        channels = getattr(results, "channels", None)
        if not channels:
            return None
        alternatives = getattr(channels[0], "alternatives", None)
        if not alternatives:
            return None
        return alternatives[0]

    def _build_word_list(
        self,
        alternative: Any,  # pyright: ignore[reportExplicitAny]
        *,
        diarize: bool,
    ) -> list[Word]:
        """Build a list of Word objects from a Deepgram transcription alternative.

        Args:
            alternative (Any): A Deepgram alternative object containing word timing data.
            diarize (bool): Whether speaker diarization was enabled.

        Returns:
            list[Word]: List of Word objects with timing and confidence information.
        """
        alt_words = getattr(alternative, "words", None) or []
        return [
            Word(
                word=getattr(w, "word", "") or "",
                start=getattr(w, "start", 0.0) or 0.0,
                end=getattr(w, "end", 0.0) or 0.0,
                confidence=getattr(w, "confidence", 0.0) or 0.0,
                speaker=getattr(w, "speaker", None) if diarize else None,
                punctuated_word=getattr(w, "punctuated_word", None),
            )
            for w in alt_words
        ]

    @staticmethod
    def _extract_summary(
        results: Any,  # pyright: ignore[reportExplicitAny]
        *,
        summarize: bool,
    ) -> str | None:
        """Extract the short summary text from Deepgram results.

        Args:
            results (Any): Deepgram results object.
            summarize (bool): Whether summarization was requested.

        Returns:
            str | None: Short summary string, or None if unavailable.
        """
        if not summarize:
            return None
        result_summary = getattr(results, "summary", None)
        if not result_summary:
            return None
        short: str | None = getattr(result_summary, "short", None)
        return short

    @staticmethod
    def _calculate_confidence(words: list[Word]) -> tuple[float, float]:
        """Calculate mean and minimum confidence across a list of words.

        Args:
            words (list[Word]): List of Word objects with confidence scores.

        Returns:
            tuple[float, float]: Tuple of (mean_confidence, min_confidence). Both are 0.0 when the
            word list is empty.
        """
        confidences = [w.confidence for w in words]
        if not confidences:
            return 0.0, 0.0
        return sum(confidences) / len(confidences), min(confidences)

    @staticmethod
    def _calculate_cost(
        duration_minutes: float,
        *,
        diarize: bool,
        summarize: bool,
    ) -> Decimal:
        """Estimate the Deepgram API cost for a transcription.

        Args:
            duration_minutes (float): Audio duration in minutes.
            diarize (bool): Whether speaker diarization was enabled.
            summarize (bool): Whether summarization was enabled.

        Returns:
            Decimal: Estimated cost as a Decimal before quantization.
        """
        cost = DEEPGRAM_COST_PER_MINUTE_BASE * Decimal(str(duration_minutes))
        if diarize:
            cost += DEEPGRAM_COST_PER_MINUTE_DIARIZATION * Decimal(
                str(duration_minutes)
            )
        if summarize:
            cost += DEEPGRAM_COST_PER_MINUTE_SUMMARIZATION * Decimal(
                str(duration_minutes)
            )
        return cost

    def _parse_utterances_and_speakers(
        self,
        result_utterances: Any,  # pyright: ignore[reportExplicitAny]
    ) -> tuple[list[Utterance], list[Speaker]]:
        """Parse utterance list and accumulate per-speaker statistics.

        Args:
            result_utterances (Any): Utterance list from Deepgram response, or None if
                diarization was disabled.

        Returns:
            tuple[list[Utterance], list[Speaker]]: Tuple of (utterance list, speaker list with accumulated durations).
        """
        utterances: list[Utterance] = []
        speakers_dict: dict[int, Speaker] = {}

        if not result_utterances:
            return utterances, []

        for utt in result_utterances:
            speaker_id = getattr(utt, "speaker", 0) or 0
            utt_words = [
                Word(
                    word=getattr(w, "word", "") or "",
                    start=getattr(w, "start", 0.0) or 0.0,
                    end=getattr(w, "end", 0.0) or 0.0,
                    confidence=getattr(w, "confidence", 0.0) or 0.0,
                    speaker=getattr(w, "speaker", None),
                    punctuated_word=getattr(w, "punctuated_word", None),
                )
                for w in (getattr(utt, "words", None) or [])
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

            if speaker_id not in speakers_dict:
                speakers_dict[speaker_id] = Speaker(
                    id=speaker_id,
                    label=f"Speaker {speaker_id + 1}",
                    total_duration=0.0,
                    utterance_count=0,
                )
            existing = speakers_dict[speaker_id]
            speakers_dict[speaker_id] = Speaker(
                id=existing.id,
                label=existing.label,
                total_duration=existing.total_duration + utterance.duration,
                utterance_count=existing.utterance_count + 1,
            )

        return utterances, list(speakers_dict.values())

    def _empty_result(self, processing_time: float) -> TranscriptionResult:
        """Create an empty result for edge cases.

        Args:
            processing_time (float): Time taken for API call.

        Returns:
            TranscriptionResult: Empty TranscriptionResult.
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
                cost_usd=Decimal(0),
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
            duration_seconds (float): Audio duration in seconds.
            enable_diarization (bool): Include diarization cost.
            enable_summarization (bool): Include summarization cost.

        Returns:
            Decimal: Estimated cost in USD.
        """
        duration_minutes = Decimal(str(duration_seconds / 60))
        cost = DEEPGRAM_COST_PER_MINUTE_BASE * duration_minutes

        if enable_diarization:
            cost += DEEPGRAM_COST_PER_MINUTE_DIARIZATION * duration_minutes
        if enable_summarization:
            cost += DEEPGRAM_COST_PER_MINUTE_SUMMARIZATION * duration_minutes

        return cost.quantize(Decimal("0.0001"))
