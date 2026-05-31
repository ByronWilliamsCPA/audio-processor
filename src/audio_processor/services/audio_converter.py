"""Audio format conversion and extraction using FFmpeg.

This module provides a wrapper around FFmpeg for:
- Extracting audio from video files
- Converting between audio formats
- Detecting file format and codec information
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from audio_processor.core.config import settings
from audio_processor.core.exceptions import AudioProcessorError, ValidationError
from audio_processor.core.models import AudioFormat
from audio_processor.utils.logging import get_logger

logger = get_logger(__name__)

# Supported MIME types mapped to AudioFormat
MIME_TYPE_MAP: dict[str, AudioFormat] = {
    "audio/mpeg": AudioFormat.MP3,
    "audio/mp3": AudioFormat.MP3,
    "audio/wav": AudioFormat.WAV,
    "audio/x-wav": AudioFormat.WAV,
    "audio/wave": AudioFormat.WAV,
    "audio/x-m4a": AudioFormat.M4A,
    "audio/mp4": AudioFormat.M4A,
    "audio/aac": AudioFormat.M4A,
    "audio/flac": AudioFormat.FLAC,
    "audio/x-flac": AudioFormat.FLAC,
    "audio/ogg": AudioFormat.OGG,
    "audio/vorbis": AudioFormat.OGG,
    "audio/webm": AudioFormat.WEBM,
    "video/mp4": AudioFormat.MP4,
    "video/quicktime": AudioFormat.MOV,
    "video/x-msvideo": AudioFormat.AVI,
    "video/x-matroska": AudioFormat.MKV,
    "video/webm": AudioFormat.WEBM,
}

# File extensions mapped to AudioFormat
EXTENSION_MAP: dict[str, AudioFormat] = {
    ".mp3": AudioFormat.MP3,
    ".wav": AudioFormat.WAV,
    ".m4a": AudioFormat.M4A,
    ".flac": AudioFormat.FLAC,
    ".ogg": AudioFormat.OGG,
    ".webm": AudioFormat.WEBM,
    ".mp4": AudioFormat.MP4,
    ".mov": AudioFormat.MOV,
    ".avi": AudioFormat.AVI,
    ".mkv": AudioFormat.MKV,
}

# Video formats that require audio extraction
VIDEO_FORMATS: set[AudioFormat] = {
    AudioFormat.MP4,
    AudioFormat.MOV,
    AudioFormat.AVI,
    AudioFormat.MKV,
}


@dataclass(frozen=True)
class AudioInfo:
    """Information about an audio file.

    Attributes:
        duration_seconds (float): Duration of the audio in seconds.
        sample_rate (int): Sample rate in Hz.
        channels (int): Number of audio channels.
        codec (str): Audio codec name.
        bit_rate (int | None): Bit rate in bits per second.
        format_name (str): Container format name.
        is_video (bool): Whether the file is a video container.
    """

    duration_seconds: float
    sample_rate: int
    channels: int
    codec: str
    bit_rate: int | None
    format_name: str
    is_video: bool


class AudioConverter:
    """FFmpeg wrapper for audio format conversion and extraction.

    This class provides methods for:
    - Probing audio file information
    - Extracting audio from video files
    - Converting audio to optimal format for ASR

    Args:
        temp_dir (str | None): Directory for temporary files. Defaults to settings value.
        target_sample_rate (int | None): Target sample rate for conversion. Defaults to 16000.
        target_channels (int | None): Target number of channels. Defaults to 1 (mono).

    Example:
        >>> converter = AudioConverter()
        >>> info = converter.probe("/path/to/audio.mp3")
        >>> print(f"Duration: {info.duration_seconds}s")
        >>> output_path = converter.convert_for_asr("/path/to/video.mp4")
    """

    def __init__(
        self,
        temp_dir: str | None = None,
        target_sample_rate: int | None = None,
        target_channels: int | None = None,
    ) -> None:
        self.temp_dir = Path(temp_dir or settings.audio_temp_dir)
        self.target_sample_rate = (
            target_sample_rate or settings.audio_target_sample_rate
        )
        self.target_channels = target_channels or settings.audio_target_channels

        # Ensure temp directory exists
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def probe(self, file_path: str | Path) -> AudioInfo:
        """Probe an audio/video file to get its properties.

        Args:
            file_path (str | Path): Path to the audio or video file.

        Returns:
            AudioInfo: AudioInfo containing file properties.

        Raises:
            ValidationError: If the file cannot be probed or has no audio.
            AudioProcessorError: If FFprobe fails.
        """
        file_path = Path(file_path)

        if not file_path.exists():
            msg = f"File not found: {file_path}"
            raise ValidationError(msg, field="file_path", value=str(file_path))

        # Run ffprobe to get file information
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(file_path),
        ]

        try:
            result = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            msg = f"FFprobe timed out for file: {file_path}"
            raise AudioProcessorError(msg) from e
        except FileNotFoundError as e:
            msg = "FFprobe not found. Please install FFmpeg."
            raise AudioProcessorError(msg) from e

        if result.returncode != 0:
            msg = f"FFprobe failed: {result.stderr}"
            raise AudioProcessorError(msg)

        try:
            probe_data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            msg = f"Failed to parse FFprobe output: {e}"
            raise AudioProcessorError(msg) from e

        # Find audio and video streams
        audio_stream, video_stream = self._find_streams(probe_data)

        if audio_stream is None:
            msg = f"No audio stream found in file: {file_path}"
            raise ValidationError(msg, field="file_path", value=str(file_path))

        # Extract format information
        format_info = probe_data.get("format", {})

        # Get duration - try format first, then stream
        duration = float(format_info.get("duration", 0))
        if duration == 0:
            duration = float(audio_stream.get("duration", 0))

        # Get bit rate
        bit_rate_str = audio_stream.get("bit_rate") or format_info.get("bit_rate")
        bit_rate = int(bit_rate_str) if bit_rate_str else None

        return AudioInfo(
            duration_seconds=duration,
            sample_rate=int(audio_stream.get("sample_rate", 0)),
            channels=int(audio_stream.get("channels", 0)),
            codec=audio_stream.get("codec_name", "unknown"),
            bit_rate=bit_rate,
            format_name=format_info.get("format_name", "unknown"),
            is_video=video_stream is not None,
        )

    def detect_format(
        self,
        file_path: str | Path,
        content_type: str | None = None,
    ) -> AudioFormat:
        """Detect the audio format of a file.

        Args:
            file_path (str | Path): Path to the file.
            content_type (str | None): Optional MIME type from upload.

        Returns:
            AudioFormat: Detected AudioFormat.

        Raises:
            ValidationError: If format cannot be detected or is unsupported.
        """
        file_path = Path(file_path)

        # Try MIME type first
        if content_type and content_type in MIME_TYPE_MAP:
            return MIME_TYPE_MAP[content_type]

        # Try file extension
        ext = file_path.suffix.lower()
        if ext in EXTENSION_MAP:
            return EXTENSION_MAP[ext]

        # Try probing the file
        try:
            info = self.probe(file_path)
            fmt = self._format_from_codec(
                info.codec.lower(), info.format_name.lower(), info.is_video
            )
            if fmt is not None:
                return fmt
        except AudioProcessorError:
            pass

        msg = f"Unsupported or undetectable audio format: {file_path}"
        raise ValidationError(msg, field="file_path", value=str(file_path))

    def is_video(self, file_path: str | Path) -> bool:
        """Check if a file is a video container.

        Args:
            file_path (str | Path): Path to the file.

        Returns:
            bool: True if the file is a video container.
        """
        try:
            info = self.probe(file_path)
        except (ValidationError, AudioProcessorError):
            return False
        else:
            return info.is_video

    def _find_streams(
        self,
        probe_data: dict[str, Any],  # pyright: ignore[reportExplicitAny]
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:  # pyright: ignore[reportExplicitAny]
        """Return the first audio and video streams from ffprobe data.

        Args:
            probe_data (dict[str, Any]): Parsed JSON output from ffprobe.

        Returns:
            tuple[dict[str, Any] | None, dict[str, Any] | None]: Tuple of (first audio stream dict or None, first video stream dict or None).
        """
        audio_stream: dict[str, Any] | None = None  # pyright: ignore[reportExplicitAny]
        video_stream: dict[str, Any] | None = None  # pyright: ignore[reportExplicitAny]
        for stream in probe_data.get("streams", []):
            if stream.get("codec_type") == "audio" and audio_stream is None:
                audio_stream = stream
            elif stream.get("codec_type") == "video" and video_stream is None:
                video_stream = stream
        return audio_stream, video_stream

    def _format_from_codec(
        self,
        codec: str,
        format_name: str,
        is_video: bool,
    ) -> AudioFormat | None:
        """Map probed codec/format names to an AudioFormat enum value.

        Args:
            codec (str): Codec name from ffprobe (lowercased).
            format_name (str): Container format name from ffprobe (lowercased).
            is_video (bool): Whether the file contains a video stream.

        Returns:
            AudioFormat | None: Matching AudioFormat, or None if no mapping is found.
        """
        audio_table: list[tuple[str, str, AudioFormat]] = [
            ("mp3", "mp3", AudioFormat.MP3),
            ("pcm", "wav", AudioFormat.WAV),
            ("aac", "m4a", AudioFormat.M4A),
            ("flac", "", AudioFormat.FLAC),
            ("vorbis", "ogg", AudioFormat.OGG),
        ]
        for codec_kw, fmt_kw, audio_fmt in audio_table:
            if codec_kw in codec or (fmt_kw and fmt_kw in format_name):
                return audio_fmt
        if is_video:
            video_table: list[tuple[str, AudioFormat]] = [
                ("mp4", AudioFormat.MP4),
                ("mov", AudioFormat.MP4),
                ("avi", AudioFormat.AVI),
                ("matroska", AudioFormat.MKV),
            ]
            for fmt_kw, video_fmt in video_table:
                if fmt_kw in format_name:
                    return video_fmt
        return None

    def extract_audio(
        self,
        input_path: str | Path,
        output_path: str | Path | None = None,
    ) -> Path:
        """Extract audio from a video file.

        Args:
            input_path (str | Path): Path to the video file.
            output_path (str | Path | None): Optional output path. If not provided, a temp file is created.

        Returns:
            Path: Path to the extracted audio file.

        Raises:
            AudioProcessorError: If extraction fails.
        """
        input_path = Path(input_path)

        if output_path is None:
            with tempfile.NamedTemporaryFile(
                suffix=".wav", dir=self.temp_dir, delete=False
            ) as temp_file:
                output_path = Path(temp_file.name)
        else:
            output_path = Path(output_path)

        logger.info(
            "extracting_audio",
            input_path=str(input_path),
            output_path=str(output_path),
        )

        # FFmpeg command to extract audio
        cmd = [
            "ffmpeg",
            "-i",
            str(input_path),
            "-vn",  # No video
            "-acodec",
            "pcm_s16le",  # 16-bit PCM
            "-ar",
            str(self.target_sample_rate),
            "-ac",
            str(self.target_channels),
            "-y",  # Overwrite output
            str(output_path),
        ]

        try:
            result = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=settings.job_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            msg = f"Audio extraction timed out for: {input_path}"
            raise AudioProcessorError(msg) from e
        except FileNotFoundError as e:
            msg = "FFmpeg not found. Please install FFmpeg."
            raise AudioProcessorError(msg) from e

        if result.returncode != 0:
            msg = f"Audio extraction failed: {result.stderr}"
            raise AudioProcessorError(msg)

        logger.info(
            "audio_extracted",
            input_path=str(input_path),
            output_path=str(output_path),
        )

        return output_path

    def convert_for_asr(
        self,
        input_path: str | Path,
        output_path: str | Path | None = None,
    ) -> Path:
        """Convert audio file to optimal format for ASR processing.

        Converts to 16kHz mono WAV PCM, which is optimal for Deepgram and other
        ASR services.

        Args:
            input_path (str | Path): Path to the input audio/video file.
            output_path (str | Path | None): Optional output path. If not provided, a temp file is created.

        Returns:
            Path: Path to the converted audio file.

        Raises:
            AudioProcessorError: If conversion fails.
        """
        input_path = Path(input_path)

        if output_path is None:
            with tempfile.NamedTemporaryFile(
                suffix=".wav", dir=self.temp_dir, delete=False
            ) as temp_file:
                output_path = Path(temp_file.name)
        else:
            output_path = Path(output_path)

        logger.info(
            "converting_for_asr",
            input_path=str(input_path),
            output_path=str(output_path),
            target_sample_rate=self.target_sample_rate,
            target_channels=self.target_channels,
        )

        # FFmpeg command to convert to ASR-optimal format
        cmd = [
            "ffmpeg",
            "-i",
            str(input_path),
            "-vn",  # No video
            "-acodec",
            "pcm_s16le",  # 16-bit PCM
            "-ar",
            str(self.target_sample_rate),  # Target sample rate
            "-ac",
            str(self.target_channels),  # Target channels
            "-y",  # Overwrite output
            str(output_path),
        ]

        try:
            result = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=settings.job_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            msg = f"Audio conversion timed out for: {input_path}"
            raise AudioProcessorError(msg) from e
        except FileNotFoundError as e:
            msg = "FFmpeg not found. Please install FFmpeg."
            raise AudioProcessorError(msg) from e

        if result.returncode != 0:
            msg = f"Audio conversion failed: {result.stderr}"
            raise AudioProcessorError(msg)

        logger.info(
            "audio_converted",
            input_path=str(input_path),
            output_path=str(output_path),
        )

        return output_path

    def validate_file(
        self,
        file_path: str | Path,
        max_size_bytes: int | None = None,
        max_duration_seconds: float | None = None,
    ) -> AudioInfo:
        """Validate an audio file against size and duration limits.

        Args:
            file_path (str | Path): Path to the audio file.
            max_size_bytes (int | None): Maximum file size in bytes. Defaults to settings value.
            max_duration_seconds (float | None): Maximum duration in seconds. Defaults to settings.

        Returns:
            AudioInfo: AudioInfo if validation passes.

        Raises:
            ValidationError: If validation fails.
        """
        file_path = Path(file_path)
        max_size = max_size_bytes or settings.max_file_size_bytes
        max_duration = max_duration_seconds or settings.max_duration_seconds

        # Check file exists
        if not file_path.exists():
            msg = f"File not found: {file_path}"
            raise ValidationError(msg, field="file_path", value=str(file_path))

        # Check file size
        file_size = file_path.stat().st_size
        if file_size > max_size:
            msg = f"File size {file_size} exceeds maximum {max_size} bytes"
            raise ValidationError(msg, field="file_size", value=file_size)

        # Probe the file
        info = self.probe(file_path)

        # Check duration
        if info.duration_seconds > max_duration:
            msg = f"Duration {info.duration_seconds}s exceeds maximum {max_duration}s"
            raise ValidationError(
                msg,
                field="duration",
                value=info.duration_seconds,
            )

        # Check minimum duration
        if info.duration_seconds < 1.0:
            msg = f"Duration {info.duration_seconds}s is too short (minimum 1 second)"
            raise ValidationError(
                msg,
                field="duration",
                value=info.duration_seconds,
            )

        return info
