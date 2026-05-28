"""Unit tests for audio processing services."""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from audio_processor.core.config import Settings
from audio_processor.core.exceptions import (
    AudioProcessorError,
    ConfigurationError,
    ValidationError,
)
from audio_processor.core.models import QualityLevel

if TYPE_CHECKING:
    from pathlib import Path


class TestSettings:
    """Tests for Settings configuration."""

    def test_default_settings(self) -> None:
        """Test default configuration values."""
        settings = Settings()
        assert settings.log_level == "INFO"
        assert settings.deepgram_model == "nova-2"
        assert settings.audio_target_sample_rate == 16000
        assert settings.vad_enabled is True

    def test_max_file_size_bytes(self) -> None:
        """Test max file size calculation."""
        settings = Settings()
        assert settings.max_file_size_bytes == 500 * 1024 * 1024

    def test_max_duration_seconds(self) -> None:
        """Test max duration calculation."""
        settings = Settings()
        assert settings.max_duration_seconds == 4.0 * 3600


class TestAudioConverterMIMETypes:
    """Tests for MIME type handling."""

    def test_mime_type_mapping(self) -> None:
        """Test MIME type to format mapping."""
        from audio_processor.core.models import AudioFormat
        from audio_processor.services.audio_converter import MIME_TYPE_MAP

        assert MIME_TYPE_MAP["audio/mpeg"] == AudioFormat.MP3
        assert MIME_TYPE_MAP["audio/wav"] == AudioFormat.WAV
        assert MIME_TYPE_MAP["video/mp4"] == AudioFormat.MP4

    def test_extension_mapping(self) -> None:
        """Test file extension to format mapping."""
        from audio_processor.core.models import AudioFormat
        from audio_processor.services.audio_converter import EXTENSION_MAP

        assert EXTENSION_MAP[".mp3"] == AudioFormat.MP3
        assert EXTENSION_MAP[".wav"] == AudioFormat.WAV
        assert EXTENSION_MAP[".mp4"] == AudioFormat.MP4


class TestAudioConverterInit:
    """Tests for AudioConverter initialization."""

    def test_default_initialization(self) -> None:
        """Test default initialization."""
        from audio_processor.services.audio_converter import AudioConverter

        converter = AudioConverter()
        assert converter.target_sample_rate == 16000
        assert converter.target_channels == 1

    def test_custom_initialization(self, tmp_path: Path) -> None:
        """Test custom initialization."""
        from audio_processor.services.audio_converter import AudioConverter

        custom_temp = tmp_path / "custom" / "temp"
        converter = AudioConverter(
            temp_dir=str(custom_temp),
            target_sample_rate=44100,
            target_channels=2,
        )
        assert converter.target_sample_rate == 44100
        assert converter.target_channels == 2
        assert converter.temp_dir == custom_temp


