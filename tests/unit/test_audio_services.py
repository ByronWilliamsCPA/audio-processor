"""Unit tests for audio processing services."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from audio_processor.core.config import Settings
from audio_processor.core.exceptions import AudioProcessorError, ConfigurationError, ValidationError
from audio_processor.core.models import QualityLevel


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
        from audio_processor.services.audio_converter import MIME_TYPE_MAP
        from audio_processor.core.models import AudioFormat

        assert MIME_TYPE_MAP["audio/mpeg"] == AudioFormat.MP3
        assert MIME_TYPE_MAP["audio/wav"] == AudioFormat.WAV
        assert MIME_TYPE_MAP["video/mp4"] == AudioFormat.MP4

    def test_extension_mapping(self) -> None:
        """Test file extension to format mapping."""
        from audio_processor.services.audio_converter import EXTENSION_MAP
        from audio_processor.core.models import AudioFormat

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

    def test_custom_initialization(self) -> None:
        """Test custom initialization."""
        from audio_processor.services.audio_converter import AudioConverter

        converter = AudioConverter(
            temp_dir="/custom/temp",
            target_sample_rate=44100,
            target_channels=2,
        )
        assert converter.target_sample_rate == 44100
        assert converter.target_channels == 2
        assert converter.temp_dir == Path("/custom/temp")


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


class TestAudioConverterValidation:
    """Tests for AudioConverter.validate_file method."""

    def test_validate_file_not_found(self) -> None:
        """Test validating non-existent file."""
        from audio_processor.services.audio_converter import AudioConverter

        converter = AudioConverter()
        with pytest.raises(ValidationError) as exc_info:
            converter.validate_file("/nonexistent/file.wav")
        assert "File not found" in str(exc_info.value)


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


class TestDeepgramClientInit:
    """Tests for DeepgramTranscriptionClient initialization."""

    def test_init_without_api_key(self) -> None:
        """Test initialization without API key raises error."""
        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        # Temporarily clear the settings
        with patch("audio_processor.services.deepgram_client.settings") as mock_settings:
            mock_settings.deepgram_api_key = None

            with pytest.raises(ConfigurationError) as exc_info:
                DeepgramTranscriptionClient()
            assert "API key not configured" in str(exc_info.value)

    def test_init_with_api_key(self) -> None:
        """Test initialization with API key."""
        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        # This should not raise
        client = DeepgramTranscriptionClient(api_key="test-api-key")
        assert client.api_key == "test-api-key"
        assert client.model == "nova-2"

    def test_custom_model(self) -> None:
        """Test initialization with custom model."""
        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        client = DeepgramTranscriptionClient(
            api_key="test-api-key",
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

        client = DeepgramTranscriptionClient(api_key="test-key")

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

        client = DeepgramTranscriptionClient(api_key="test-key")

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

    def test_custom_initialization(self) -> None:
        """Test custom initialization."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        conditioner = AudioConditioner(
            target_sample_rate=44100,
            target_channels=2,
            target_rms_db=-18.0,
            temp_dir="/custom/temp",
        )
        assert conditioner.target_sample_rate == 44100
        assert conditioner.target_channels == 2
        assert conditioner.target_rms_db == -18.0
        assert conditioner.temp_dir == Path("/custom/temp")


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


class TestAudioConditionerRMS:
    """Tests for AudioConditioner RMS calculations."""

    def test_calculate_rms_db_silence(self) -> None:
        """Test RMS calculation for silence."""
        import numpy as np
        from audio_processor.services.audio_conditioner import AudioConditioner

        conditioner = AudioConditioner()
        silence = np.zeros(1000)
        rms_db = conditioner._calculate_rms_db(silence)
        assert rms_db == -96.0  # Silence floor

    def test_calculate_rms_db_full_scale(self) -> None:
        """Test RMS calculation for full-scale sine wave."""
        import numpy as np
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
        import numpy as np
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
        import numpy as np
        from audio_processor.services.audio_conditioner import AudioConditioner

        conditioner = AudioConditioner()
        silence = np.zeros(1000)
        normalized, gain_db = conditioner._normalize_rms(silence, -20.0)

        # Should not crash, gain should be 0
        assert gain_db == 0.0
        assert np.array_equal(normalized, silence)


class TestVADProcessorInit:
    """Tests for VADProcessor initialization."""

    def test_default_initialization(self) -> None:
        """Test default initialization."""
        from audio_processor.services.vad_processor import VADProcessor

        vad = VADProcessor()
        assert vad.threshold == 0.5
        assert vad.min_silence_duration_ms == 500
        assert vad.min_speech_duration_ms == 250

    def test_custom_initialization(self) -> None:
        """Test custom initialization."""
        from audio_processor.services.vad_processor import VADProcessor

        vad = VADProcessor(
            threshold=0.7,
            min_silence_duration_ms=300,
            min_speech_duration_ms=100,
            temp_dir="/custom/temp",
        )
        assert vad.threshold == 0.7
        assert vad.min_silence_duration_ms == 300
        assert vad.min_speech_duration_ms == 100
        assert vad.temp_dir == Path("/custom/temp")


class TestVADProcessorDetect:
    """Tests for VADProcessor.detect_speech method."""

    def test_detect_speech_file_not_found(self) -> None:
        """Test detecting speech in non-existent file."""
        from audio_processor.services.vad_processor import VADProcessor

        vad = VADProcessor()
        with pytest.raises(ValidationError) as exc_info:
            vad.detect_speech("/nonexistent/file.wav")
        assert "file not found" in str(exc_info.value).lower()


class TestVADProcessorProcess:
    """Tests for VADProcessor.process_audio method."""

    def test_process_audio_file_not_found(self) -> None:
        """Test processing non-existent file."""
        from audio_processor.services.vad_processor import VADProcessor

        vad = VADProcessor()
        with pytest.raises(ValidationError) as exc_info:
            vad.process_audio("/nonexistent/file.wav")
        assert "file not found" in str(exc_info.value).lower()


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
