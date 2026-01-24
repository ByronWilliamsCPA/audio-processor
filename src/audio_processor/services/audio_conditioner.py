"""Audio signal conditioning service.

This module provides audio preprocessing to optimize transcription quality:
- Resampling to target sample rate (16kHz for ASR)
- Mono conversion for consistent processing
- RMS normalization for consistent volume levels
- DC offset removal
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from numpy.typing import NDArray

from audio_processor.core.config import settings
from audio_processor.core.exceptions import AudioProcessorError, ValidationError
from audio_processor.utils.logging import get_logger

logger = get_logger(__name__)

# Type alias for audio samples
AudioSamples = NDArray[np.floating[np.float64]]


@dataclass(frozen=True)
class ConditioningResult:
    """Result of audio conditioning.

    Attributes:
        output_path: Path to the conditioned audio file.
        original_sample_rate: Original sample rate in Hz.
        target_sample_rate: Target sample rate in Hz.
        original_channels: Original number of channels.
        original_duration: Original duration in seconds.
        output_duration: Output duration in seconds.
        original_rms_db: Original RMS level in dBFS.
        output_rms_db: Output RMS level in dBFS.
        gain_applied_db: Gain applied during normalization.
        dc_offset_removed: Whether DC offset was removed.
    """

    output_path: Path
    original_sample_rate: int
    target_sample_rate: int
    original_channels: int
    original_duration: float
    output_duration: float
    original_rms_db: float
    output_rms_db: float
    gain_applied_db: float
    dc_offset_removed: bool


class AudioConditioner:
    """Audio signal conditioning for optimal ASR processing.

    Prepares audio files for transcription by:
    1. Resampling to target rate (default 16kHz)
    2. Converting to mono
    3. Removing DC offset
    4. Normalizing RMS level

    These preprocessing steps can improve Word Error Rate (WER) by 10-20%
    for challenging audio.

    Example:
        >>> conditioner = AudioConditioner()
        >>> result = conditioner.condition("/path/to/audio.wav")
        >>> print(f"Conditioned: {result.output_path}")
        >>> print(f"Gain applied: {result.gain_applied_db:.1f} dB")
    """

    def __init__(
        self,
        target_sample_rate: int | None = None,
        target_channels: int | None = None,
        target_rms_db: float | None = None,
        temp_dir: str | None = None,
    ) -> None:
        """Initialize the AudioConditioner.

        Args:
            target_sample_rate: Target sample rate in Hz. Defaults to 16000.
            target_channels: Target number of channels. Defaults to 1 (mono).
            target_rms_db: Target RMS level in dBFS. Defaults to -20.
            temp_dir: Directory for temporary files.
        """
        self.target_sample_rate = target_sample_rate or settings.audio_target_sample_rate
        self.target_channels = target_channels or settings.audio_target_channels
        self.target_rms_db = target_rms_db or settings.audio_target_rms_db
        self.temp_dir = Path(temp_dir or settings.audio_temp_dir)

        # Ensure temp directory exists
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def condition(
        self,
        input_path: str | Path,
        output_path: str | Path | None = None,
        *,
        resample: bool = True,
        to_mono: bool = True,
        normalize: bool = True,
        remove_dc: bool = True,
    ) -> ConditioningResult:
        """Condition an audio file for optimal ASR processing.

        Args:
            input_path: Path to the input audio file.
            output_path: Optional output path. If None, creates temp file.
            resample: Whether to resample to target rate.
            to_mono: Whether to convert to mono.
            normalize: Whether to normalize RMS level.
            remove_dc: Whether to remove DC offset.

        Returns:
            ConditioningResult with details about the conditioning.

        Raises:
            ValidationError: If input file doesn't exist.
            AudioProcessorError: If conditioning fails.
        """
        input_path = Path(input_path)

        if not input_path.exists():
            msg = f"Audio file not found: {input_path}"
            raise ValidationError(msg, field="input_path", value=str(input_path))

        logger.info(
            "conditioning_audio",
            input_path=str(input_path),
            resample=resample,
            to_mono=to_mono,
            normalize=normalize,
            remove_dc=remove_dc,
        )

        try:
            # Load audio file
            audio, original_sr = self._load_audio(input_path)
            original_channels = 1 if audio.ndim == 1 else audio.shape[1]
            original_duration = len(audio) / original_sr

            # Calculate original RMS
            if audio.ndim > 1:
                audio_mono_orig = np.mean(audio, axis=1)
            else:
                audio_mono_orig = audio
            original_rms_db = self._calculate_rms_db(audio_mono_orig)

            # Convert to mono if requested
            if to_mono and audio.ndim > 1:
                audio = np.mean(audio, axis=1)

            # Remove DC offset if requested
            dc_removed = False
            if remove_dc:
                dc_offset = np.mean(audio)
                if abs(dc_offset) > 1e-6:
                    audio = audio - dc_offset
                    dc_removed = True

            # Resample if requested and needed
            target_sr = self.target_sample_rate if resample else original_sr
            if resample and original_sr != target_sr:
                audio = librosa.resample(
                    audio,
                    orig_sr=original_sr,
                    target_sr=target_sr,
                )

            # Normalize RMS if requested
            gain_applied_db = 0.0
            if normalize:
                audio, gain_applied_db = self._normalize_rms(audio, self.target_rms_db)

            # Calculate output RMS
            output_rms_db = self._calculate_rms_db(audio)
            output_duration = len(audio) / target_sr

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

            # Write as 16-bit PCM WAV
            sf.write(str(output_path), audio, target_sr, subtype="PCM_16")

            logger.info(
                "audio_conditioned",
                input_path=str(input_path),
                output_path=str(output_path),
                original_sr=original_sr,
                target_sr=target_sr,
                gain_applied_db=round(gain_applied_db, 2),
            )

            return ConditioningResult(
                output_path=output_path,
                original_sample_rate=original_sr,
                target_sample_rate=target_sr,
                original_channels=original_channels,
                original_duration=original_duration,
                output_duration=output_duration,
                original_rms_db=original_rms_db,
                output_rms_db=output_rms_db,
                gain_applied_db=gain_applied_db,
                dc_offset_removed=dc_removed,
            )

        except (OSError, RuntimeError) as e:
            msg = f"Failed to condition audio: {e}"
            raise AudioProcessorError(msg, operation="conditioning") from e

    def _load_audio(self, file_path: Path) -> tuple[AudioSamples, int]:
        """Load audio file.

        Args:
            file_path: Path to the audio file.

        Returns:
            Tuple of (audio samples, sample rate).
        """
        try:
            # Try soundfile first (faster for WAV/FLAC)
            audio, sample_rate = sf.read(str(file_path), dtype="float64")
            return audio, sample_rate
        except RuntimeError:
            # Fall back to librosa for other formats
            audio, sample_rate = librosa.load(str(file_path), sr=None, mono=False)
            # Transpose if stereo (librosa returns [channels, samples])
            if audio.ndim > 1:
                audio = audio.T
            return audio, sample_rate

    def _calculate_rms_db(self, audio: AudioSamples) -> float:
        """Calculate RMS level in dBFS.

        Args:
            audio: Audio samples.

        Returns:
            RMS level in decibels (dBFS).
        """
        rms = np.sqrt(np.mean(audio**2))
        if rms > 0:
            return float(20 * np.log10(rms))
        return -96.0  # Silence floor

    def _normalize_rms(
        self,
        audio: AudioSamples,
        target_db: float,
    ) -> tuple[AudioSamples, float]:
        """Normalize audio to target RMS level.

        Args:
            audio: Input audio samples.
            target_db: Target RMS level in dBFS.

        Returns:
            Tuple of (normalized audio, gain applied in dB).
        """
        current_rms = np.sqrt(np.mean(audio**2))

        if current_rms < 1e-10:
            # Audio is essentially silent
            return audio, 0.0

        # Calculate target RMS in linear scale
        target_rms = 10 ** (target_db / 20)

        # Calculate gain
        gain = target_rms / current_rms
        gain_db = float(20 * np.log10(gain))

        # Apply gain with headroom protection
        normalized = audio * gain

        # Soft clip to prevent clipping (use tanh for smooth limiting)
        peak = np.max(np.abs(normalized))
        if peak > 0.99:
            # Apply soft limiting
            normalized = np.tanh(normalized * 2) / 2
            # Recalculate actual gain
            actual_rms = np.sqrt(np.mean(normalized**2))
            if actual_rms > 0:
                gain_db = float(20 * np.log10(actual_rms / current_rms))

        return normalized, gain_db

    def estimate_improvement(
        self,
        input_path: str | Path,
    ) -> dict[str, float | bool | str]:
        """Estimate potential improvement from conditioning.

        Analyzes audio to predict how much conditioning might help.

        Args:
            input_path: Path to the audio file.

        Returns:
            Dictionary with improvement estimates.
        """
        input_path = Path(input_path)

        if not input_path.exists():
            msg = f"Audio file not found: {input_path}"
            raise ValidationError(msg, field="input_path", value=str(input_path))

        try:
            audio, sample_rate = self._load_audio(input_path)

            # Get mono for analysis
            if audio.ndim > 1:
                audio_mono = np.mean(audio, axis=1)
            else:
                audio_mono = audio

            # Check sample rate
            needs_resample = sample_rate != self.target_sample_rate
            resample_benefit = "high" if sample_rate < 16000 else "low"

            # Check channels
            channels = 1 if audio.ndim == 1 else audio.shape[1]
            needs_mono = channels > 1

            # Check DC offset
            dc_offset = abs(float(np.mean(audio_mono)))
            needs_dc_removal = dc_offset > 0.01

            # Check RMS level
            current_rms_db = self._calculate_rms_db(audio_mono)
            level_diff = abs(current_rms_db - self.target_rms_db)
            needs_normalization = level_diff > 6.0  # More than 6dB off

            # Estimate overall benefit
            benefit_score = 0.0
            if needs_resample and sample_rate < 16000:
                benefit_score += 0.3
            if needs_mono:
                benefit_score += 0.1
            if needs_dc_removal:
                benefit_score += 0.1
            if needs_normalization:
                benefit_score += 0.2 * min(level_diff / 20, 1.0)

            # Estimate WER improvement
            estimated_wer_improvement = benefit_score * 0.15  # Up to 15% improvement

            return {
                "needs_resample": needs_resample,
                "current_sample_rate": sample_rate,
                "resample_benefit": resample_benefit,
                "needs_mono_conversion": needs_mono,
                "current_channels": channels,
                "needs_dc_removal": needs_dc_removal,
                "dc_offset": dc_offset,
                "needs_normalization": needs_normalization,
                "current_rms_db": round(current_rms_db, 1),
                "target_rms_db": self.target_rms_db,
                "estimated_wer_improvement_percent": round(estimated_wer_improvement * 100, 1),
            }

        except (OSError, RuntimeError) as e:
            msg = f"Failed to analyze audio: {e}"
            raise AudioProcessorError(msg, operation="analysis") from e
