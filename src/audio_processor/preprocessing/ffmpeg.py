"""Thin FFmpeg wrapper for format conversion (Sprint 2).

Provides a single ``convert_to_wav`` helper that shells out to ``ffmpeg``
via ``subprocess`` with an argument list (never a shell string) to
eliminate shell injection risk.

The ``ffmpeg`` binary is required on ``PATH`` at import time; the module
raises ``EnvironmentError`` with a clear message if it is missing.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from pathlib import Path

FFMPEG_BINARY: Final[str] = "ffmpeg"


def _locate_ffmpeg() -> str:
    """Return the resolved path to the ``ffmpeg`` binary.

    Returns:
        Absolute path to the ``ffmpeg`` executable found on ``PATH``.

    Raises:
        OSError: If ``ffmpeg`` is not available on ``PATH``.
    """
    resolved = shutil.which(FFMPEG_BINARY)
    if resolved is None:
        msg = (
            "ffmpeg binary not found on PATH. Install ffmpeg "
            "(e.g. `apt install ffmpeg` or `brew install ffmpeg`) "
            "and ensure it is on PATH before importing this module."
        )
        raise OSError(msg)
    return resolved


# Validate ffmpeg availability at import time so misconfigured environments
# fail fast rather than at first conversion.
_FFMPEG_PATH: Final[str] = _locate_ffmpeg()


def convert_to_wav(input_path: Path, output_path: Path) -> Path:
    """Convert an audio or video file to a WAV file using ffmpeg.

    Invokes ffmpeg via ``subprocess.run`` with an argument list (no shell
    interpolation) and overwrites ``output_path`` if it already exists.

    Args:
        input_path: Filesystem path to the source media file.
        output_path: Filesystem path for the resulting WAV file. The parent
            directory must already exist.

    Returns:
        The ``output_path`` argument, returned for call-chaining convenience.

    Raises:
        RuntimeError: If the ffmpeg invocation exits with a non-zero status.
            The original ``stderr`` output is included for diagnostics.
    """
    cmd: list[str] = [
        _FFMPEG_PATH,
        "-y",  # overwrite output without prompting
        "-i",
        str(input_path),
        "-vn",  # drop any video stream
        "-acodec",
        "pcm_s16le",  # standard 16-bit PCM WAV
        str(output_path),
    ]

    # `check=False` so we can surface ffmpeg's stderr verbatim; `shell=False`
    # (the default) is the security-critical guarantee, never pass a string.
    result = subprocess.run(  # noqa: S603 - argv list, shell=False
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "<no stderr output>"
        msg = (
            f"ffmpeg failed (exit {result.returncode}) converting "
            f"{input_path} -> {output_path}: {stderr}"
        )
        raise RuntimeError(msg)

    return output_path
