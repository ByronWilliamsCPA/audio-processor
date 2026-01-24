"""Voice Activity Detection (VAD) processor using Silero VAD.

This module provides voice activity detection for:
- Identifying speech segments in audio
- Removing silence to reduce processing costs
- Timeline reconstruction for accurate timestamps
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import soundfile as sf
import torch
from numpy.typing import NDArray

from audio_processor.core.config import settings
from audio_processor.core.exceptions import AudioProcessorError, ValidationError
from audio_processor.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Silero VAD requires 16kHz audio
SILERO_SAMPLE_RATE = 16000

# Type alias for audio samples
AudioSamples = NDArray[np.floating[np.float64]]


@dataclass(frozen=True)
class SpeechSegment:
    """A detected speech segment.

    Attributes:
        start: Start time in seconds.
        end: End time in seconds.
        confidence: Detection confidence (0.0-1.0).
    """

    start: float
    end: float
    confidence: float = 1.0

    @property
    def duration(self) -> float:
        """Duration of the segment in seconds."""
        return self.end - self.start


@dataclass(frozen=True)
class VADResult:
    """Result of Voice Activity Detection.

    Attributes:
        segments: List of detected speech segments.
        total_speech_duration: Total duration of speech in seconds.
        total_silence_duration: Total duration of silence in seconds.
        speech_ratio: Ratio of speech to total duration.
        original_duration: Original audio duration in seconds.
        processed_path: Path to processed audio (if silence removed).
        timeline_map: Mapping from processed time to original time.
    """

    segments: tuple[SpeechSegment, ...]
    total_speech_duration: float
    total_silence_duration: float
    speech_ratio: float
    original_duration: float
    processed_path: Path | None = None
    timeline_map: tuple[tuple[float, float], ...] | None = None


class VADProcessor:
    """Voice Activity Detection processor using Silero VAD.

    Uses the Silero VAD model (a neural network-based detector) to identify
    speech segments in audio. Can optionally remove silence sections to
    reduce transcription costs and improve accuracy.

    Example:
        >>> vad = VADProcessor()
        >>> result = vad.detect_speech("/path/to/audio.wav")
        >>> for segment in result.segments:
        ...     print(f"Speech: {segment.start:.2f}s - {segment.end:.2f}s")
        >>>
        >>> # Remove silence
        >>> result = vad.process_audio("/path/to/audio.wav", remove_silence=True)
        >>> print(f"Reduced from {result.original_duration}s to {result.total_speech_duration}s")
    """

    _model: torch.jit.ScriptModule | None = None
    _utils: tuple[object, ...] | None = None

    def __init__(
        self,
        threshold: float | None = None,
        min_silence_duration_ms: int | None = None,
        min_speech_duration_ms: int | None = None,
        temp_dir: str | None = None,
    ) -> None:
        """Initialize the VAD processor.

        Args:
            threshold: VAD threshold (0.0-1.0). Higher = stricter.
            min_silence_duration_ms: Minimum silence duration to detect.
            min_speech_duration_ms: Minimum speech duration to keep.
            temp_dir: Directory for temporary files.
        """
        self.threshold = threshold or settings.vad_threshold
        self.min_silence_duration_ms = min_silence_duration_ms or settings.vad_min_silence_duration_ms
        self.min_speech_duration_ms = min_speech_duration_ms or settings.vad_min_speech_duration_ms
        self.temp_dir = Path(temp_dir or settings.audio_temp_dir)

        # Ensure temp directory exists
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _load_model(self) -> tuple[torch.jit.ScriptModule, tuple[object, ...]]:
        """Load Silero VAD model (cached as class attribute).

        Returns:
            Tuple of (model, utils).
        """
        if VADProcessor._model is None:
            logger.info("loading_silero_vad_model")
            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True,
            )
            VADProcessor._model = model
            VADProcessor._utils = utils
            logger.info("silero_vad_model_loaded")

        return VADProcessor._model, VADProcessor._utils  # type: ignore[return-value]

    def detect_speech(
        self,
        input_path: str | Path,
    ) -> VADResult:
        """Detect speech segments in an audio file.

        Args:
            input_path: Path to the audio file (must be 16kHz mono WAV).

        Returns:
            VADResult with detected speech segments.

        Raises:
            ValidationError: If file doesn't exist.
            AudioProcessorError: If VAD processing fails.
        """
        input_path = Path(input_path)

        if not input_path.exists():
            msg = f"Audio file not found: {input_path}"
            raise ValidationError(msg, field="input_path", value=str(input_path))

        logger.info("detecting_speech", input_path=str(input_path))

        try:
            # Load audio
            audio, sample_rate = sf.read(str(input_path), dtype="float32")

            # Ensure mono
            if audio.ndim > 1:
                audio = np.mean(audio, axis=1)

            # Resample to 16kHz if needed (Silero requirement)
            if sample_rate != SILERO_SAMPLE_RATE:
                import librosa

                audio = librosa.resample(
                    audio.astype(np.float64),
                    orig_sr=sample_rate,
                    target_sr=SILERO_SAMPLE_RATE,
                ).astype(np.float32)
                sample_rate = SILERO_SAMPLE_RATE

            original_duration = len(audio) / sample_rate

            # Load model
            model, utils = self._load_model()
            get_speech_timestamps = utils[0]

            # Convert to torch tensor
            audio_tensor = torch.from_numpy(audio)

            # Run VAD
            speech_timestamps = get_speech_timestamps(
                audio_tensor,
                model,
                threshold=self.threshold,
                min_silence_duration_ms=self.min_silence_duration_ms,
                min_speech_duration_ms=self.min_speech_duration_ms,
                sampling_rate=SILERO_SAMPLE_RATE,
            )

            # Convert to SpeechSegments
            segments: list[SpeechSegment] = []
            for ts in speech_timestamps:
                start = ts["start"] / SILERO_SAMPLE_RATE
                end = ts["end"] / SILERO_SAMPLE_RATE
                segments.append(SpeechSegment(start=start, end=end))

            # Calculate statistics
            total_speech = sum(s.duration for s in segments)
            total_silence = original_duration - total_speech
            speech_ratio = total_speech / original_duration if original_duration > 0 else 0.0

            logger.info(
                "speech_detected",
                input_path=str(input_path),
                segments_count=len(segments),
                speech_duration=round(total_speech, 2),
                speech_ratio=round(speech_ratio, 3),
            )

            return VADResult(
                segments=tuple(segments),
                total_speech_duration=total_speech,
                total_silence_duration=total_silence,
                speech_ratio=speech_ratio,
                original_duration=original_duration,
            )

        except Exception as e:
            msg = f"VAD processing failed: {e}"
            raise AudioProcessorError(msg, operation="vad") from e

    def process_audio(
        self,
        input_path: str | Path,
        output_path: str | Path | None = None,
        *,
        remove_silence: bool = True,
        padding_ms: int = 100,
    ) -> VADResult:
        """Process audio with VAD, optionally removing silence.

        Args:
            input_path: Path to the input audio file.
            output_path: Optional output path. If None, creates temp file.
            remove_silence: Whether to remove silence sections.
            padding_ms: Padding to add around speech segments.

        Returns:
            VADResult with processed audio path and timeline map.

        Raises:
            ValidationError: If file doesn't exist.
            AudioProcessorError: If processing fails.
        """
        input_path = Path(input_path)

        if not input_path.exists():
            msg = f"Audio file not found: {input_path}"
            raise ValidationError(msg, field="input_path", value=str(input_path))

        # First detect speech
        result = self.detect_speech(input_path)

        if not remove_silence or not result.segments:
            return result

        logger.info(
            "removing_silence",
            input_path=str(input_path),
            segments_count=len(result.segments),
        )

        try:
            # Load audio
            audio, sample_rate = sf.read(str(input_path), dtype="float64")

            # Ensure mono
            if audio.ndim > 1:
                audio = np.mean(audio, axis=1)

            # Calculate padding in samples
            padding_samples = int(padding_ms * sample_rate / 1000)

            # Extract speech segments with padding
            speech_chunks: list[AudioSamples] = []
            timeline_map: list[tuple[float, float]] = []
            current_output_time = 0.0

            for segment in result.segments:
                # Convert to samples with padding
                start_sample = max(0, int(segment.start * sample_rate) - padding_samples)
                end_sample = min(len(audio), int(segment.end * sample_rate) + padding_samples)

                chunk = audio[start_sample:end_sample]
                speech_chunks.append(chunk)

                # Track timeline mapping (output_time -> original_time)
                original_start = start_sample / sample_rate
                chunk_duration = len(chunk) / sample_rate
                timeline_map.append((current_output_time, original_start))
                current_output_time += chunk_duration

            # Concatenate speech chunks
            if speech_chunks:
                processed_audio = np.concatenate(speech_chunks)
            else:
                processed_audio = np.array([], dtype=np.float64)

            # Write output file
            if output_path is None:
                temp_file = tempfile.NamedTemporaryFile(
                    suffix=".wav",
                    dir=self.temp_dir,
                    delete=False,
                )
                output_path = Path(temp_file.name)
                temp_file.close()
            else:
                output_path = Path(output_path)

            sf.write(str(output_path), processed_audio, sample_rate, subtype="PCM_16")

            # Recalculate durations
            processed_duration = len(processed_audio) / sample_rate
            silence_removed = result.original_duration - processed_duration

            logger.info(
                "silence_removed",
                input_path=str(input_path),
                output_path=str(output_path),
                original_duration=round(result.original_duration, 2),
                processed_duration=round(processed_duration, 2),
                silence_removed=round(silence_removed, 2),
            )

            return VADResult(
                segments=result.segments,
                total_speech_duration=processed_duration,
                total_silence_duration=silence_removed,
                speech_ratio=result.speech_ratio,
                original_duration=result.original_duration,
                processed_path=output_path,
                timeline_map=tuple(timeline_map),
            )

        except Exception as e:
            msg = f"Failed to process audio with VAD: {e}"
            raise AudioProcessorError(msg, operation="vad_processing") from e

    def map_timestamp(
        self,
        processed_time: float,
        timeline_map: tuple[tuple[float, float], ...],
    ) -> float:
        """Map a timestamp from processed audio to original audio.

        Used to reconstruct original timestamps after silence removal.

        Args:
            processed_time: Timestamp in the processed (silence-removed) audio.
            timeline_map: Timeline mapping from VADResult.

        Returns:
            Corresponding timestamp in the original audio.
        """
        if not timeline_map:
            return processed_time

        # Find the segment this timestamp belongs to
        for i, (output_start, original_start) in enumerate(timeline_map):
            # Check if this is the last segment or if we're before the next
            if i == len(timeline_map) - 1:
                # Last segment
                offset = processed_time - output_start
                return original_start + offset

            next_output_start = timeline_map[i + 1][0]
            if processed_time < next_output_start:
                # In this segment
                offset = processed_time - output_start
                return original_start + offset

        # Fallback (shouldn't reach here)
        return processed_time

    def should_process(
        self,
        input_path: str | Path,
        min_silence_ratio: float = 0.3,
    ) -> bool:
        """Determine if VAD processing would be beneficial.

        Args:
            input_path: Path to the audio file.
            min_silence_ratio: Minimum silence ratio to consider processing.

        Returns:
            True if VAD processing is recommended.
        """
        try:
            result = self.detect_speech(input_path)
            silence_ratio = 1.0 - result.speech_ratio
            return silence_ratio >= min_silence_ratio
        except (ValidationError, AudioProcessorError):
            return False
