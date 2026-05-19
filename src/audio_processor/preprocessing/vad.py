"""Silero VAD wrapper for speech-segment detection (Sprint 3).

Loads the Silero VAD model lazily via ``torch.hub`` and exposes a single
``detect_speech_segments`` helper that returns the list of speech
intervals in ``(start_seconds, end_seconds)`` form.

The model is downloaded and cached by ``torch.hub`` on first use; later
calls reuse the cached weights.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, Final, cast

import torch

if TYPE_CHECKING:
    import numpy as np

SILERO_REPO: Final[str] = "snakers4/silero-vad"
SILERO_MODEL: Final[str] = "silero_vad"

_model_lock = threading.Lock()
_cached_model: Any = None
_cached_utils: Any = None


def _load_silero_vad() -> tuple[Any, Any]:
    """Lazily load and cache the Silero VAD model and helper utilities.

    Returns:
        Tuple ``(model, utils)`` where ``model`` is the loaded Silero VAD
        torch module and ``utils`` is the helper tuple returned by
        ``torch.hub.load`` (containing ``get_speech_timestamps`` and
        related helpers).
    """
    global _cached_model, _cached_utils
    if _cached_model is not None and _cached_utils is not None:
        return _cached_model, _cached_utils

    with _model_lock:
        if _cached_model is None or _cached_utils is None:
            loaded = cast(
                "tuple[Any, tuple[Any, ...]]",
                # Pinned Silero VAD model; trust_repo=True is the intentional
                # design choice per PR description and task spec.
                torch.hub.load(  # nosec B614
                    repo_or_dir=SILERO_REPO,
                    model=SILERO_MODEL,
                    trust_repo=True,
                ),
            )
            _cached_model, _cached_utils = loaded
    return _cached_model, _cached_utils


def detect_speech_segments(
    audio: np.ndarray,
    sample_rate: int,
) -> list[tuple[float, float]]:
    """Detect speech segments in mono audio using Silero VAD.

    Args:
        audio: 1-D mono audio array of floating-point samples in the range
            ``[-1.0, 1.0]``. Silero VAD natively supports 8 kHz and 16 kHz
            sample rates; 16 kHz is recommended.
        sample_rate: Sample rate of ``audio`` in Hz.

    Returns:
        Ordered list of ``(start_seconds, end_seconds)`` tuples describing
        the detected speech intervals. Returns an empty list if no speech
        is detected.
    """
    model, utils = _load_silero_vad()
    # Silero's `utils` is a tuple; `get_speech_timestamps` is the first
    # element by convention.
    get_speech_timestamps = utils[0]

    tensor = torch.as_tensor(audio, dtype=torch.float32)
    timestamps: list[dict[str, int]] = get_speech_timestamps(
        tensor,
        model,
        sampling_rate=sample_rate,
    )

    return [(ts["start"] / sample_rate, ts["end"] / sample_rate) for ts in timestamps]
