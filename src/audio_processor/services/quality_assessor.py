"""Audio quality assessment service.

This module provides quality analysis for audio files including:
- Signal-to-Noise Ratio (SNR) calculation
- Silence detection and ratio
- Clipping detection
- Composite quality scoring
"""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from numpy.typing import NDArray

from audio_processor.core.config import settings
from audio_processor.core.exceptions import AudioProcessorError, ValidationError
from audio_processor.core.models import AudioQualityMetrics, QualityLevel
from audio_processor.utils.logging import get_logger

logger = get_logger(__name__)

# Type alias for audio samples
AudioSamples = NDArray[np.float64]


class QualityAssessor:
    """Audio quality assessment service.

    Analyzes audio files to assess quality metrics that may impact
    transcription accuracy. Provides SNR, silence ratio, clipping
    detection, and composite quality scoring.

    Args:
        snr_excellent_db (float | None): SNR threshold for excellent quality.
        snr_good_db (float | None): SNR threshold for good quality.
        snr_fair_db (float | None): SNR threshold for fair quality.
        max_silence_ratio (float | None): Maximum acceptable silence ratio.
        max_clipping_ratio (float | None): Maximum acceptable clipping ratio.

    Example:
        >>> assessor = QualityAssessor()
        >>> metrics = assessor.assess("/path/to/audio.wav")
        >>> print(f"Quality: {metrics.quality_level}")
        >>> if metrics.warnings:
        ...     print(f"Warnings: {metrics.warnings}")
    """

    def __init__(
        self,
        snr_excellent_db: float | None = None,
        snr_good_db: float | None = None,
        snr_fair_db: float | None = None,
        max_silence_ratio: float | None = None,
        max_clipping_ratio: float | None = None,
    ) -> None:
        self.snr_excellent_db = snr_excellent_db or settings.quality_snr_excellent_db
        self.snr_good_db = snr_good_db or settings.quality_snr_good_db
        self.snr_fair_db = snr_fair_db or settings.quality_snr_fair_db
        self.max_silence_ratio = max_silence_ratio or settings.quality_max_silence_ratio
        self.max_clipping_ratio = (
            max_clipping_ratio or settings.quality_max_clipping_ratio
        )

    def assess(self, file_path: str | Path) -> AudioQualityMetrics:
        """Assess audio quality of a file.

        Args:
            file_path (str | Path): Path to the audio file.

        Returns:
            AudioQualityMetrics: AudioQualityMetrics with quality assessment results.

        Raises:
            ValidationError: If the file doesn't exist or can't be read.
            AudioProcessorError: If quality assessment fails.
        """
        file_path = Path(file_path)

        if not file_path.exists():
            msg = f"File not found: {file_path}"
            raise ValidationError(msg, field="file_path", value=str(file_path))

        logger.info("assessing_audio_quality", file_path=str(file_path))

        try:
            # Load audio file
            audio, sample_rate = self._load_audio(file_path)

            # Calculate metrics
            duration = len(audio) / sample_rate
            channels = 1 if audio.ndim == 1 else audio.shape[1]

            # Ensure mono for analysis
            if audio.ndim > 1:
                audio = np.mean(audio, axis=1)

            # Calculate individual metrics
            snr_db = self._calculate_snr(audio)
            silence_ratio = self._calculate_silence_ratio(audio, sample_rate)
            clipping_ratio = self._calculate_clipping_ratio(audio)
            peak_amplitude = float(np.max(np.abs(audio)))
            rms_level_db = self._calculate_rms_db(audio)

            # Calculate composite quality score
            quality_score = self._calculate_quality_score(
                snr_db=snr_db,
                silence_ratio=silence_ratio,
                clipping_ratio=clipping_ratio,
            )

            # Determine quality level
            quality_level = self._determine_quality_level(snr_db, quality_score)

            # Generate warnings
            warnings = self._generate_warnings(
                snr_db=snr_db,
                silence_ratio=silence_ratio,
                clipping_ratio=clipping_ratio,
                peak_amplitude=peak_amplitude,
            )

            metrics = AudioQualityMetrics(
                snr_db=snr_db,
                silence_ratio=silence_ratio,
                clipping_ratio=clipping_ratio,
                peak_amplitude=peak_amplitude,
                rms_level_db=rms_level_db,
                duration_seconds=duration,
                sample_rate=sample_rate,
                channels=channels,
                quality_score=quality_score,
                quality_level=quality_level,
                warnings=tuple(warnings),
            )

            logger.info(
                "audio_quality_assessed",
                file_path=str(file_path),
                quality_level=quality_level.value,
                quality_score=round(quality_score, 3),
                snr_db=round(snr_db, 1),
            )

        except (OSError, RuntimeError) as e:
            msg = f"Failed to assess audio quality: {e}"
            raise AudioProcessorError(msg, operation="quality_assessment") from e

        else:
            return metrics

    def _load_audio(self, file_path: Path) -> tuple[AudioSamples, int]:
        """Load audio file using soundfile.

        Args:
            file_path (Path): Path to the audio file.

        Returns:
            tuple[AudioSamples, int]: Tuple of (audio samples, sample rate).
        """
        try:
            audio, sample_rate = sf.read(str(file_path), dtype="float64")
        except RuntimeError:
            # Fall back to librosa for formats soundfile doesn't support
            audio, sample_rate = librosa.load(str(file_path), sr=None, mono=False)
            # Transpose if stereo (librosa returns [channels, samples])
            if audio.ndim > 1:
                audio = audio.T
        return audio, int(sample_rate)  # pyright: ignore[reportReturnType]

    def _calculate_snr(self, audio: AudioSamples) -> float:
        """Calculate Signal-to-Noise Ratio using spectral method.

        Uses a simplified approach: estimate noise from the quietest
        portions of the signal.

        Args:
            audio (AudioSamples): Audio samples (mono).

        Returns:
            float: SNR in decibels.
        """
        # Calculate frame-level energy
        frame_length = 2048
        hop_length = 512

        # Compute short-term energy
        frames = librosa.util.frame(
            audio, frame_length=frame_length, hop_length=hop_length
        )
        frame_energy = np.sum(frames**2, axis=0)

        if len(frame_energy) == 0:
            return 0.0

        # Sort energies
        sorted_energy = np.sort(frame_energy)

        # Estimate noise from bottom 10% of frames
        noise_percentile = 10
        noise_idx = max(1, len(sorted_energy) * noise_percentile // 100)
        noise_energy = np.mean(sorted_energy[:noise_idx])

        # Signal energy from top 50% of frames
        signal_percentile = 50
        signal_idx = len(sorted_energy) * signal_percentile // 100
        signal_energy = np.mean(sorted_energy[signal_idx:])

        # Calculate SNR
        if noise_energy > 0:
            snr = 10 * np.log10(signal_energy / noise_energy)
            return float(np.clip(snr, -10, 60))  # Reasonable bounds
        return 60.0  # Very clean signal (or silent)

    def _calculate_silence_ratio(
        self,
        audio: AudioSamples,
        sample_rate: int,
        threshold_db: float = -40.0,
        frame_ms: float = 25.0,
    ) -> float:
        """Calculate the ratio of silence in the audio.

        Args:
            audio (AudioSamples): Audio samples (mono).
            sample_rate (int): Sample rate in Hz.
            threshold_db (float): Silence threshold in dB below peak.
            frame_ms (float): Frame size in milliseconds.

        Returns:
            float: Ratio of silent frames (0.0 to 1.0).
        """
        frame_length = int(sample_rate * frame_ms / 1000)
        hop_length = frame_length // 2

        # Compute RMS energy per frame
        rms = librosa.feature.rms(
            y=audio,
            frame_length=frame_length,
            hop_length=hop_length,
        )[0]

        if len(rms) == 0:
            return 0.0

        # Convert threshold to linear
        peak_rms = np.max(rms)
        if peak_rms == 0:
            return 1.0  # All silence

        threshold_linear = peak_rms * (10 ** (threshold_db / 20))

        # Count silent frames
        silent_frames = np.sum(rms < threshold_linear)
        return float(silent_frames / len(rms))

    def _calculate_clipping_ratio(
        self,
        audio: AudioSamples,
        threshold: float = 0.99,
    ) -> float:
        """Calculate the ratio of clipped samples.

        Args:
            audio (AudioSamples): Audio samples (mono), normalized to [-1, 1].
            threshold (float): Amplitude threshold for clipping detection.

        Returns:
            float: Ratio of clipped samples (0.0 to 1.0).
        """
        if len(audio) == 0:
            return 0.0

        clipped_samples = np.sum(np.abs(audio) >= threshold)
        return float(clipped_samples / len(audio))

    def _calculate_rms_db(self, audio: AudioSamples) -> float:
        """Calculate RMS level in dBFS.

        Args:
            audio (AudioSamples): Audio samples (mono).

        Returns:
            float: RMS level in decibels (dBFS).
        """
        rms = np.sqrt(np.mean(audio**2))
        if rms > 0:
            return float(20 * np.log10(rms))
        return -96.0  # Silence floor

    def _calculate_quality_score(
        self,
        snr_db: float,
        silence_ratio: float,
        clipping_ratio: float,
    ) -> float:
        """Calculate composite quality score.

        Combines multiple metrics into a single 0.0-1.0 score.

        Args:
            snr_db (float): Signal-to-noise ratio in dB.
            silence_ratio (float): Ratio of silence (0.0-1.0).
            clipping_ratio (float): Ratio of clipped samples (0.0-1.0).

        Returns:
            float: Quality score from 0.0 (worst) to 1.0 (best).
        """
        # SNR score (0-1): Maps 0-30dB to 0-1
        snr_score = np.clip(snr_db / 30.0, 0.0, 1.0)

        # Silence penalty: High silence reduces score
        silence_penalty = 1.0 - np.clip(silence_ratio / 0.8, 0.0, 1.0)

        # Clipping penalty: Any clipping is bad
        clipping_penalty = 1.0 - np.clip(clipping_ratio / 0.05, 0.0, 1.0)

        # Weighted combination
        # SNR is most important for transcription quality
        score = 0.5 * snr_score + 0.3 * silence_penalty + 0.2 * clipping_penalty

        return float(np.clip(score, 0.0, 1.0))

    def _determine_quality_level(
        self,
        snr_db: float,
        quality_score: float,
    ) -> QualityLevel:
        """Determine qualitative quality level.

        Args:
            snr_db (float): Signal-to-noise ratio in dB.
            quality_score (float): Composite quality score.

        Returns:
            QualityLevel: QualityLevel enum value.
        """
        if snr_db >= self.snr_excellent_db and quality_score >= 0.8:
            return QualityLevel.EXCELLENT
        if snr_db >= self.snr_good_db and quality_score >= 0.6:
            return QualityLevel.GOOD
        if snr_db >= self.snr_fair_db and quality_score >= 0.4:
            return QualityLevel.FAIR
        return QualityLevel.POOR

    def _generate_warnings(
        self,
        snr_db: float,
        silence_ratio: float,
        clipping_ratio: float,
        peak_amplitude: float,
    ) -> list[str]:
        """Generate quality warnings for the audio.

        Args:
            snr_db (float): Signal-to-noise ratio in dB.
            silence_ratio (float): Ratio of silence.
            clipping_ratio (float): Ratio of clipped samples.
            peak_amplitude (float): Maximum amplitude.

        Returns:
            list[str]: List of warning messages.
        """
        warnings: list[str] = []

        # Low SNR warning
        if snr_db < self.snr_fair_db:
            warnings.append(
                f"Low signal-to-noise ratio ({snr_db:.1f} dB). "
                "Transcription accuracy may be reduced."
            )

        # High silence warning
        if silence_ratio > self.max_silence_ratio:
            warnings.append(
                f"High silence ratio ({silence_ratio:.1%}). "
                "Consider trimming silent sections for cost savings."
            )

        # Clipping warning
        if clipping_ratio > self.max_clipping_ratio:
            warnings.append(
                f"Audio clipping detected ({clipping_ratio:.2%} of samples). "
                "This may impact transcription quality."
            )

        # Low level warning
        if peak_amplitude < 0.1:
            warnings.append(
                "Very low audio level detected. "
                "Consider increasing gain before processing."
            )

        return warnings
