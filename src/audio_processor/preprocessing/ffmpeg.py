"""Thin FFmpeg wrapper for format conversion (Sprint 2).

Provides a single ``convert_to_wav`` helper that shells out to ``ffmpeg``
via ``subprocess`` with an argument list (never a shell string) to
eliminate shell injection risk.

The ``ffmpeg`` binary is resolved on ``PATH`` at import time and cached;
if it is missing, the lookup result is preserved and any subsequent call
to ``convert_to_wav`` raises ``FfmpegConversionError`` with a clear
remediation message. Importing the module never fails, which lets test
suites mock ``subprocess`` without requiring the binary on hosts where
the real conversion will not run.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING, Final

from audio_processor.exceptions import FfmpegConversionError

if TYPE_CHECKING:
    from pathlib import Path

FFMPEG_BINARY: Final[str] = "ffmpeg"

_FFMPEG_MISSING_MSG: Final[str] = (
    "ffmpeg binary not found on PATH. Install ffmpeg "
    "(e.g. `apt install ffmpeg` or `brew install ffmpeg`) "
    "and ensure it is on PATH before calling convert_to_wav()."
)


def _locate_ffmpeg() -> str | None:
    """Resolve the ``ffmpeg`` binary on ``PATH`` if present.

    Returns:
        Absolute path to the ``ffmpeg`` executable, or ``None`` when the
        binary is not available.
    """
    return shutil.which(FFMPEG_BINARY)


# Resolve once at import time so we pay the PATH lookup cost only once and
# can surface a clear message at the first real call.
_FFMPEG_PATH: Final[str | None] = _locate_ffmpeg()


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
        FfmpegConversionError: If the ``ffmpeg`` binary is not on ``PATH``
            (resolved once at import; raised on first call so test suites
            that mock ``subprocess`` can still import the module), or if
            the ffmpeg invocation exits with a non-zero status. The
            original ``stderr`` output is included in ``details`` for
            diagnostics.
    """
    if _FFMPEG_PATH is None:
        raise FfmpegConversionError(_FFMPEG_MISSING_MSG)

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
            f"{input_path} -> {output_path}"
        )
        raise FfmpegConversionError(
            msg,
            details={
                "input_path": str(input_path),
                "output_path": str(output_path),
                "exit_code": result.returncode,
                "stderr": stderr,
            },
        )

    return output_path
