"""Unit tests for `audio_processor.preprocessing.vad.detect_speech_segments`."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from audio_processor.preprocessing import vad as vad_module
from audio_processor.preprocessing.vad import detect_speech_segments


@pytest.fixture(autouse=True)
def _reset_vad_cache() -> None:
    """Ensure each test re-loads the (mocked) Silero model."""
    vad_module._cached_model = None
    vad_module._cached_utils = None


@pytest.mark.unit
def test_detect_speech_segments_returns_seconds() -> None:
    """Frame-index timestamps from Silero are converted to seconds."""
    sample_rate = 16_000
    audio = np.zeros(sample_rate, dtype=np.float32)

    fake_model = MagicMock(name="silero_model")
    # Silero's `utils` is a tuple whose first element is
    # `get_speech_timestamps`. Build a tuple of MagicMocks so indexing works.
    get_speech_timestamps = MagicMock(
        return_value=[
            {"start": 0, "end": 8_000},
            {"start": 8_000, "end": 16_000},
        ],
    )
    fake_utils = (get_speech_timestamps, MagicMock(), MagicMock(), MagicMock())

    with patch.object(
        vad_module.torch.hub,
        "load",
        return_value=(fake_model, fake_utils),
    ) as hub_load:
        segments = detect_speech_segments(audio, sample_rate)

    hub_load.assert_called_once()
    assert segments == [(0.0, 0.5), (0.5, 1.0)]
    # `get_speech_timestamps` receives the audio tensor and the sample rate.
    call_args = get_speech_timestamps.call_args
    assert call_args.kwargs["sampling_rate"] == sample_rate


@pytest.mark.unit
def test_detect_speech_segments_empty_when_no_speech() -> None:
    """An empty timestamps list from Silero yields an empty segments list."""
    sample_rate = 16_000
    audio = np.zeros(sample_rate, dtype=np.float32)

    get_speech_timestamps = MagicMock(return_value=[])
    fake_utils = (get_speech_timestamps,)

    with patch.object(
        vad_module.torch.hub,
        "load",
        return_value=(MagicMock(), fake_utils),
    ):
        segments = detect_speech_segments(audio, sample_rate)

    assert segments == []
