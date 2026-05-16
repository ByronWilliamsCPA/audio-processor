"""Top-level exceptions for the audio_processor package.

This module exposes exceptions used by the audio preprocessing pipeline.
Exceptions defined here inherit from the centralized ProjectBaseError so
they participate in the project-wide error hierarchy and structured logging.
"""

from __future__ import annotations

from audio_processor.core.exceptions import ProjectBaseError


class AudioLoadError(ProjectBaseError):
    """Raised when an audio file cannot be loaded or decoded.

    This covers unsupported formats, corrupt files, and any underlying
    library failure encountered while reading or decoding audio data.

    Example:
        >>> raise AudioLoadError(
        ...     "Unsupported audio format",
        ...     details={"path": "/tmp/sample.xyz", "suffix": ".xyz"},
        ... )
    """


__all__ = ["AudioLoadError"]