class TestAudioConverterProbe:
    """Tests for AudioConverter.probe method."""

    def test_probe_file_not_found(self) -> None:
        """Test probing non-existent file raises error."""
        from audio_processor.services.audio_converter import AudioConverter

        converter = AudioConverter()
        with pytest.raises(ValidationError) as exc_info:
            converter.probe("/nonexistent/file.wav")
        assert "File not found" in str(exc_info.value)

    @patch("subprocess.run")
    def test_probe_ffprobe_not_found(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test probe when FFprobe is not installed."""
        from audio_processor.services.audio_converter import AudioConverter

        # Create a dummy file
        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)

        mock_run.side_effect = FileNotFoundError()

        converter = AudioConverter()
        with pytest.raises(AudioProcessorError) as exc_info:
            converter.probe(test_file)
        assert "FFprobe not found" in str(exc_info.value)

    @patch("subprocess.run")
    def test_probe_timeout(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test probe raises AudioProcessorError on timeout."""
        from audio_processor.services.audio_converter import AudioConverter

        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffprobe", timeout=30)

        converter = AudioConverter()
        with pytest.raises(AudioProcessorError) as exc_info:
            converter.probe(test_file)
        assert "timed out" in str(exc_info.value).lower()

    @patch("subprocess.run")
    def test_probe_nonzero_returncode(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test probe raises AudioProcessorError when ffprobe returns non-zero."""
        from audio_processor.services.audio_converter import AudioConverter

        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Invalid data found"
        mock_run.return_value = mock_result

        converter = AudioConverter()
        with pytest.raises(AudioProcessorError) as exc_info:
            converter.probe(test_file)
        assert "FFprobe failed" in str(exc_info.value)

    @patch("subprocess.run")
    def test_probe_bad_json(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test probe raises AudioProcessorError on invalid JSON output."""
        from audio_processor.services.audio_converter import AudioConverter

        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not valid json {"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        converter = AudioConverter()
        with pytest.raises(AudioProcessorError) as exc_info:
            converter.probe(test_file)
        assert "parse" in str(exc_info.value).lower()

    @patch("subprocess.run")
    def test_probe_no_audio_stream(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test probe raises ValidationError when file has no audio stream."""
        from audio_processor.services.audio_converter import AudioConverter

        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"\x00" * 100)

        fake_probe = json.dumps({"streams": [], "format": {"format_name": "mp4"}})
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = fake_probe
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        converter = AudioConverter()
        with pytest.raises(ValidationError) as exc_info:
            converter.probe(test_file)
        assert "No audio stream" in str(exc_info.value)

    @patch("subprocess.run")
    def test_probe_success_returns_audio_info(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test probe returns correct AudioInfo on success."""
        from audio_processor.services.audio_converter import AudioConverter, AudioInfo

        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)

        fake_probe = json.dumps(
            {
                "streams": [
                    {
                        "codec_type": "audio",
                        "codec_name": "pcm_s16le",
                        "sample_rate": "44100",
                        "channels": 2,
                        "duration": "120.0",
                        "bit_rate": "1411200",
                    }
                ],
                "format": {
                    "format_name": "wav",
                    "duration": "120.0",
                    "bit_rate": "1411200",
                },
            }
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = fake_probe
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        converter = AudioConverter()
        info = converter.probe(test_file)

        assert isinstance(info, AudioInfo)
        assert info.sample_rate == 44100
        assert info.channels == 2
        assert info.codec == "pcm_s16le"
        assert info.duration_seconds == 120.0
        assert info.is_video is False

    @patch("subprocess.run")
    def test_probe_video_file_detects_video_stream(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test probe sets is_video=True when a video stream is present."""
        from audio_processor.services.audio_converter import AudioConverter

        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"\x00" * 100)

        fake_probe = json.dumps(
            {
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                    },
                    {
                        "codec_type": "audio",
                        "codec_name": "aac",
                        "sample_rate": "48000",
                        "channels": 2,
                        "duration": "60.0",
                    },
                ],
                "format": {"format_name": "mp4", "duration": "60.0"},
            }
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = fake_probe
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        converter = AudioConverter()
        info = converter.probe(test_file)

        assert info.is_video is True
        assert info.codec == "aac"

    @patch("subprocess.run")
    def test_probe_duration_fallback_to_stream(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test probe uses stream duration when format duration is zero."""
        from audio_processor.services.audio_converter import AudioConverter

        test_file = tmp_path / "test.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)

        fake_probe = json.dumps(
            {
                "streams": [
                    {
                        "codec_type": "audio",
                        "codec_name": "pcm_s16le",
                        "sample_rate": "16000",
                        "channels": 1,
                        "duration": "30.0",
                    }
                ],
                "format": {"format_name": "wav"},
            }
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = fake_probe
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        converter = AudioConverter()
        info = converter.probe(test_file)

        assert info.duration_seconds == 30.0


class TestAudioConverterValidation:
    """Tests for AudioConverter.validate_file method."""

    def test_validate_file_not_found(self) -> None:
        """Test validating non-existent file."""
        from audio_processor.services.audio_converter import AudioConverter

        converter = AudioConverter()
        with pytest.raises(ValidationError) as exc_info:
            converter.validate_file("/nonexistent/file.wav")
        assert "File not found" in str(exc_info.value)

    @patch("subprocess.run")
    def test_validate_file_too_large(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test validating oversized file raises ValidationError."""
        from audio_processor.services.audio_converter import AudioConverter

        test_file = tmp_path / "big.wav"
        test_file.write_bytes(b"\x00" * 100)

        converter = AudioConverter()
        with pytest.raises(ValidationError) as exc_info:
            converter.validate_file(test_file, max_size_bytes=10)
        assert "size" in str(exc_info.value).lower()

    @patch("subprocess.run")
    def test_validate_file_exceeds_duration(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test validating file with duration exceeding limit raises ValidationError."""
        from audio_processor.services.audio_converter import AudioConverter

        test_file = tmp_path / "long.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)

        fake_probe = json.dumps(
            {
                "streams": [
                    {
                        "codec_type": "audio",
                        "codec_name": "pcm_s16le",
                        "sample_rate": "16000",
                        "channels": 1,
                        "duration": "7200.0",
                    }
                ],
                "format": {"format_name": "wav", "duration": "7200.0"},
            }
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = fake_probe
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        converter = AudioConverter()
        with pytest.raises(ValidationError) as exc_info:
            converter.validate_file(test_file, max_duration_seconds=60.0)
        assert "duration" in str(exc_info.value).lower()

    @patch("subprocess.run")
    def test_validate_file_too_short(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test validating file shorter than 1 second raises ValidationError."""
        from audio_processor.services.audio_converter import AudioConverter

        test_file = tmp_path / "short.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)

        fake_probe = json.dumps(
            {
                "streams": [
                    {
                        "codec_type": "audio",
                        "codec_name": "pcm_s16le",
                        "sample_rate": "16000",
                        "channels": 1,
                        "duration": "0.5",
                    }
                ],
                "format": {"format_name": "wav", "duration": "0.5"},
            }
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = fake_probe
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        converter = AudioConverter()
        with pytest.raises(ValidationError) as exc_info:
            converter.validate_file(test_file)
        assert "too short" in str(exc_info.value).lower()

    @patch("subprocess.run")
    def test_validate_file_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test validating a valid file returns AudioInfo."""
        from audio_processor.services.audio_converter import AudioConverter, AudioInfo

        test_file = tmp_path / "valid.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)

        fake_probe = json.dumps(
            {
                "streams": [
                    {
                        "codec_type": "audio",
                        "codec_name": "pcm_s16le",
                        "sample_rate": "16000",
                        "channels": 1,
                        "duration": "10.0",
                    }
                ],
                "format": {"format_name": "wav", "duration": "10.0"},
            }
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = fake_probe
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        converter = AudioConverter()
        info = converter.validate_file(test_file)

        assert isinstance(info, AudioInfo)
        assert info.duration_seconds == 10.0


class TestAudioConverterDetectFormat:
    """Tests for AudioConverter.detect_format method."""

    def test_detect_format_from_mime_type(self) -> None:
        """Test format detection from MIME type takes precedence."""
        from audio_processor.core.models import AudioFormat
        from audio_processor.services.audio_converter import AudioConverter

        converter = AudioConverter()
        fmt = converter.detect_format("/some/file.wav", content_type="audio/mpeg")

        assert fmt == AudioFormat.MP3

    def test_detect_format_from_extension(self) -> None:
        """Test format detection falls back to file extension."""
        from audio_processor.core.models import AudioFormat
        from audio_processor.services.audio_converter import AudioConverter

        converter = AudioConverter()
        fmt = converter.detect_format("/some/file.flac")

        assert fmt == AudioFormat.FLAC

    @patch("subprocess.run")
    def test_detect_format_from_probe_mp3(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test format detection falls through to probe for unknown extension."""
        from audio_processor.core.models import AudioFormat
        from audio_processor.services.audio_converter import AudioConverter

        test_file = tmp_path / "audio.unknown"
        test_file.write_bytes(b"\x00" * 100)

        fake_probe = json.dumps(
            {
                "streams": [
                    {
                        "codec_type": "audio",
                        "codec_name": "mp3",
                        "sample_rate": "44100",
                        "channels": 2,
                        "duration": "60.0",
                    }
                ],
                "format": {"format_name": "mp3", "duration": "60.0"},
            }
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = fake_probe
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        converter = AudioConverter()
        fmt = converter.detect_format(test_file)

        assert fmt == AudioFormat.MP3

    @patch("subprocess.run")
    def test_detect_format_unsupported_raises(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test detect_format raises ValidationError for unsupported format."""
        from audio_processor.services.audio_converter import AudioConverter

        test_file = tmp_path / "audio.xyz"
        test_file.write_bytes(b"\x00" * 100)

        mock_run.side_effect = FileNotFoundError()

        converter = AudioConverter()
        with pytest.raises(ValidationError) as exc_info:
            converter.detect_format(test_file)
        assert "unsupported" in str(exc_info.value).lower()

    @patch("subprocess.run")
    def test_detect_format_from_probe_wav(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test format detection from probe identifies WAV via pcm codec."""
        from audio_processor.core.models import AudioFormat
        from audio_processor.services.audio_converter import AudioConverter

        test_file = tmp_path / "audio.bin"
        test_file.write_bytes(b"\x00" * 100)

        fake_probe = json.dumps(
            {
                "streams": [
                    {
                        "codec_type": "audio",
                        "codec_name": "pcm_s16le",
                        "sample_rate": "44100",
                        "channels": 1,
                        "duration": "5.0",
                    }
                ],
                "format": {"format_name": "wav", "duration": "5.0"},
            }
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = fake_probe
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        converter = AudioConverter()
        fmt = converter.detect_format(test_file)

        assert fmt == AudioFormat.WAV

    @patch("subprocess.run")
    def test_detect_format_from_probe_video_mp4(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test format detection from probe identifies MP4 video format via is_video path."""
        from audio_processor.core.models import AudioFormat
        from audio_processor.services.audio_converter import AudioConverter

        test_file = tmp_path / "video.bin"
        test_file.write_bytes(b"\x00" * 100)

        # Use opus codec so the earlier codec checks (mp3/pcm/aac/flac/vorbis) don't match,
        # allowing the is_video branch to fire and return MP4 based on format_name.
        fake_probe = json.dumps(
            {
                "streams": [
                    {"codec_type": "video", "codec_name": "h264"},
                    {
                        "codec_type": "audio",
                        "codec_name": "opus",
                        "sample_rate": "48000",
                        "channels": 2,
                        "duration": "60.0",
                    },
                ],
                "format": {"format_name": "mp4", "duration": "60.0"},
            }
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = fake_probe
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        converter = AudioConverter()
        fmt = converter.detect_format(test_file)

        assert fmt == AudioFormat.MP4


class TestAudioConverterIsVideo:
    """Tests for AudioConverter.is_video method."""

    @patch("subprocess.run")
    def test_is_video_returns_true_for_video(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test is_video returns True for video files."""
        from audio_processor.services.audio_converter import AudioConverter

        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"\x00" * 100)

        fake_probe = json.dumps(
            {
                "streams": [
                    {"codec_type": "video", "codec_name": "h264"},
                    {
                        "codec_type": "audio",
                        "codec_name": "aac",
                        "sample_rate": "48000",
                        "channels": 2,
                        "duration": "60.0",
                    },
                ],
                "format": {"format_name": "mp4", "duration": "60.0"},
            }
        )
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = fake_probe
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        converter = AudioConverter()
        assert converter.is_video(test_file) is True

    def test_is_video_returns_false_on_error(self) -> None:
        """Test is_video returns False when probe fails."""
        from audio_processor.services.audio_converter import AudioConverter

        converter = AudioConverter()
        assert converter.is_video("/nonexistent/file.mp4") is False


class TestAudioConverterExtractAudio:
    """Tests for AudioConverter.extract_audio method."""

    @patch("subprocess.run")
    def test_extract_audio_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test successful audio extraction returns output path."""
        from audio_processor.services.audio_converter import AudioConverter

        input_file = tmp_path / "video.mp4"
        input_file.write_bytes(b"\x00" * 100)
        output_file = tmp_path / "audio.wav"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        converter = AudioConverter(temp_dir=str(tmp_path))
        result = converter.extract_audio(input_file, output_path=output_file)

        assert result == output_file
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_extract_audio_nonzero_returncode(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test extract_audio raises AudioProcessorError on failure."""
        from audio_processor.services.audio_converter import AudioConverter

        input_file = tmp_path / "video.mp4"
        input_file.write_bytes(b"\x00" * 100)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Conversion error"
        mock_run.return_value = mock_result

        converter = AudioConverter(temp_dir=str(tmp_path))
        with pytest.raises(AudioProcessorError) as exc_info:
            converter.extract_audio(input_file)
        assert "extraction failed" in str(exc_info.value).lower()

    @patch("subprocess.run")
    def test_extract_audio_timeout(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test extract_audio raises AudioProcessorError on timeout."""
        from audio_processor.services.audio_converter import AudioConverter

        input_file = tmp_path / "video.mp4"
        input_file.write_bytes(b"\x00" * 100)

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=300)

        converter = AudioConverter(temp_dir=str(tmp_path))
        with pytest.raises(AudioProcessorError) as exc_info:
            converter.extract_audio(input_file)
        assert "timed out" in str(exc_info.value).lower()

    @patch("subprocess.run")
    def test_extract_audio_ffmpeg_not_found(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test extract_audio raises AudioProcessorError when FFmpeg is missing."""
        from audio_processor.services.audio_converter import AudioConverter

        input_file = tmp_path / "video.mp4"
        input_file.write_bytes(b"\x00" * 100)

        mock_run.side_effect = FileNotFoundError()

        converter = AudioConverter(temp_dir=str(tmp_path))
        with pytest.raises(AudioProcessorError) as exc_info:
            converter.extract_audio(input_file)
        assert "FFmpeg not found" in str(exc_info.value)

    @patch("subprocess.run")
    def test_extract_audio_creates_temp_file_when_no_output(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test extract_audio auto-creates temp output path when none given."""
        from audio_processor.services.audio_converter import AudioConverter

        input_file = tmp_path / "video.mp4"
        input_file.write_bytes(b"\x00" * 100)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        converter = AudioConverter(temp_dir=str(tmp_path))
        result = converter.extract_audio(input_file)

        assert result.suffix == ".wav"
        assert result.parent == tmp_path


class TestAudioConverterConvertForAsr:
    """Tests for AudioConverter.convert_for_asr method."""

    @patch("subprocess.run")
    def test_convert_for_asr_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test successful conversion returns output path."""
        from audio_processor.services.audio_converter import AudioConverter

        input_file = tmp_path / "audio.mp3"
        input_file.write_bytes(b"\x00" * 100)
        output_file = tmp_path / "converted.wav"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        converter = AudioConverter(temp_dir=str(tmp_path))
        result = converter.convert_for_asr(input_file, output_path=output_file)

        assert result == output_file

    @patch("subprocess.run")
    def test_convert_for_asr_nonzero_returncode(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test convert_for_asr raises AudioProcessorError on failure."""
        from audio_processor.services.audio_converter import AudioConverter

        input_file = tmp_path / "audio.mp3"
        input_file.write_bytes(b"\x00" * 100)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "conversion failed"
        mock_run.return_value = mock_result

        converter = AudioConverter(temp_dir=str(tmp_path))
        with pytest.raises(AudioProcessorError) as exc_info:
            converter.convert_for_asr(input_file)
        assert "conversion failed" in str(exc_info.value).lower()

    @patch("subprocess.run")
    def test_convert_for_asr_timeout(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test convert_for_asr raises AudioProcessorError on timeout."""
        from audio_processor.services.audio_converter import AudioConverter

        input_file = tmp_path / "audio.mp3"
        input_file.write_bytes(b"\x00" * 100)

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=300)

        converter = AudioConverter(temp_dir=str(tmp_path))
        with pytest.raises(AudioProcessorError) as exc_info:
            converter.convert_for_asr(input_file)
        assert "timed out" in str(exc_info.value).lower()

    @patch("subprocess.run")
    def test_convert_for_asr_ffmpeg_not_found(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test convert_for_asr raises AudioProcessorError when FFmpeg missing."""
        from audio_processor.services.audio_converter import AudioConverter

        input_file = tmp_path / "audio.mp3"
        input_file.write_bytes(b"\x00" * 100)

        mock_run.side_effect = FileNotFoundError()

        converter = AudioConverter(temp_dir=str(tmp_path))
        with pytest.raises(AudioProcessorError) as exc_info:
            converter.convert_for_asr(input_file)
        assert "FFmpeg not found" in str(exc_info.value)

    @patch("subprocess.run")
    def test_convert_for_asr_auto_temp_path(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test convert_for_asr creates temp WAV output when none is provided."""
        from audio_processor.services.audio_converter import AudioConverter

        input_file = tmp_path / "audio.mp3"
        input_file.write_bytes(b"\x00" * 100)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        converter = AudioConverter(temp_dir=str(tmp_path))
        result = converter.convert_for_asr(input_file)

        assert result.suffix == ".wav"
        assert result.parent == tmp_path


class TestQualityAssessorInit:
    """Tests for QualityAssessor initialization."""

    def test_default_initialization(self) -> None:
        """Test default initialization."""
        from audio_processor.services.quality_assessor import QualityAssessor

        assessor = QualityAssessor()
        assert assessor.snr_excellent_db == 25.0
        assert assessor.snr_good_db == 15.0
        assert assessor.snr_fair_db == 10.0

    def test_custom_initialization(self) -> None:
        """Test custom threshold initialization."""
        from audio_processor.services.quality_assessor import QualityAssessor

        assessor = QualityAssessor(
            snr_excellent_db=30.0,
            snr_good_db=20.0,
            snr_fair_db=15.0,
        )
        assert assessor.snr_excellent_db == 30.0
        assert assessor.snr_good_db == 20.0
        assert assessor.snr_fair_db == 15.0


class TestQualityAssessorAssess:
    """Tests for QualityAssessor.assess method."""

    def test_assess_file_not_found(self) -> None:
        """Test assessing non-existent file."""
        from audio_processor.services.quality_assessor import QualityAssessor

        assessor = QualityAssessor()
        with pytest.raises(ValidationError) as exc_info:
            assessor.assess("/nonexistent/file.wav")
        assert "File not found" in str(exc_info.value)

    @patch("soundfile.read")
    def test_assess_returns_metrics_for_clean_signal(
        self, mock_sf_read: MagicMock, tmp_path: Path
    ) -> None:
        """Test assess returns AudioQualityMetrics for a clean audio signal."""
        from audio_processor.core.models import AudioQualityMetrics
        from audio_processor.services.quality_assessor import QualityAssessor

        test_file = tmp_path / "clean.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)

        t = np.linspace(0, 2, 32000, dtype=np.float64)
        fake_audio = 0.3 * np.sin(2 * np.pi * 440 * t)
        mock_sf_read.return_value = (fake_audio, 16000)

        assessor = QualityAssessor()
        metrics = assessor.assess(test_file)

        assert isinstance(metrics, AudioQualityMetrics)
        assert metrics.sample_rate == 16000
        assert metrics.channels == 1
        assert metrics.duration_seconds > 0
        assert 0.0 <= metrics.quality_score <= 1.0

    @patch("soundfile.read")
    def test_assess_stereo_audio_converted_to_mono(
        self, mock_sf_read: MagicMock, tmp_path: Path
    ) -> None:
        """Test assess handles stereo audio by converting to mono."""
        from audio_processor.services.quality_assessor import QualityAssessor

        test_file = tmp_path / "stereo.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)

        stereo = np.zeros((32000, 2), dtype=np.float64)
        stereo[:, 0] = 0.3
        stereo[:, 1] = -0.3
        mock_sf_read.return_value = (stereo, 16000)

        assessor = QualityAssessor()
        metrics = assessor.assess(test_file)

        assert metrics.channels == 2

    @patch("soundfile.read")
    def test_assess_raises_audio_processor_error_on_oserror(
        self, mock_sf_read: MagicMock, tmp_path: Path
    ) -> None:
        """Test assess raises AudioProcessorError when soundfile raises OSError."""
        from audio_processor.services.quality_assessor import QualityAssessor

        test_file = tmp_path / "bad.wav"
        test_file.write_bytes(b"\x00" * 100)

        mock_sf_read.side_effect = OSError("file is corrupt")

        assessor = QualityAssessor()
        with pytest.raises(AudioProcessorError) as exc_info:
            assessor.assess(test_file)
        assert "quality" in str(exc_info.value).lower()


class TestQualityAssessorMetrics:
    """Tests for QualityAssessor metric calculations."""

    def test_quality_level_determination(self) -> None:
        """Test quality level determination logic."""
        from audio_processor.services.quality_assessor import QualityAssessor

        assessor = QualityAssessor()

        # Test excellent quality
        level = assessor._determine_quality_level(30.0, 0.9)
        assert level == QualityLevel.EXCELLENT

        # Test good quality
        level = assessor._determine_quality_level(20.0, 0.7)
        assert level == QualityLevel.GOOD

        # Test fair quality
        level = assessor._determine_quality_level(12.0, 0.5)
        assert level == QualityLevel.FAIR

        # Test poor quality
        level = assessor._determine_quality_level(5.0, 0.2)
        assert level == QualityLevel.POOR

    def test_warning_generation(self) -> None:
        """Test warning message generation."""
        from audio_processor.services.quality_assessor import QualityAssessor

        assessor = QualityAssessor()

        # Test low SNR warning
        warnings = assessor._generate_warnings(
            snr_db=5.0,
            silence_ratio=0.1,
            clipping_ratio=0.0,
            peak_amplitude=0.5,
        )
        assert any("signal-to-noise" in w.lower() for w in warnings)

        # Test high silence warning
        warnings = assessor._generate_warnings(
            snr_db=30.0,
            silence_ratio=0.7,
            clipping_ratio=0.0,
            peak_amplitude=0.5,
        )
        assert any("silence" in w.lower() for w in warnings)

        # Test clipping warning
        warnings = assessor._generate_warnings(
            snr_db=30.0,
            silence_ratio=0.1,
            clipping_ratio=0.1,
            peak_amplitude=0.99,
        )
        assert any("clipping" in w.lower() for w in warnings)

        # Test low level warning
        warnings = assessor._generate_warnings(
            snr_db=30.0,
            silence_ratio=0.1,
            clipping_ratio=0.0,
            peak_amplitude=0.05,
        )
        assert any("low audio level" in w.lower() for w in warnings)

    def test_calculate_snr_returns_float(self) -> None:
        """Test SNR calculation returns a valid float for a sine wave."""
        from audio_processor.services.quality_assessor import QualityAssessor

        assessor = QualityAssessor()
        t = np.linspace(0, 2, 32000, dtype=np.float64)
        audio = 0.3 * np.sin(2 * np.pi * 440 * t)

        snr = assessor._calculate_snr(audio)

        assert isinstance(snr, float)
        assert -10.0 <= snr <= 60.0

    def test_calculate_snr_silent_audio_returns_max(self) -> None:
        """Test SNR calculation returns 60.0 for all-silent audio (noise energy is zero)."""
        from audio_processor.services.quality_assessor import QualityAssessor

        assessor = QualityAssessor()
        # Must be at least frame_length=2048 samples for librosa to frame successfully
        audio = np.zeros(4096, dtype=np.float64)

        snr = assessor._calculate_snr(audio)

        assert snr == pytest.approx(60.0)

    def test_calculate_silence_ratio_all_silent(self) -> None:
        """Test silence ratio is 1.0 for all-silent audio."""
        from audio_processor.services.quality_assessor import QualityAssessor

        assessor = QualityAssessor()
        silence = np.zeros(16000, dtype=np.float64)

        ratio = assessor._calculate_silence_ratio(silence, 16000)

        assert ratio == 1.0

    def test_calculate_silence_ratio_loud_signal(self) -> None:
        """Test silence ratio is near zero for a loud sustained signal."""
        from audio_processor.services.quality_assessor import QualityAssessor

        assessor = QualityAssessor()
        t = np.linspace(0, 2, 32000, dtype=np.float64)
        audio = 0.8 * np.sin(2 * np.pi * 440 * t)

        ratio = assessor._calculate_silence_ratio(audio, 16000)

        assert ratio < 0.1

    def test_calculate_clipping_ratio_no_clipping(self) -> None:
        """Test clipping ratio is 0.0 for a well-within-range signal."""
        from audio_processor.services.quality_assessor import QualityAssessor

        assessor = QualityAssessor()
        audio = np.full(1000, 0.5, dtype=np.float64)

        ratio = assessor._calculate_clipping_ratio(audio)

        assert ratio == 0.0

    def test_calculate_clipping_ratio_fully_clipped(self) -> None:
        """Test clipping ratio is 1.0 when all samples are at full scale."""
        from audio_processor.services.quality_assessor import QualityAssessor

        assessor = QualityAssessor()
        audio = np.ones(1000, dtype=np.float64)

        ratio = assessor._calculate_clipping_ratio(audio)

        assert ratio == 1.0

    def test_calculate_clipping_ratio_empty(self) -> None:
        """Test clipping ratio returns 0.0 for empty audio."""
        from audio_processor.services.quality_assessor import QualityAssessor

        assessor = QualityAssessor()
        audio = np.array([], dtype=np.float64)

        ratio = assessor._calculate_clipping_ratio(audio)

        assert ratio == 0.0

    def test_calculate_rms_db_silence(self) -> None:
        """Test RMS dB returns silence floor for all-zero audio."""
        from audio_processor.services.quality_assessor import QualityAssessor

        assessor = QualityAssessor()
        audio = np.zeros(1000, dtype=np.float64)

        rms_db = assessor._calculate_rms_db(audio)

        assert rms_db == -96.0

    def test_calculate_quality_score_bounds(self) -> None:
        """Test quality score is always in [0.0, 1.0]."""
        from audio_processor.services.quality_assessor import QualityAssessor

        assessor = QualityAssessor()

        perfect = assessor._calculate_quality_score(
            snr_db=60.0, silence_ratio=0.0, clipping_ratio=0.0
        )
        assert perfect == 1.0

        worst = assessor._calculate_quality_score(
            snr_db=0.0, silence_ratio=1.0, clipping_ratio=1.0
        )
        assert worst == 0.0

    @patch("soundfile.read")
    def test_load_audio_falls_back_to_librosa(
        self, mock_sf_read: MagicMock, tmp_path: Path
    ) -> None:
        """Test _load_audio falls back to librosa when soundfile raises RuntimeError."""
        from audio_processor.services.quality_assessor import QualityAssessor

        test_file = tmp_path / "audio.mp3"
        test_file.write_bytes(b"\x00" * 100)

        mock_sf_read.side_effect = RuntimeError("unsupported format")
        fake_audio = np.zeros(16000, dtype=np.float32)

        with patch(
            "audio_processor.services.quality_assessor.librosa.load",
            return_value=(fake_audio, 16000),
        ):
            assessor = QualityAssessor()
            audio, sr = assessor._load_audio(test_file)

        assert sr == 16000
        assert len(audio) == 16000

    @patch("soundfile.read")
    def test_load_audio_librosa_transpose_stereo(
        self, mock_sf_read: MagicMock, tmp_path: Path
    ) -> None:
        """Test _load_audio transposes librosa stereo output from [ch, samples] to [samples, ch]."""
        from audio_processor.services.quality_assessor import QualityAssessor

        test_file = tmp_path / "stereo.mp3"
        test_file.write_bytes(b"\x00" * 100)

        mock_sf_read.side_effect = RuntimeError("unsupported")
        # librosa returns shape [channels, samples] for stereo
        fake_audio = np.zeros((2, 16000), dtype=np.float32)

        with patch(
            "audio_processor.services.quality_assessor.librosa.load",
            return_value=(fake_audio, 16000),
        ):
            assessor = QualityAssessor()
            audio, _sr = assessor._load_audio(test_file)

        # After transpose, shape should be [samples, channels]
        assert audio.shape == (16000, 2)


class TestDeepgramClientInit:
    """Tests for DeepgramTranscriptionClient initialization."""

    def test_init_without_api_key(self) -> None:
        """Test initialization without API key raises error."""
        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        # Temporarily clear the settings
        with patch(
            "audio_processor.services.deepgram_client.settings"
        ) as mock_settings:
            mock_settings.deepgram_api_key = None

            with pytest.raises(ConfigurationError) as exc_info:
                DeepgramTranscriptionClient()
            assert "API key not configured" in str(exc_info.value)

    def test_init_with_api_key(self) -> None:
        """Test initialization with API key."""
        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        # This should not raise
        client = DeepgramTranscriptionClient(
            api_key="test-api-key",  # pragma: allowlist secret
        )
        assert client.api_key == "test-api-key"  # pragma: allowlist secret
        assert client.model == "nova-2"

    def test_custom_model(self) -> None:
        """Test initialization with custom model."""
        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        client = DeepgramTranscriptionClient(
            api_key="test-api-key",  # pragma: allowlist secret
            model="nova",
            language="es",
        )
        assert client.model == "nova"
        assert client.language == "es"


class TestDeepgramClientCostEstimate:
    """Tests for DeepgramTranscriptionClient cost estimation."""

    def test_cost_estimate_base(self) -> None:
        """Test base cost estimation."""
        from decimal import Decimal

        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        client = DeepgramTranscriptionClient(
            api_key="test-key",  # pragma: allowlist secret
        )

        # 1 hour = 60 minutes
        cost = client.estimate_cost(
            3600,
            enable_diarization=False,
            enable_summarization=False,
        )
        # Base rate: $0.0043/min * 60 = $0.258
        assert cost > Decimal("0.25")
        assert cost < Decimal("0.30")

    def test_cost_estimate_with_features(self) -> None:
        """Test cost estimation with all features."""
        from decimal import Decimal

        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        client = DeepgramTranscriptionClient(
            api_key="test-key",  # pragma: allowlist secret
        )

        # 1 hour with all features
        cost = client.estimate_cost(
            3600,
            enable_diarization=True,
            enable_summarization=True,
        )
        # Should be higher than base
        assert cost > Decimal("0.30")


class TestAudioConditionerInit:
    """Tests for AudioConditioner initialization."""

    def test_default_initialization(self) -> None:
        """Test default initialization."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        conditioner = AudioConditioner()
        assert conditioner.target_sample_rate == 16000
        assert conditioner.target_channels == 1
        assert conditioner.target_rms_db == -20.0

    def test_custom_initialization(self, tmp_path: Path) -> None:
        """Test custom initialization."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        custom_temp = tmp_path / "custom" / "temp"
        conditioner = AudioConditioner(
            target_sample_rate=44100,
            target_channels=2,
            target_rms_db=-18.0,
            temp_dir=str(custom_temp),
        )
        assert conditioner.target_sample_rate == 44100
        assert conditioner.target_channels == 2
        assert conditioner.target_rms_db == -18.0
        assert conditioner.temp_dir == custom_temp


class TestAudioConditionerCondition:
    """Tests for AudioConditioner.condition method."""

    def test_condition_file_not_found(self) -> None:
        """Test conditioning non-existent file."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        conditioner = AudioConditioner()
        with pytest.raises(ValidationError) as exc_info:
            conditioner.condition("/nonexistent/file.wav")
        assert "file not found" in str(exc_info.value).lower()

    def test_estimate_improvement_file_not_found(self) -> None:
        """Test estimate_improvement with non-existent file."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        conditioner = AudioConditioner()
        with pytest.raises(ValidationError) as exc_info:
            conditioner.estimate_improvement("/nonexistent/file.wav")
        assert "file not found" in str(exc_info.value).lower()

    @patch("soundfile.write")
    @patch("soundfile.read")
    def test_condition_mono_signal_with_output_path(
        self, mock_sf_read: MagicMock, mock_sf_write: MagicMock, tmp_path: Path
    ) -> None:
        """Test conditioning a mono signal with an explicit output path."""
        from audio_processor.services.audio_conditioner import (
            AudioConditioner,
            ConditioningResult,
        )

        input_file = tmp_path / "input.wav"
        input_file.write_bytes(b"RIFF" + b"\x00" * 100)
        output_file = tmp_path / "output.wav"

        t = np.linspace(0, 1, 16000, dtype=np.float64)
        fake_audio = 0.1 * np.sin(2 * np.pi * 440 * t)
        mock_sf_read.return_value = (fake_audio, 16000)

        conditioner = AudioConditioner(temp_dir=str(tmp_path))
        result = conditioner.condition(input_file, output_path=output_file)

        assert isinstance(result, ConditioningResult)
        assert result.output_path == output_file
        assert result.original_sample_rate == 16000
        assert result.target_sample_rate == 16000
        assert result.original_channels == 1
        mock_sf_write.assert_called_once()

    @patch("soundfile.write")
    @patch("soundfile.read")
    def test_condition_stereo_signal_converted_to_mono(
        self, mock_sf_read: MagicMock, mock_sf_write: MagicMock, tmp_path: Path
    ) -> None:
        """Test conditioning converts stereo audio to mono."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        input_file = tmp_path / "stereo.wav"
        input_file.write_bytes(b"RIFF" + b"\x00" * 100)
        output_file = tmp_path / "output.wav"

        stereo = np.zeros((16000, 2), dtype=np.float64)
        stereo[:, 0] = 0.2
        stereo[:, 1] = -0.2
        mock_sf_read.return_value = (stereo, 16000)

        conditioner = AudioConditioner(temp_dir=str(tmp_path))
        result = conditioner.condition(input_file, output_path=output_file)

        assert result.original_channels == 2

    @patch("soundfile.write")
    @patch("soundfile.read")
    def test_condition_dc_offset_is_removed(
        self, mock_sf_read: MagicMock, mock_sf_write: MagicMock, tmp_path: Path
    ) -> None:
        """Test conditioning removes DC offset when present."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        input_file = tmp_path / "dc.wav"
        input_file.write_bytes(b"RIFF" + b"\x00" * 100)
        output_file = tmp_path / "output.wav"

        t = np.linspace(0, 1, 16000, dtype=np.float64)
        # Signal with significant DC offset
        fake_audio = 0.1 * np.sin(2 * np.pi * 440 * t) + 0.05
        mock_sf_read.return_value = (fake_audio, 16000)

        conditioner = AudioConditioner(temp_dir=str(tmp_path))
        result = conditioner.condition(
            input_file, output_path=output_file, remove_dc=True
        )

        assert result.dc_offset_removed is True

    @patch("soundfile.write")
    @patch("soundfile.read")
    def test_condition_auto_creates_temp_output(
        self, mock_sf_read: MagicMock, mock_sf_write: MagicMock, tmp_path: Path
    ) -> None:
        """Test condition auto-creates a temp WAV output when no path provided."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        input_file = tmp_path / "input.wav"
        input_file.write_bytes(b"RIFF" + b"\x00" * 100)

        fake_audio = 0.2 * np.ones(16000, dtype=np.float64)
        mock_sf_read.return_value = (fake_audio, 16000)

        conditioner = AudioConditioner(temp_dir=str(tmp_path))
        result = conditioner.condition(input_file)

        assert result.output_path.suffix == ".wav"
        assert result.output_path.parent == tmp_path

    @patch("soundfile.read")
    def test_condition_raises_audio_processor_error_on_oserror(
        self, mock_sf_read: MagicMock, tmp_path: Path
    ) -> None:
        """Test condition raises AudioProcessorError when file IO fails."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        input_file = tmp_path / "bad.wav"
        input_file.write_bytes(b"\x00" * 100)

        mock_sf_read.side_effect = OSError("disk error")

        conditioner = AudioConditioner(temp_dir=str(tmp_path))
        with pytest.raises(AudioProcessorError) as exc_info:
            conditioner.condition(input_file)
        assert "condition" in str(exc_info.value).lower()

    @patch("soundfile.write")
    @patch("soundfile.read")
    def test_condition_resamples_when_rates_differ(
        self, mock_sf_read: MagicMock, mock_sf_write: MagicMock, tmp_path: Path
    ) -> None:
        """Test condition resamples when source and target sample rates differ."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        input_file = tmp_path / "input.wav"
        input_file.write_bytes(b"RIFF" + b"\x00" * 100)
        output_file = tmp_path / "output.wav"

        # Provide 44100 Hz audio; conditioner targets 16000
        t = np.linspace(0, 1, 44100, dtype=np.float64)
        fake_audio = 0.2 * np.sin(2 * np.pi * 440 * t)
        mock_sf_read.return_value = (fake_audio, 44100)

        conditioner = AudioConditioner(temp_dir=str(tmp_path))
        result = conditioner.condition(input_file, output_path=output_file)

        assert result.original_sample_rate == 44100
        assert result.target_sample_rate == 16000


class TestAudioConditionerEstimateImprovement:
    """Tests for AudioConditioner.estimate_improvement method."""

    @patch("soundfile.read")
    def test_estimate_improvement_mono_normalized_signal(
        self, mock_sf_read: MagicMock, tmp_path: Path
    ) -> None:
        """Test estimate_improvement on a well-conditioned mono signal."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        input_file = tmp_path / "good.wav"
        input_file.write_bytes(b"RIFF" + b"\x00" * 100)

        t = np.linspace(0, 1, 16000, dtype=np.float64)
        fake_audio = 0.1 * np.sin(2 * np.pi * 440 * t)
        mock_sf_read.return_value = (fake_audio, 16000)

        conditioner = AudioConditioner(temp_dir=str(tmp_path))
        result = conditioner.estimate_improvement(input_file)

        assert "needs_resample" in result
        assert result["current_sample_rate"] == 16000
        assert result["needs_mono_conversion"] is False

    @patch("soundfile.read")
    def test_estimate_improvement_stereo_needs_mono(
        self, mock_sf_read: MagicMock, tmp_path: Path
    ) -> None:
        """Test estimate_improvement flags stereo audio as needing mono conversion."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        input_file = tmp_path / "stereo.wav"
        input_file.write_bytes(b"RIFF" + b"\x00" * 100)

        stereo = np.zeros((16000, 2), dtype=np.float64)
        stereo[:, 0] = 0.2
        mock_sf_read.return_value = (stereo, 16000)

        conditioner = AudioConditioner(temp_dir=str(tmp_path))
        result = conditioner.estimate_improvement(input_file)

        assert result["needs_mono_conversion"] is True
        assert result["current_channels"] == 2

    @patch("soundfile.read")
    def test_estimate_improvement_low_sample_rate_high_benefit(
        self, mock_sf_read: MagicMock, tmp_path: Path
    ) -> None:
        """Test estimate_improvement reports high benefit for sub-16kHz audio."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        input_file = tmp_path / "lowrate.wav"
        input_file.write_bytes(b"RIFF" + b"\x00" * 100)

        t = np.linspace(0, 1, 8000, dtype=np.float64)
        fake_audio = 0.2 * np.sin(2 * np.pi * 440 * t)
        mock_sf_read.return_value = (fake_audio, 8000)

        conditioner = AudioConditioner(temp_dir=str(tmp_path))
        result = conditioner.estimate_improvement(input_file)

        assert result["needs_resample"] is True
        assert result["resample_benefit"] == "high"

    @patch("soundfile.read")
    def test_estimate_improvement_raises_audio_processor_error(
        self, mock_sf_read: MagicMock, tmp_path: Path
    ) -> None:
        """Test estimate_improvement raises AudioProcessorError on OSError."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        input_file = tmp_path / "broken.wav"
        input_file.write_bytes(b"\x00" * 100)

        mock_sf_read.side_effect = OSError("cannot read")

        conditioner = AudioConditioner(temp_dir=str(tmp_path))
        with pytest.raises(AudioProcessorError):
            conditioner.estimate_improvement(input_file)


class TestAudioConditionerRMS:
    """Tests for AudioConditioner RMS calculations."""

    def test_calculate_rms_db_silence(self) -> None:
        """Test RMS calculation for silence."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        conditioner = AudioConditioner()
        silence = np.zeros(1000)
        rms_db = conditioner._calculate_rms_db(silence)
        assert rms_db == -96.0  # Silence floor

    def test_calculate_rms_db_full_scale(self) -> None:
        """Test RMS calculation for full-scale sine wave."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        conditioner = AudioConditioner()
        # Full-scale sine wave has RMS of ~0.707 (-3 dBFS)
        t = np.linspace(0, 1, 44100)
        sine_wave = np.sin(2 * np.pi * 440 * t)
        rms_db = conditioner._calculate_rms_db(sine_wave)
        assert -4 < rms_db < -2  # Approximately -3 dBFS


class TestAudioConditionerNormalize:
    """Tests for AudioConditioner normalization."""

    def test_normalize_rms(self) -> None:
        """Test RMS normalization."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        conditioner = AudioConditioner()

        # Create a quiet signal
        t = np.linspace(0, 1, 16000)
        quiet_signal = 0.01 * np.sin(2 * np.pi * 440 * t)

        # Normalize to -20 dBFS
        normalized, gain_db = conditioner._normalize_rms(quiet_signal, -20.0)

        # Should have applied positive gain
        assert gain_db > 0
        # Output should be louder
        assert np.max(np.abs(normalized)) > np.max(np.abs(quiet_signal))

    def test_normalize_rms_silence(self) -> None:
        """Test RMS normalization with silence."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        conditioner = AudioConditioner()
        silence = np.zeros(1000)
        normalized, gain_db = conditioner._normalize_rms(silence, -20.0)

        # Should not crash, gain should be 0
        assert gain_db == 0.0
        assert np.array_equal(normalized, silence)

    def test_normalize_rms_applies_soft_clip_when_peak_exceeds_threshold(
        self,
    ) -> None:
        """Test _normalize_rms soft-clips when normalized peak exceeds 0.99."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        conditioner = AudioConditioner()
        # Very quiet signal that normalizing to 0 dB will push over 0.99
        t = np.linspace(0, 1, 16000)
        loud_target = 0.001 * np.sin(2 * np.pi * 440 * t)

        normalized, _gain_db = conditioner._normalize_rms(loud_target, 0.0)

        # Output should not exceed 1.0 due to soft clipping
        assert np.max(np.abs(normalized)) <= 1.0


class TestAudioConditionerLoadAudio:
    """Tests for AudioConditioner._load_audio method."""

    @patch("soundfile.read")
    def test_load_audio_falls_back_to_librosa(
        self, mock_sf_read: MagicMock, tmp_path: Path
    ) -> None:
        """Test _load_audio uses librosa when soundfile raises RuntimeError."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        test_file = tmp_path / "audio.mp3"
        test_file.write_bytes(b"\x00" * 100)

        mock_sf_read.side_effect = RuntimeError("not supported")
        fake_audio = np.zeros(16000, dtype=np.float32)

        with patch(
            "audio_processor.services.audio_conditioner.librosa.load",
            return_value=(fake_audio, 16000),
        ):
            conditioner = AudioConditioner()
            _audio, sr = conditioner._load_audio(test_file)

        assert sr == 16000

    @patch("soundfile.read")
    def test_load_audio_librosa_transposes_stereo(
        self, mock_sf_read: MagicMock, tmp_path: Path
    ) -> None:
        """Test _load_audio transposes librosa stereo [ch, samples] to [samples, ch]."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        test_file = tmp_path / "stereo.mp3"
        test_file.write_bytes(b"\x00" * 100)

        mock_sf_read.side_effect = RuntimeError("not supported")
        fake_stereo = np.zeros((2, 16000), dtype=np.float32)

        with patch(
            "audio_processor.services.audio_conditioner.librosa.load",
            return_value=(fake_stereo, 16000),
        ):
            conditioner = AudioConditioner()
            audio, _sr = conditioner._load_audio(test_file)

        assert audio.shape == (16000, 2)


class TestVADProcessorInit:
    """Tests for VADProcessor initialization."""

    def test_default_initialization(self) -> None:
        """Test default initialization."""
        from audio_processor.services.vad_processor import VADProcessor

        vad = VADProcessor()
        assert vad.threshold == 0.5
        assert vad.min_silence_duration_ms == 500
        assert vad.min_speech_duration_ms == 250

    def test_custom_initialization(self, tmp_path: Path) -> None:
        """Test custom initialization."""
        from audio_processor.services.vad_processor import VADProcessor

        custom_temp = tmp_path / "custom" / "temp"
        vad = VADProcessor(
            threshold=0.7,
            min_silence_duration_ms=300,
            min_speech_duration_ms=100,
            temp_dir=str(custom_temp),
        )
        assert vad.threshold == 0.7
        assert vad.min_silence_duration_ms == 300
        assert vad.min_speech_duration_ms == 100
        assert vad.temp_dir == custom_temp


class TestVADProcessorLoadModel:
    """Tests for VADProcessor._load_model method."""

    def test_load_model_caches_result(self) -> None:
        """Test _load_model caches model as class attribute after first load."""
        from audio_processor.services.vad_processor import VADProcessor

        # Reset class-level cache before test
        original_model = VADProcessor._model
        original_utils = VADProcessor._utils
        VADProcessor._model = None
        VADProcessor._utils = None

        fake_model = MagicMock(spec=object)
        fake_utils = (MagicMock(), MagicMock())

        with patch(
            "audio_processor.services.vad_processor.torch.hub.load",
            return_value=(fake_model, fake_utils),
        ) as mock_hub_load:
            vad = VADProcessor()
            model1, _utils1 = vad._load_model()
            model2, _utils2 = vad._load_model()

        # torch.hub.load should only be called once
        mock_hub_load.assert_called_once()
        assert model1 is model2

        # Restore original state
        VADProcessor._model = original_model
        VADProcessor._utils = original_utils

    def test_load_model_returns_cached_when_already_loaded(self) -> None:
        """Test _load_model returns existing cache without calling torch.hub.load."""
        from audio_processor.services.vad_processor import VADProcessor

        fake_model = MagicMock(spec=object)
        fake_utils = (MagicMock(), MagicMock())

        original_model = VADProcessor._model
        original_utils = VADProcessor._utils
        VADProcessor._model = fake_model  # type: ignore[assignment]
        VADProcessor._utils = fake_utils  # type: ignore[assignment]

        try:
            with patch(
                "audio_processor.services.vad_processor.torch.hub.load"
            ) as mock_hub_load:
                vad = VADProcessor()
                model, _utils = vad._load_model()

            mock_hub_load.assert_not_called()
            assert model is fake_model
        finally:
            VADProcessor._model = original_model
            VADProcessor._utils = original_utils


class TestVADProcessorDetect:
    """Tests for VADProcessor.detect_speech method."""

    def test_detect_speech_file_not_found(self) -> None:
        """Test detecting speech in non-existent file."""
        from audio_processor.services.vad_processor import VADProcessor

        vad = VADProcessor()
        with pytest.raises(ValidationError) as exc_info:
            vad.detect_speech("/nonexistent/file.wav")
        assert "file not found" in str(exc_info.value).lower()

    @patch("soundfile.read")
    def test_detect_speech_returns_vad_result(
        self, mock_sf_read: MagicMock, tmp_path: Path
    ) -> None:
        """Test detect_speech returns correct VADResult for a simple signal."""
        from audio_processor.services.vad_processor import VADProcessor, VADResult

        test_file = tmp_path / "audio.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)

        t = np.linspace(0, 2, 32000, dtype=np.float32)
        fake_audio = 0.3 * np.sin(2 * np.pi * 440 * t)
        mock_sf_read.return_value = (fake_audio, 16000)

        fake_model = MagicMock()
        fake_get_timestamps = MagicMock(
            return_value=[{"start": 0, "end": 16000}, {"start": 24000, "end": 32000}]
        )

        with patch.object(
            VADProcessor,
            "_load_model",
            return_value=(fake_model, (fake_get_timestamps,)),
        ):
            vad = VADProcessor()
            result = vad.detect_speech(test_file)

        assert isinstance(result, VADResult)
        assert len(result.segments) == 2
        assert result.original_duration == pytest.approx(2.0, abs=0.01)

    @patch("soundfile.read")
    def test_detect_speech_resamples_non_16khz_audio(
        self, mock_sf_read: MagicMock, tmp_path: Path
    ) -> None:
        """Test detect_speech resamples audio that is not 16kHz."""
        from audio_processor.services.vad_processor import VADProcessor

        test_file = tmp_path / "audio.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)

        t = np.linspace(0, 1, 44100, dtype=np.float32)
        fake_audio = 0.3 * np.sin(2 * np.pi * 440 * t)
        # Source is 44100 Hz
        mock_sf_read.return_value = (fake_audio, 44100)

        fake_model = MagicMock()
        fake_get_timestamps = MagicMock(return_value=[])

        with (
            patch.object(
                VADProcessor,
                "_load_model",
                return_value=(fake_model, (fake_get_timestamps,)),
            ),
            patch(
                "librosa.resample", return_value=np.zeros(16000, dtype=np.float32)
            ) as mock_resample,
        ):
            vad = VADProcessor()
            result = vad.detect_speech(test_file)

        mock_resample.assert_called_once()
        assert result.segments == ()

    @patch("soundfile.read")
    def test_detect_speech_handles_stereo_by_taking_mean(
        self, mock_sf_read: MagicMock, tmp_path: Path
    ) -> None:
        """Test detect_speech converts stereo to mono before VAD."""
        from audio_processor.services.vad_processor import VADProcessor

        test_file = tmp_path / "stereo.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)

        stereo = np.zeros((16000, 2), dtype=np.float32)
        mock_sf_read.return_value = (stereo, 16000)

        fake_model = MagicMock()
        fake_get_timestamps = MagicMock(return_value=[])

        with patch.object(
            VADProcessor,
            "_load_model",
            return_value=(fake_model, (fake_get_timestamps,)),
        ):
            vad = VADProcessor()
            result = vad.detect_speech(test_file)

        assert result.segments == ()

    @patch("soundfile.read")
    def test_detect_speech_raises_audio_processor_error_on_exception(
        self, mock_sf_read: MagicMock, tmp_path: Path
    ) -> None:
        """Test detect_speech wraps unexpected errors in AudioProcessorError."""
        from audio_processor.services.vad_processor import VADProcessor

        test_file = tmp_path / "audio.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)

        mock_sf_read.side_effect = RuntimeError("unexpected failure")

        vad = VADProcessor()
        with pytest.raises(AudioProcessorError) as exc_info:
            vad.detect_speech(test_file)
        assert "VAD processing failed" in str(exc_info.value)


class TestVADProcessorProcess:
    """Tests for VADProcessor.process_audio method."""

    def test_process_audio_file_not_found(self) -> None:
        """Test processing non-existent file."""
        from audio_processor.services.vad_processor import VADProcessor

        vad = VADProcessor()
        with pytest.raises(ValidationError) as exc_info:
            vad.process_audio("/nonexistent/file.wav")
        assert "file not found" in str(exc_info.value).lower()

    @patch("soundfile.write")
    @patch("soundfile.read")
    def test_process_audio_removes_silence_and_writes_output(
        self, mock_sf_read: MagicMock, mock_sf_write: MagicMock, tmp_path: Path
    ) -> None:
        """Test process_audio concatenates speech segments and writes output."""
        from audio_processor.services.vad_processor import (
            SpeechSegment,
            VADProcessor,
            VADResult,
        )

        test_file = tmp_path / "audio.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)
        output_file = tmp_path / "processed.wav"

        fake_audio = 0.3 * np.ones(32000, dtype=np.float64)
        # First call (detect_speech, float32), second call (process_audio, float64)
        mock_sf_read.side_effect = [
            (fake_audio.astype(np.float32), 16000),
            (fake_audio, 16000),
        ]

        segment = SpeechSegment(start=0.0, end=1.0)
        fake_vad_result = VADResult(
            segments=(segment,),
            total_speech_duration=1.0,
            total_silence_duration=1.0,
            speech_ratio=0.5,
            original_duration=2.0,
        )

        with patch.object(VADProcessor, "detect_speech", return_value=fake_vad_result):
            vad = VADProcessor(temp_dir=str(tmp_path))
            result = vad.process_audio(
                test_file, output_path=output_file, remove_silence=True
            )

        assert result.processed_path == output_file
        mock_sf_write.assert_called_once()

    @patch("soundfile.write")
    @patch("soundfile.read")
    def test_process_audio_no_silence_removal_returns_detect_result(
        self, mock_sf_read: MagicMock, mock_sf_write: MagicMock, tmp_path: Path
    ) -> None:
        """Test process_audio with remove_silence=False returns detect_speech result."""
        from audio_processor.services.vad_processor import (
            SpeechSegment,
            VADProcessor,
            VADResult,
        )

        test_file = tmp_path / "audio.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)

        segment = SpeechSegment(start=0.0, end=1.0)
        fake_vad_result = VADResult(
            segments=(segment,),
            total_speech_duration=1.0,
            total_silence_duration=1.0,
            speech_ratio=0.5,
            original_duration=2.0,
        )

        with patch.object(VADProcessor, "detect_speech", return_value=fake_vad_result):
            vad = VADProcessor(temp_dir=str(tmp_path))
            result = vad.process_audio(test_file, remove_silence=False)

        assert result is fake_vad_result
        mock_sf_write.assert_not_called()

    @patch("soundfile.write")
    @patch("soundfile.read")
    def test_process_audio_empty_segments_returns_detect_result(
        self, mock_sf_read: MagicMock, mock_sf_write: MagicMock, tmp_path: Path
    ) -> None:
        """Test process_audio with no speech segments returns detect_speech result directly."""
        from audio_processor.services.vad_processor import VADProcessor, VADResult

        test_file = tmp_path / "silence.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)

        fake_vad_result = VADResult(
            segments=(),
            total_speech_duration=0.0,
            total_silence_duration=2.0,
            speech_ratio=0.0,
            original_duration=2.0,
        )

        with patch.object(VADProcessor, "detect_speech", return_value=fake_vad_result):
            vad = VADProcessor(temp_dir=str(tmp_path))
            result = vad.process_audio(test_file, remove_silence=True)

        assert result is fake_vad_result
        mock_sf_write.assert_not_called()

    @patch("soundfile.write")
    @patch("soundfile.read")
    def test_process_audio_auto_creates_temp_output(
        self, mock_sf_read: MagicMock, mock_sf_write: MagicMock, tmp_path: Path
    ) -> None:
        """Test process_audio creates a temp WAV file when no output path given."""
        from audio_processor.services.vad_processor import (
            SpeechSegment,
            VADProcessor,
            VADResult,
        )

        test_file = tmp_path / "audio.wav"
        test_file.write_bytes(b"RIFF" + b"\x00" * 100)

        fake_audio = np.zeros(32000, dtype=np.float64)
        mock_sf_read.return_value = (fake_audio, 16000)

        segment = SpeechSegment(start=0.0, end=1.0)
        fake_vad_result = VADResult(
            segments=(segment,),
            total_speech_duration=1.0,
            total_silence_duration=1.0,
            speech_ratio=0.5,
            original_duration=2.0,
        )

        with patch.object(VADProcessor, "detect_speech", return_value=fake_vad_result):
            vad = VADProcessor(temp_dir=str(tmp_path))
            result = vad.process_audio(test_file)

        assert result.processed_path is not None
        assert result.processed_path.suffix == ".wav"
        assert result.processed_path.parent == tmp_path


class TestVADProcessorShouldProcess:
    """Tests for VADProcessor.should_process method."""

    def test_should_process_returns_true_when_silence_ratio_high(
        self, tmp_path: Path
    ) -> None:
        """Test should_process returns True when silence ratio meets threshold."""
        from audio_processor.services.vad_processor import VADProcessor, VADResult

        test_file = tmp_path / "audio.wav"
        test_file.write_bytes(b"\x00" * 100)

        fake_result = VADResult(
            segments=(),
            total_speech_duration=0.5,
            total_silence_duration=1.5,
            speech_ratio=0.25,
            original_duration=2.0,
        )

        with patch.object(VADProcessor, "detect_speech", return_value=fake_result):
            vad = VADProcessor()
            assert vad.should_process(test_file, min_silence_ratio=0.3) is True

    def test_should_process_returns_false_when_mostly_speech(
        self, tmp_path: Path
    ) -> None:
        """Test should_process returns False when silence ratio is below threshold."""
        from audio_processor.services.vad_processor import VADProcessor, VADResult

        test_file = tmp_path / "audio.wav"
        test_file.write_bytes(b"\x00" * 100)

        fake_result = VADResult(
            segments=(),
            total_speech_duration=1.8,
            total_silence_duration=0.2,
            speech_ratio=0.9,
            original_duration=2.0,
        )

        with patch.object(VADProcessor, "detect_speech", return_value=fake_result):
            vad = VADProcessor()
            assert vad.should_process(test_file, min_silence_ratio=0.3) is False

    def test_should_process_returns_false_on_error(self) -> None:
        """Test should_process returns False when detect_speech raises an error."""
        from audio_processor.services.vad_processor import VADProcessor

        vad = VADProcessor()
        # Non-existent file will trigger ValidationError inside detect_speech
        assert vad.should_process("/nonexistent/file.wav") is False


class TestVADProcessorTimestamp:
    """Tests for VADProcessor timestamp mapping."""

    def test_map_timestamp_empty(self) -> None:
        """Test timestamp mapping with empty map."""
        from audio_processor.services.vad_processor import VADProcessor

        vad = VADProcessor()
        result = vad.map_timestamp(5.0, ())
        assert result == 5.0

    def test_map_timestamp_single_segment(self) -> None:
        """Test timestamp mapping with single segment."""
        from audio_processor.services.vad_processor import VADProcessor

        vad = VADProcessor()
        # Timeline: output time 0.0 maps to original time 2.0
        timeline_map = ((0.0, 2.0),)
        result = vad.map_timestamp(1.0, timeline_map)
        assert result == 3.0  # 2.0 + 1.0

    def test_map_timestamp_multiple_segments(self) -> None:
        """Test timestamp mapping with multiple segments."""
        from audio_processor.services.vad_processor import VADProcessor

        vad = VADProcessor()
        # Two segments: [0-2] maps to [1-3], [2-4] maps to [5-7]
        timeline_map = ((0.0, 1.0), (2.0, 5.0))

        # First segment
        assert vad.map_timestamp(1.0, timeline_map) == 2.0  # 1.0 + 1.0

        # Second segment
        assert vad.map_timestamp(3.0, timeline_map) == 6.0  # 5.0 + 1.0


class TestSpeechSegment:
    """Tests for SpeechSegment dataclass."""

    def test_speech_segment_duration(self) -> None:
        """Test speech segment duration calculation."""
        from audio_processor.services.vad_processor import SpeechSegment

        segment = SpeechSegment(start=1.5, end=4.5)
        assert segment.duration == 3.0

    def test_speech_segment_with_confidence(self) -> None:
        """Test speech segment with custom confidence."""
        from audio_processor.services.vad_processor import SpeechSegment

        segment = SpeechSegment(start=0.0, end=1.0, confidence=0.95)
        assert segment.confidence == 0.95
