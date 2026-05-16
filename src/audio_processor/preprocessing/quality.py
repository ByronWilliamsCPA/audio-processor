"""Audio quality checks (Sprint 4).

Lightweight signal-quality metrics used to flag problematic recordings
before downstream ASR. Provides:

* :func:`check_snr` - estimate signal-to-noise ratio in dB.
* :func:`check_clipping` - flag clipped samples above a peak threshold.
"""

from __future__ import annotations

import numpy as np
from scipy import signal as scipy_signal

# Floor used when the noise estimate is zero (e.g. perfectly silent
# segments) to avoid divide-by-zero / log(0) blowups while still returning
# a finite, very-high SNR value.
_NOISE_FLOOR: float = 1e-12


def check_snr(audio: np.ndarray) -> float:
    """Estimate the signal-to-noise ratio of ``audio`` in decibels.

    The signal envelope is approximated by a 4th-order Butterworth
    low-pass filter (``scipy.signal``) cut at the Nyquist quarter; the
    high-frequency residual after subtracting the envelope is treated as
    noise. The returned value is ``10 * log10(P_signal / P_noise)``.

    Args:
        audio: 1-D floating-point mono audio array. An empty or all-zero
            array returns ``-inf``.

    Returns:
        SNR estimate in dB. Returns ``float('inf')`` when the residual
        noise power is below the internal floor (i.e. effectively
        noise-free signal), and ``float('-inf')`` when there is no signal.
    """
    if audio.size == 0:
        return float("-inf")

    samples = np.asarray(audio, dtype=np.float64)
    signal_power = float(np.mean(samples**2))
    if signal_power <= _NOISE_FLOOR:
        return float("-inf")

    # 4th-order Butterworth low-pass at Nyquist/2 (i.e. half the
    # representable bandwidth) approximates the slow-varying signal
    # envelope; the residual captures broadband noise.
    sos = scipy_signal.butter(N=4, Wn=0.5, btype="low", output="sos")
    envelope = scipy_signal.sosfiltfilt(sos, samples)
    noise = samples - envelope
    noise_power = float(np.mean(noise**2))

    if noise_power <= _NOISE_FLOOR:
        return float("inf")

    return float(10.0 * np.log10(signal_power / noise_power))


def check_clipping(audio: np.ndarray, threshold: float = 0.99) -> bool:
    """Return ``True`` if any sample's magnitude exceeds ``threshold``.

    Args:
        audio: 1-D floating-point mono audio array expected to be in the
            normalized range ``[-1.0, 1.0]``.
        threshold: Peak-magnitude threshold in the same units as ``audio``.
            Defaults to ``0.99`` to flag near-full-scale samples.

    Returns:
        ``True`` if at least one sample's absolute value strictly exceeds
        ``threshold``; ``False`` otherwise (including for empty arrays).
    """
    if audio.size == 0:
        return False
    return bool(np.any(np.abs(audio) > threshold))
