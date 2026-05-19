"""Unit tests for `audio_processor.preprocessing.ffmpeg.convert_to_wav`."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from audio_processor.exceptions import FfmpegConversionError
from audio_processor.preprocessing import ffmpeg as ffmpeg_module
from audio_processor.preprocessing.ffmpeg import convert_to_wav

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.unit
def test_convert_to_wav_invokes_ffmpeg_with_argv_list(tmp_path: Path) -> None:
    """Successful invocation passes an argv list (never a shell string)."""
    src = tmp_path / "in.mp3"
    src.write_bytes(b"\x00")
    dst = tmp_path / "out.wav"

    fake = MagicMock(spec=subprocess.CompletedProcess)
    fake.returncode = 0
    fake.stderr = ""

    with (
        patch.object(ffmpeg_module, "_FFMPEG_PATH", "/usr/bin/ffmpeg"),
        patch.object(ffmpeg_module.subprocess, "run", return_value=fake) as run_mock,
    ):
        result = convert_to_wav(src, dst)

    assert result == dst
    run_mock.assert_called_once()
    args, kwargs = run_mock.call_args
    cmd = args[0]
    assert isinstance(cmd, list), "command must be argv list to avoid shell injection"
    assert cmd[0] == "/usr/bin/ffmpeg"
    assert str(src) in cmd
    assert str(dst) in cmd
    assert kwargs.get("shell", False) is False


@pytest.mark.unit
def test_convert_to_wav_raises_when_ffmpeg_missing(tmp_path: Path) -> None:
    """Calling ``convert_to_wav`` without ffmpeg on PATH raises OSError."""
    src = tmp_path / "in.mp3"
    src.write_bytes(b"\x00")
    dst = tmp_path / "out.wav"

    with (
        patch.object(ffmpeg_module, "_FFMPEG_PATH", None),
        pytest.raises(FfmpegConversionError, match="ffmpeg binary not found"),
    ):
        convert_to_wav(src, dst)


@pytest.mark.unit
def test_convert_to_wav_raises_on_nonzero_exit(tmp_path: Path) -> None:
    """A non-zero ffmpeg exit surfaces FfmpegConversionError with stderr context."""
    src = tmp_path / "in.mp3"
    src.write_bytes(b"\x00")
    dst = tmp_path / "out.wav"

    fake = MagicMock(spec=subprocess.CompletedProcess)
    fake.returncode = 1
    fake.stderr = "Invalid data found when processing input"

    with (
        patch.object(ffmpeg_module, "_FFMPEG_PATH", "/usr/bin/ffmpeg"),
        patch.object(ffmpeg_module.subprocess, "run", return_value=fake),
        pytest.raises(FfmpegConversionError) as exc_info,
    ):
        convert_to_wav(src, dst)

    assert "exit 1" in str(exc_info.value)
    assert (
        exc_info.value.details.get("stderr")
        == "Invalid data found when processing input"
    )
    assert exc_info.value.details.get("exit_code") == 1
