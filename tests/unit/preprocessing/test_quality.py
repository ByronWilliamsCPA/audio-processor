"""Unit tests for `audio_processor.preprocessing.quality`."""

from __future__ import annotations

import math

import numpy as np
import pytest

from audio_processor.preprocessing.quality import check_clipping, check_snr


@pytest.mark.unit
def test_check_snr_clean_tone_is_high() -> None:
    """A clean sine wave produces a large positive SNR."""
    sr = 16_000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    tone = 0.5 * np.sin(2 * np.pi * 440.0 * t)

    snr_db = check_snr(tone.astype(np.float32))

    assert snr_db > 20.0


@pytest.mark.unit
def test_check_snr_silent_input_returns_neg_inf() -> None:
    """All-zero input has no signal energy and returns -inf."""
    audio = np.zeros(1_000, dtype=np.float32)
    assert check_snr(audio) == float("-inf")


@pytest.mark.unit
def test_check_snr_empty_input_returns_neg_inf() -> None:
    """Empty input returns -inf rather than raising."""
    assert check_snr(np.array([], dtype=np.float32)) == float("-inf")


@pytest.mark.unit
def test_check_snr_returns_finite_for_noisy_signal() -> None:
    """A sine tone plus broadband noise yields a finite, lower SNR."""
    rng = np.random.default_rng(seed=0)
    sr = 16_000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    tone = 0.5 * np.sin(2 * np.pi * 440.0 * t)
    noise = rng.normal(scale=0.1, size=sr)
    noisy = (tone + noise).astype(np.float32)

    snr_db = check_snr(noisy)

    assert math.isfinite(snr_db)


@pytest.mark.unit
def test_check_clipping_detects_peak_above_threshold() -> None:
    """A single sample above the threshold trips the detector."""
    audio = np.array([0.1, -0.2, 0.995, 0.0], dtype=np.float32)
    assert check_clipping(audio, threshold=0.99) is True


@pytest.mark.unit
def test_check_clipping_returns_false_below_threshold() -> None:
    """Samples strictly at or below the threshold do not trip the detector."""
    audio = np.array([0.5, -0.99, 0.99, -0.5], dtype=np.float32)
    assert check_clipping(audio, threshold=0.99) is False


@pytest.mark.unit
def test_check_clipping_empty_input_is_false() -> None:
    """Empty input is reported as not-clipping (no samples to exceed)."""
    assert check_clipping(np.array([], dtype=np.float32)) is False
