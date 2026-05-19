"""Audio loading and format normalization (Sprint 1).

Loads audio files from disk, converts multi-channel audio to mono, and
resamples to the canonical 16 kHz sample rate used by downstream
preprocessing stages (VAD, quality assessment, ASR).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import librosa
import numpy as np
import soundfile as sf

from audio_processor.exceptions import AudioLoadError

if TYPE_CHECKING:
    from pathlib import Path

TARGET_SAMPLE_RATE: Final[int] = 16_000
SUPPORTED_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".wav", ".mp3", ".flac", ".ogg"},
)


def load_audio(path: Path) -> tuple[np.ndarray, int]:
    """Load an audio file, convert to mono, and resample to 16 kHz.

    Reads the file with ``soundfile`` for efficient PCM decoding and falls
    back to ``librosa`` for compressed formats (e.g. MP3) that soundfile
    cannot always decode. Multi-channel input is averaged to mono.
    Resampling uses librosa's polyphase resampler.

    Args:
        path: Filesystem path to the audio file. The suffix must be one of
            ``.wav``, ``.mp3``, ``.flac``, or ``.ogg``.

    Returns:
        Tuple ``(audio, sample_rate)`` where ``audio`` is a 1-D ``float32``
        numpy array of mono samples and ``sample_rate`` is always
        ``TARGET_SAMPLE_RATE`` (16_000).

    Raises:
        AudioLoadError: If the file suffix is unsupported, the file is
            missing, or the underlying decoder fails on a corrupt file.
    """
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        msg = f"Unsupported audio format: {suffix!r}"
        raise AudioLoadError(
            msg,
            details={
                "path": str(path),
                "suffix": suffix,
                "supported": ", ".join(sorted(SUPPORTED_SUFFIXES)),
            },
        )

    try:
        audio, sample_rate = _read_samples(path, suffix)
    except AudioLoadError:
        raise
    except (OSError, ValueError, RuntimeError) as exc:
        msg = f"Failed to load audio file: {path}"
        raise AudioLoadError(
            msg,
            details={"path": str(path), "reason": str(exc)},
        ) from exc

    mono = _to_mono(audio)
    resampled = _resample(mono, sample_rate, TARGET_SAMPLE_RATE)
    return resampled.astype(np.float32, copy=False), TARGET_SAMPLE_RATE


def _read_samples(path: Path, suffix: str) -> tuple[np.ndarray, int]:
    """Read raw samples from disk, choosing a decoder based on suffix.

    Args:
        path: Filesystem path to the audio file.
        suffix: Lowercase file extension (including the leading dot).

    Returns:
        Tuple ``(samples, sample_rate)`` where ``samples`` may be either
        1-D (mono) or 2-D (frames x channels) ``float`` numpy array.
        Decoder errors propagate to the caller, which wraps them as
        ``AudioLoadError``.
    """
    # soundfile handles WAV/FLAC/OGG natively; librosa (audioread/ffmpeg)
    # is required for MP3 on most platforms.
    if suffix == ".mp3":
        samples, sample_rate = librosa.load(str(path), sr=None, mono=False)
        # librosa returns (channels, frames) for multi-channel; transpose to
        # (frames, channels) to match soundfile's convention.
        if samples.ndim == 2:
            samples = samples.T
        return samples, int(sample_rate)

    samples, sample_rate = sf.read(str(path), always_2d=False)
    return samples, int(sample_rate)


def _to_mono(audio: np.ndarray) -> np.ndarray:
    """Collapse a multi-channel array to mono by averaging channels.

    Args:
        audio: Either a 1-D array of mono samples or a 2-D array shaped
            ``(frames, channels)``.

    Returns:
        1-D ``float`` numpy array of mono samples.
    """
    if audio.ndim == 1:
        return audio
    return audio.mean(axis=1)


def _resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample mono audio to the target sample rate.

    Args:
        audio: 1-D mono audio array.
        orig_sr: Original sample rate in Hz.
        target_sr: Desired output sample rate in Hz.

    Returns:
        Resampled 1-D audio array. If ``orig_sr == target_sr`` the input is
        returned unchanged.
    """
    if orig_sr == target_sr:
        return audio
    return librosa.resample(audio, orig_sr=orig_sr, target_sr=target_sr)
