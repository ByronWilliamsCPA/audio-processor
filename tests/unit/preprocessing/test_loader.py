"""Unit tests for `audio_processor.preprocessing.loader.load_audio`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest
import soundfile as sf

from audio_processor.exceptions import AudioLoadError
from audio_processor.preprocessing.loader import TARGET_SAMPLE_RATE, load_audio

if TYPE_CHECKING:
    from pathlib import Path


def _write_wav(path: Path, sample_rate: int, duration_s: float = 0.5) -> np.ndarray:
    """Write a synthetic stereo sine wave WAV and return the raw samples."""
    t = np.linspace(0.0, duration_s, int(sample_rate * duration_s), endpoint=False)
    left = 0.5 * np.sin(2 * np.pi * 440.0 * t)
    right = 0.5 * np.sin(2 * np.pi * 880.0 * t)
    samples = np.stack([left, right], axis=1).astype(np.float32)
    sf.write(str(path), samples, sample_rate, subtype="PCM_16")
    return samples


@pytest.mark.unit
def test_load_audio_resamples_to_target_and_mono(tmp_path: Path) -> None:
    """A 44.1 kHz stereo WAV loads as mono at 16 kHz."""
    src = tmp_path / "sample.wav"
    _write_wav(src, sample_rate=44_100, duration_s=0.25)

    audio, sample_rate = load_audio(src)

    assert sample_rate == TARGET_SAMPLE_RATE
    assert audio.ndim == 1
    assert audio.dtype == np.float32
    # 0.25 s @ 16 kHz = 4000 samples (resampler may be off by a handful).
    assert abs(audio.shape[0] - 4_000) <= 8


@pytest.mark.unit
def test_load_audio_passthrough_when_already_16k_mono(tmp_path: Path) -> None:
    """A mono 16 kHz file is returned without resampling artifacts."""
    src = tmp_path / "mono16k.wav"
    sr = TARGET_SAMPLE_RATE
    samples = (0.25 * np.sin(np.linspace(0, 2 * np.pi, sr))).astype(np.float32)
    sf.write(str(src), samples, sr, subtype="PCM_16")

    audio, sample_rate = load_audio(src)

    assert sample_rate == TARGET_SAMPLE_RATE
    assert audio.shape == samples.shape


@pytest.mark.unit
def test_load_audio_rejects_unsupported_suffix(tmp_path: Path) -> None:
    """Suffixes outside the allow-list raise AudioLoadError before I/O."""
    bogus = tmp_path / "clip.xyz"
    bogus.write_bytes(b"\x00\x00")

    with pytest.raises(AudioLoadError) as exc_info:
        load_audio(bogus)

    assert ".xyz" in str(exc_info.value)


@pytest.mark.unit
def test_load_audio_raises_on_corrupt_file(tmp_path: Path) -> None:
    """A file with a supported suffix but garbage contents raises."""
    corrupt = tmp_path / "corrupt.wav"
    corrupt.write_bytes(b"not a real wav file")

    with pytest.raises(AudioLoadError):
        load_audio(corrupt)
