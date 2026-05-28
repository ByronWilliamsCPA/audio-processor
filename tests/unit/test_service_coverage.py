"""Unit tests targeting coverage gaps in service modules.

Covers:
- DeepgramTranscriptionClient: transcribe, _parse_response, _parse_utterances_and_speakers
- QualityAssessor: assess, internal calculation methods
- AudioConditioner: condition, estimate_improvement, normalization helpers
- VADProcessor: detect_speech, process_audio, map_timestamp, should_process
- AudioConverter: probe, detect_format, extract_audio, convert_for_asr, validate_file
"""

from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from audio_processor.core.exceptions import (
    AudioProcessorError,
    ConfigurationError,
    TranscriptionError,
    ValidationError,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_audio(
    n_samples: int = 16000,
    sample_rate: int = 16000,
    seed: int = 42,
) -> tuple[np.ndarray, int]:  # type: ignore[type-arg]
    """Return a deterministic mono audio array and its sample rate."""
    rng = np.random.default_rng(seed)
    return rng.standard_normal(n_samples).astype(np.float64), sample_rate


def _make_stereo_audio(n_samples: int = 16000) -> np.ndarray:  # type: ignore[type-arg]
    """Return a stereo (N, 2) audio array."""
    rng = np.random.default_rng(0)
    return rng.standard_normal((n_samples, 2)).astype(np.float64)


# ---------------------------------------------------------------------------
# DeepgramTranscriptionClient
# ---------------------------------------------------------------------------


class TestDeepgramClientInit:
    """Tests for DeepgramTranscriptionClient init edge cases."""

    def test_uses_settings_api_key(self) -> None:
        """API key from settings is used when none provided explicitly."""
        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        mock_client = MagicMock()
        with (
            patch("audio_processor.services.deepgram_client.settings") as mock_settings,
            patch(
                "audio_processor.services.deepgram_client._deepgram_available",
                new=True,
            ),
            patch(
                "audio_processor.services.deepgram_client._DeepgramClient",
                return_value=mock_client,
            ),
        ):
            mock_settings.deepgram_api_key = MagicMock()
            mock_settings.deepgram_api_key.get_secret_value.return_value = (
                "from-settings"  # pragma: allowlist secret
            )
            mock_settings.deepgram_model = "nova-2"
            mock_settings.deepgram_language = "en"
            mock_settings.deepgram_timeout_seconds = 300

            client = DeepgramTranscriptionClient()
            assert client.api_key == "from-settings"  # pragma: allowlist secret

    def test_raises_when_deepgram_not_installed(self) -> None:
        """ConfigurationError raised when deepgram package is missing."""
        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        with (
            patch(
                "audio_processor.services.deepgram_client._deepgram_available",
                new=False,
            ),
            pytest.raises(ConfigurationError, match="deepgram package not installed"),
        ):
            DeepgramTranscriptionClient(api_key="key")  # pragma: allowlist secret

    def test_raises_when_client_init_fails(self) -> None:
        """ConfigurationError raised when _DeepgramClient constructor throws."""
        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        with (
            patch(
                "audio_processor.services.deepgram_client._deepgram_available",
                new=True,
            ),
            patch(
                "audio_processor.services.deepgram_client._DeepgramClient",
                side_effect=RuntimeError("bad key"),
            ),
            pytest.raises(ConfigurationError, match="Failed to initialize"),
        ):
            DeepgramTranscriptionClient(api_key="bad")  # pragma: allowlist secret


class TestDeepgramTranscribe:
    """Tests for DeepgramTranscriptionClient.transcribe."""

    def _make_client(self) -> tuple[object, MagicMock]:
        """Return (client, mock_inner_client)."""
        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        mock_inner = MagicMock()
        with (
            patch(
                "audio_processor.services.deepgram_client._deepgram_available",
                new=True,
            ),
            patch(
                "audio_processor.services.deepgram_client._DeepgramClient",
                return_value=mock_inner,
            ),
        ):
            client = DeepgramTranscriptionClient(
                api_key="test-key",  # pragma: allowlist secret
            )
        return client, mock_inner

    def test_transcribe_file_not_found(self, tmp_path: Path) -> None:
        """ValidationError raised for missing audio file."""
        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        with (
            patch(
                "audio_processor.services.deepgram_client._deepgram_available",
                new=True,
            ),
            patch(
                "audio_processor.services.deepgram_client._DeepgramClient",
                return_value=MagicMock(),
            ),
        ):
            client = DeepgramTranscriptionClient(
                api_key="test-key",  # pragma: allowlist secret
            )
            with pytest.raises(ValidationError, match="Audio file not found"):
                client.transcribe(tmp_path / "missing.wav")

    def test_transcribe_unauthorized_error(self, tmp_path: Path) -> None:
        """401 unauthorized maps to TranscriptionError with status 401."""
        client, mock_inner = self._make_client()

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 100)

        mock_inner.listen.rest.v.return_value.transcribe_file.side_effect = Exception(
            "401 unauthorized"
        )

        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        assert isinstance(client, DeepgramTranscriptionClient)
        with pytest.raises(TranscriptionError) as exc_info:
            client.transcribe(audio_file)
        assert exc_info.value.details.get("status_code") == 401

    def test_transcribe_rate_limit_error(self, tmp_path: Path) -> None:
        """Rate-limit 429 error maps to TranscriptionError with status 429."""
        client, mock_inner = self._make_client()
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 100)
        mock_inner.listen.rest.v.return_value.transcribe_file.side_effect = Exception(
            "429 rate limit exceeded"
        )

        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        assert isinstance(client, DeepgramTranscriptionClient)
        with pytest.raises(TranscriptionError) as exc_info:
            client.transcribe(audio_file)
        assert exc_info.value.details.get("status_code") == 429

    def test_transcribe_timeout_error(self, tmp_path: Path) -> None:
        """Timeout error maps to TranscriptionError with status 504."""
        client, mock_inner = self._make_client()
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 100)
        mock_inner.listen.rest.v.return_value.transcribe_file.side_effect = Exception(
            "connection timeout"
        )

        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        assert isinstance(client, DeepgramTranscriptionClient)
        with pytest.raises(TranscriptionError) as exc_info:
            client.transcribe(audio_file)
        assert exc_info.value.details.get("status_code") == 504

    def test_transcribe_generic_error(self, tmp_path: Path) -> None:
        """Generic exception maps to TranscriptionError."""
        client, mock_inner = self._make_client()
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 100)
        mock_inner.listen.rest.v.return_value.transcribe_file.side_effect = (
            RuntimeError("server error")
        )

        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        assert isinstance(client, DeepgramTranscriptionClient)
        with pytest.raises(TranscriptionError, match="Transcription failed"):
            client.transcribe(audio_file)

    def test_transcribe_success_with_diarization(self, tmp_path: Path) -> None:
        """Successful transcription with diarization returns TranscriptionResult."""
        client, mock_inner = self._make_client()
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 100)

        # Build mock response using SimpleNamespace for attribute access
        mock_word = SimpleNamespace(
            word="Hello",
            start=0.0,
            end=0.5,
            confidence=0.95,
            speaker=0,
            punctuated_word="Hello",
        )
        mock_alt = SimpleNamespace(
            transcript="Hello world",
            words=[mock_word],
        )
        mock_channel = SimpleNamespace(alternatives=[mock_alt])

        mock_utt = SimpleNamespace(
            speaker=0,
            start=0.0,
            end=1.0,
            transcript="Hello world",
            confidence=0.95,
            words=[mock_word],
        )
        mock_summary = SimpleNamespace(short="A greeting.")
        mock_metadata = SimpleNamespace(duration=2.5)
        mock_results = SimpleNamespace(
            channels=[mock_channel],
            utterances=[mock_utt],
            summary=mock_summary,
            metadata=mock_metadata,
        )
        mock_response = SimpleNamespace(results=mock_results)
        mock_inner.listen.rest.v.return_value.transcribe_file.return_value = (
            mock_response
        )

        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        assert isinstance(client, DeepgramTranscriptionClient)
        result = client.transcribe(
            audio_file, enable_diarization=True, enable_summarization=True
        )
        assert result.transcript == "Hello world"
        assert len(result.speakers) == 1
        assert result.summary == "A greeting."
        assert result.metadata.duration_seconds == 2.5

    def test_transcribe_no_diarization(self, tmp_path: Path) -> None:
        """Transcription without diarization returns result with no speakers."""
        client, mock_inner = self._make_client()
        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 100)

        mock_word = SimpleNamespace(
            word="Test",
            start=0.0,
            end=0.3,
            confidence=0.9,
            speaker=None,
            punctuated_word="Test.",
        )
        mock_alt = SimpleNamespace(transcript="Test.", words=[mock_word])
        mock_channel = SimpleNamespace(alternatives=[mock_alt])
        mock_metadata = SimpleNamespace(duration=1.0)
        mock_results = SimpleNamespace(
            channels=[mock_channel],
            utterances=None,
            summary=None,
            metadata=mock_metadata,
        )
        mock_response = SimpleNamespace(results=mock_results)
        mock_inner.listen.rest.v.return_value.transcribe_file.return_value = (
            mock_response
        )

        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        assert isinstance(client, DeepgramTranscriptionClient)
        result = client.transcribe(
            audio_file, enable_diarization=False, enable_summarization=False
        )
        assert result.transcript == "Test."
        assert len(result.speakers) == 0


class TestDeepgramParseResponse:
    """Tests for _parse_response edge cases."""

    def _client(self) -> object:
        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        with (
            patch(
                "audio_processor.services.deepgram_client._deepgram_available",
                new=True,
            ),
            patch(
                "audio_processor.services.deepgram_client._DeepgramClient",
                return_value=MagicMock(),
            ),
        ):
            return DeepgramTranscriptionClient(
                api_key="test-key",  # pragma: allowlist secret
            )

    def test_empty_response_returns_empty_result(self) -> None:
        """Response with no results returns empty TranscriptionResult."""
        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        client = self._client()
        assert isinstance(client, DeepgramTranscriptionClient)
        result = client._parse_response(  # type: ignore[attr-defined]
            SimpleNamespace(results=None),
            diarize=True,
            summarize=False,
            processing_time=0.1,
        )
        assert result.transcript == ""
        assert result.utterances == ()

    def test_no_channels_returns_empty_result(self) -> None:
        """Response with empty channels returns empty TranscriptionResult."""
        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        client = self._client()
        assert isinstance(client, DeepgramTranscriptionClient)
        result = client._parse_response(  # type: ignore[attr-defined]
            SimpleNamespace(results=SimpleNamespace(channels=[])),
            diarize=False,
            summarize=False,
            processing_time=0.1,
        )
        assert result.transcript == ""

    def test_no_alternatives_returns_empty_result(self) -> None:
        """Response with empty alternatives returns empty TranscriptionResult."""
        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        client = self._client()
        assert isinstance(client, DeepgramTranscriptionClient)
        result = client._parse_response(  # type: ignore[attr-defined]
            SimpleNamespace(
                results=SimpleNamespace(channels=[SimpleNamespace(alternatives=[])])
            ),
            diarize=False,
            summarize=False,
            processing_time=0.1,
        )
        assert result.transcript == ""


class TestDeepgramParseUtterances:
    """Tests for _parse_utterances_and_speakers."""

    def _client(self) -> object:
        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        with (
            patch(
                "audio_processor.services.deepgram_client._deepgram_available",
                new=True,
            ),
            patch(
                "audio_processor.services.deepgram_client._DeepgramClient",
                return_value=MagicMock(),
            ),
        ):
            return DeepgramTranscriptionClient(
                api_key="test-key",  # pragma: allowlist secret
            )

    def test_none_utterances_returns_empty(self) -> None:
        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        client = self._client()
        assert isinstance(client, DeepgramTranscriptionClient)
        utterances, speakers = client._parse_utterances_and_speakers(None)  # type: ignore[attr-defined]
        assert utterances == []
        assert speakers == []

    def test_parses_multiple_speakers(self) -> None:
        from audio_processor.services.deepgram_client import DeepgramTranscriptionClient

        client = self._client()
        assert isinstance(client, DeepgramTranscriptionClient)

        utt0 = SimpleNamespace(
            speaker=0, start=0.0, end=2.0, transcript="Hello", confidence=0.9, words=[]
        )
        utt1 = SimpleNamespace(
            speaker=1, start=2.0, end=4.0, transcript="Hi", confidence=0.85, words=[]
        )
        utt2 = SimpleNamespace(
            speaker=0, start=4.0, end=6.0, transcript="Bye", confidence=0.92, words=[]
        )
        utterances, speakers = client._parse_utterances_and_speakers(  # type: ignore[attr-defined]
            [utt0, utt1, utt2]
        )
        assert len(utterances) == 3
        assert len(speakers) == 2
        speaker_ids = {s.id for s in speakers}
        assert speaker_ids == {0, 1}


# ---------------------------------------------------------------------------
# QualityAssessor
# ---------------------------------------------------------------------------


class TestQualityAssessorDirectMethods:
    """Tests for QualityAssessor internal calculation methods."""

    def setup_method(self) -> None:
        from audio_processor.services.quality_assessor import QualityAssessor

        self.assessor = QualityAssessor()

    def test_calculate_snr_clean_signal(self) -> None:
        """SNR is high for clean sinusoidal signal."""
        t = np.linspace(0, 1.0, 16000, dtype=np.float64)
        clean = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float64)
        snr = self.assessor._calculate_snr(clean)  # type: ignore[attr-defined]
        assert snr > 0

    def test_calculate_snr_short_signal(self) -> None:
        """SNR is finite for a short noisy signal."""
        rng = np.random.default_rng(1)
        short = rng.standard_normal(4096).astype(np.float64) * 0.1
        snr = self.assessor._calculate_snr(short)  # type: ignore[attr-defined]
        assert isinstance(snr, float)

    def test_calculate_silence_ratio_all_silence(self) -> None:
        """All-zero audio has silence ratio of 1.0."""
        silence = np.zeros(16000, dtype=np.float64)
        ratio = self.assessor._calculate_silence_ratio(silence, 16000)  # type: ignore[attr-defined]
        assert ratio == 1.0

    def test_calculate_silence_ratio_zero_amplitude(self) -> None:
        """All-zero signal with length < frame_length has zero peak RMS and returns 1.0."""
        tiny = np.zeros(100, dtype=np.float64)
        ratio = self.assessor._calculate_silence_ratio(tiny, 16000)  # type: ignore[attr-defined]
        assert ratio == 1.0

    def test_calculate_clipping_ratio_no_clipping(self) -> None:
        """Low-amplitude audio has zero clipping."""
        audio = np.ones(1000, dtype=np.float64) * 0.5
        ratio = self.assessor._calculate_clipping_ratio(audio)  # type: ignore[attr-defined]
        assert ratio == 0.0

    def test_calculate_clipping_ratio_all_clipped(self) -> None:
        """Audio peaking at 1.0 reports full clipping."""
        audio = np.ones(1000, dtype=np.float64)
        ratio = self.assessor._calculate_clipping_ratio(audio)  # type: ignore[attr-defined]
        assert ratio == 1.0

    def test_calculate_clipping_ratio_empty(self) -> None:
        """Empty array returns 0.0."""
        ratio = self.assessor._calculate_clipping_ratio(  # type: ignore[attr-defined]
            np.array([], dtype=np.float64)
        )
        assert ratio == 0.0

    def test_calculate_rms_db_silence(self) -> None:
        """Silence returns -96 dB floor."""
        silence = np.zeros(1000, dtype=np.float64)
        db = self.assessor._calculate_rms_db(silence)  # type: ignore[attr-defined]
        assert db == -96.0

    def test_calculate_rms_db_full_scale(self) -> None:
        """Full-scale signal returns 0 dBFS."""
        audio = np.ones(1000, dtype=np.float64)
        db = self.assessor._calculate_rms_db(audio)  # type: ignore[attr-defined]
        assert abs(db - 0.0) < 0.1

    def test_calculate_quality_score_perfect(self) -> None:
        """High SNR, no silence, no clipping yields high quality score."""
        score = self.assessor._calculate_quality_score(30.0, 0.0, 0.0)  # type: ignore[attr-defined]
        assert score > 0.9

    def test_calculate_quality_score_poor(self) -> None:
        """Low SNR, high silence, clipping yields low quality score."""
        score = self.assessor._calculate_quality_score(0.0, 0.9, 0.1)  # type: ignore[attr-defined]
        assert score < 0.5

    def test_determine_quality_level_excellent(self) -> None:
        """High SNR + high score = EXCELLENT."""
        from audio_processor.core.models import QualityLevel

        level = self.assessor._determine_quality_level(30.0, 0.9)  # type: ignore[attr-defined]
        assert level == QualityLevel.EXCELLENT

    def test_determine_quality_level_good(self) -> None:
        from audio_processor.core.models import QualityLevel

        level = self.assessor._determine_quality_level(20.0, 0.7)  # type: ignore[attr-defined]
        assert level == QualityLevel.GOOD

    def test_determine_quality_level_fair(self) -> None:
        from audio_processor.core.models import QualityLevel

        level = self.assessor._determine_quality_level(12.0, 0.5)  # type: ignore[attr-defined]
        assert level == QualityLevel.FAIR

    def test_determine_quality_level_poor(self) -> None:
        from audio_processor.core.models import QualityLevel

        level = self.assessor._determine_quality_level(5.0, 0.2)  # type: ignore[attr-defined]
        assert level == QualityLevel.POOR

    def test_generate_warnings_all_triggered(self) -> None:
        """All warning conditions generate messages."""
        warnings = self.assessor._generate_warnings(  # type: ignore[attr-defined]
            snr_db=5.0,
            silence_ratio=0.8,
            clipping_ratio=0.05,
            peak_amplitude=0.05,
        )
        assert len(warnings) == 4

    def test_generate_warnings_none_triggered(self) -> None:
        """Good audio generates no warnings."""
        warnings = self.assessor._generate_warnings(  # type: ignore[attr-defined]
            snr_db=30.0,
            silence_ratio=0.1,
            clipping_ratio=0.0,
            peak_amplitude=0.8,
        )
        assert warnings == []


class TestQualityAssessorAssess:
    """Tests for QualityAssessor.assess with mocked I/O."""

    def test_assess_file_not_found(self) -> None:
        from audio_processor.services.quality_assessor import QualityAssessor

        assessor = QualityAssessor()
        with pytest.raises(ValidationError, match="File not found"):
            assessor.assess("/nonexistent/path/audio.wav")

    def test_assess_success_mono(self, tmp_path: Path) -> None:
        """Assess returns AudioQualityMetrics for a valid mono file."""
        from audio_processor.services.quality_assessor import QualityAssessor

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 32)

        audio_data, sr = _make_audio(16000, 16000)
        with patch("audio_processor.services.quality_assessor.sf.read") as mock_read:
            mock_read.return_value = (audio_data, sr)
            assessor = QualityAssessor()
            metrics = assessor.assess(audio_file)

        assert metrics.sample_rate == 16000
        assert metrics.channels == 1
        assert 0.0 <= metrics.quality_score <= 1.0
        assert metrics.quality_level is not None

    def test_assess_stereo_converted_to_mono(self, tmp_path: Path) -> None:
        """Stereo audio is internally converted to mono for analysis."""
        from audio_processor.services.quality_assessor import QualityAssessor

        audio_file = tmp_path / "stereo.wav"
        audio_file.write_bytes(b"\x00" * 32)

        stereo = _make_stereo_audio(16000)
        with patch("audio_processor.services.quality_assessor.sf.read") as mock_read:
            mock_read.return_value = (stereo, 16000)
            assessor = QualityAssessor()
            metrics = assessor.assess(audio_file)

        assert metrics.channels == 2

    def test_assess_io_error_raises_audio_processor_error(self, tmp_path: Path) -> None:
        """OSError from sf.read maps to AudioProcessorError."""
        from audio_processor.services.quality_assessor import QualityAssessor

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 32)

        with patch(
            "audio_processor.services.quality_assessor.sf.read",
            side_effect=OSError("bad file"),
        ):
            assessor = QualityAssessor()
            with pytest.raises(AudioProcessorError, match="Failed to assess"):
                assessor.assess(audio_file)

    def test_load_audio_fallback_to_librosa(self, tmp_path: Path) -> None:
        """Falls back to librosa when soundfile raises RuntimeError."""
        from audio_processor.services.quality_assessor import QualityAssessor

        audio_file = tmp_path / "audio.mp3"
        audio_file.write_bytes(b"\x00" * 32)

        audio_data, sr = _make_audio(16000, 16000)
        with (
            patch(
                "audio_processor.services.quality_assessor.sf.read",
                side_effect=RuntimeError("unsupported format"),
            ),
            patch(
                "audio_processor.services.quality_assessor.librosa.load",
                return_value=(audio_data, sr),
            ),
        ):
            assessor = QualityAssessor()
            _audio, sample_rate = assessor._load_audio(audio_file)  # type: ignore[attr-defined]
        assert sample_rate == sr


# ---------------------------------------------------------------------------
# AudioConditioner
# ---------------------------------------------------------------------------


class TestAudioConditionerHelpers:
    """Tests for AudioConditioner internal helpers."""

    def setup_method(self) -> None:
        from audio_processor.services.audio_conditioner import AudioConditioner

        self.conditioner = AudioConditioner()

    def test_calculate_rms_db_silence(self) -> None:
        silence = np.zeros(1000, dtype=np.float64)
        assert self.conditioner._calculate_rms_db(silence) == -96.0  # type: ignore[attr-defined]

    def test_calculate_rms_db_nonzero(self) -> None:
        audio = np.ones(1000, dtype=np.float64) * 0.1
        db = self.conditioner._calculate_rms_db(audio)  # type: ignore[attr-defined]
        assert db < 0

    def test_normalize_rms_silent_audio(self) -> None:
        """Silent audio is returned unchanged with 0 gain."""
        silence = np.zeros(1000, dtype=np.float64)
        _normalized, gain = self.conditioner._normalize_rms(silence, -20.0)  # type: ignore[attr-defined]
        assert gain == 0.0

    def test_normalize_rms_applies_gain(self) -> None:
        """Normalization brings audio to the target RMS level."""
        audio = np.ones(1000, dtype=np.float64) * 0.01
        _normalized, gain = self.conditioner._normalize_rms(audio, -20.0)  # type: ignore[attr-defined]
        assert gain != 0.0

    def test_normalize_rms_soft_clips_loud_audio(self) -> None:
        """Very loud audio gets soft-clipped when peak exceeds 0.99."""
        loud = np.ones(1000, dtype=np.float64) * 2.0
        normalized, _gain = self.conditioner._normalize_rms(loud, -3.0)  # type: ignore[attr-defined]
        assert float(np.max(np.abs(normalized))) < 2.0


class TestAudioConditionerCondition:
    """Tests for AudioConditioner.condition with mocked I/O."""

    def test_condition_file_not_found(self) -> None:
        from audio_processor.services.audio_conditioner import AudioConditioner

        conditioner = AudioConditioner()
        with pytest.raises(ValidationError, match="Audio file not found"):
            conditioner.condition("/nonexistent/audio.wav")

    def test_condition_io_error_raises_audio_processor_error(
        self, tmp_path: Path
    ) -> None:
        from audio_processor.services.audio_conditioner import AudioConditioner

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 32)

        with patch(
            "audio_processor.services.audio_conditioner.sf.read",
            side_effect=OSError("read error"),
        ):
            conditioner = AudioConditioner()
            with pytest.raises(AudioProcessorError, match="Failed to condition"):
                conditioner.condition(audio_file)

    def test_condition_mono_resample_normalize(self, tmp_path: Path) -> None:
        """Full conditioning pipeline runs without error on valid input."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 32)
        output_file = tmp_path / "output.wav"

        audio_data = np.ones(44100, dtype=np.float64) * 0.3
        with (
            patch(
                "audio_processor.services.audio_conditioner.sf.read",
                return_value=(audio_data, 44100),
            ),
            patch("audio_processor.services.audio_conditioner.sf.write") as mock_write,
            patch(
                "audio_processor.services.audio_conditioner.librosa.resample",
                return_value=np.ones(16000, dtype=np.float64) * 0.3,
            ),
        ):
            conditioner = AudioConditioner()
            result = conditioner.condition(audio_file, output_path=output_file)

        assert result.original_sample_rate == 44100
        assert result.target_sample_rate == 16000
        assert mock_write.called

    def test_condition_dc_offset_removed(self, tmp_path: Path) -> None:
        """DC offset removal is triggered when mean exceeds threshold."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 32)
        output_file = tmp_path / "output.wav"

        # Audio with significant DC offset
        audio_data = np.ones(16000, dtype=np.float64) * 0.5

        with (
            patch(
                "audio_processor.services.audio_conditioner.sf.read",
                return_value=(audio_data, 16000),
            ),
            patch("audio_processor.services.audio_conditioner.sf.write"),
        ):
            conditioner = AudioConditioner()
            result = conditioner.condition(
                audio_file,
                output_path=output_file,
                resample=False,
            )

        assert result.dc_offset_removed is True

    def test_condition_stereo_to_mono(self, tmp_path: Path) -> None:
        """Stereo audio is reported as 2 channels in original."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 32)
        output_file = tmp_path / "output.wav"

        stereo = _make_stereo_audio(16000)

        with (
            patch(
                "audio_processor.services.audio_conditioner.sf.read",
                return_value=(stereo, 16000),
            ),
            patch("audio_processor.services.audio_conditioner.sf.write"),
        ):
            conditioner = AudioConditioner()
            result = conditioner.condition(
                audio_file,
                output_path=output_file,
                resample=False,
                normalize=False,
            )

        assert result.original_channels == 2

    def test_condition_creates_temp_file_when_no_output(self, tmp_path: Path) -> None:
        """When output_path is None, a temp file path is assigned."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 32)

        audio_data = np.ones(16000, dtype=np.float64) * 0.1

        with (
            patch(
                "audio_processor.services.audio_conditioner.sf.read",
                return_value=(audio_data, 16000),
            ),
            patch("audio_processor.services.audio_conditioner.sf.write"),
        ):
            conditioner = AudioConditioner(temp_dir=str(tmp_path))
            result = conditioner.condition(
                audio_file,
                resample=False,
                normalize=False,
                remove_dc=False,
            )

        assert result.output_path is not None

    def test_load_audio_fallback_to_librosa(self, tmp_path: Path) -> None:
        """Falls back to librosa when soundfile raises RuntimeError."""
        from audio_processor.services.audio_conditioner import AudioConditioner

        audio_file = tmp_path / "audio.mp3"
        audio_file.write_bytes(b"\x00" * 32)

        audio_data, sr = _make_audio(16000, 16000)
        with (
            patch(
                "audio_processor.services.audio_conditioner.sf.read",
                side_effect=RuntimeError("format error"),
            ),
            patch(
                "audio_processor.services.audio_conditioner.librosa.load",
                return_value=(audio_data, sr),
            ),
        ):
            conditioner = AudioConditioner()
            _audio, sample_rate = conditioner._load_audio(audio_file)  # type: ignore[attr-defined]
        assert sample_rate == sr


class TestAudioConditionerEstimateImprovement:
    """Tests for AudioConditioner.estimate_improvement."""

    def test_estimate_improvement_file_not_found(self) -> None:
        from audio_processor.services.audio_conditioner import AudioConditioner

        conditioner = AudioConditioner()
        with pytest.raises(ValidationError):
            conditioner.estimate_improvement("/no/file.wav")

    def test_estimate_improvement_returns_dict(self, tmp_path: Path) -> None:
        from audio_processor.services.audio_conditioner import AudioConditioner

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 32)

        audio_data = np.ones(16000, dtype=np.float64) * 0.1
        with patch(
            "audio_processor.services.audio_conditioner.sf.read",
            return_value=(audio_data, 8000),
        ):
            conditioner = AudioConditioner()
            result = conditioner.estimate_improvement(audio_file)

        assert "needs_resample" in result
        assert result["current_sample_rate"] == 8000
        assert result["needs_resample"] is True

    def test_estimate_improvement_io_error_raises(self, tmp_path: Path) -> None:
        from audio_processor.services.audio_conditioner import AudioConditioner

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 32)

        with patch(
            "audio_processor.services.audio_conditioner.sf.read",
            side_effect=OSError("read fail"),
        ):
            conditioner = AudioConditioner()
            with pytest.raises(AudioProcessorError, match="Failed to analyze"):
                conditioner.estimate_improvement(audio_file)


# ---------------------------------------------------------------------------
# VADProcessor
# ---------------------------------------------------------------------------


class TestVADProcessorMapTimestamp:
    """Tests for VADProcessor.map_timestamp (no I/O required)."""

    def setup_method(self) -> None:
        from audio_processor.services.vad_processor import VADProcessor

        self.vad = VADProcessor()

    def test_empty_timeline_returns_input(self) -> None:
        assert self.vad.map_timestamp(5.0, ()) == 5.0  # type: ignore[attr-defined]

    def test_maps_single_segment(self) -> None:
        timeline = ((0.0, 1.5),)
        mapped = self.vad.map_timestamp(2.0, timeline)  # type: ignore[attr-defined]
        assert abs(mapped - 3.5) < 1e-9

    def test_maps_to_correct_segment(self) -> None:
        # output_start=0.0 -> original_start=1.0
        # output_start=3.0 -> original_start=5.0
        timeline = ((0.0, 1.0), (3.0, 5.0))
        mapped = self.vad.map_timestamp(3.5, timeline)  # type: ignore[attr-defined]
        assert abs(mapped - 5.5) < 1e-9

    def test_maps_first_segment_before_next(self) -> None:
        timeline = ((0.0, 0.5), (2.0, 3.0))
        mapped = self.vad.map_timestamp(1.0, timeline)  # type: ignore[attr-defined]
        assert abs(mapped - 1.5) < 1e-9


class TestVADProcessorDetectSpeech:
    """Tests for VADProcessor.detect_speech with mocked dependencies."""

    def test_detect_speech_file_not_found(self) -> None:
        from audio_processor.services.vad_processor import VADProcessor

        vad = VADProcessor()
        with pytest.raises(ValidationError, match="Audio file not found"):
            vad.detect_speech("/no/such/file.wav")

    def test_detect_speech_success(self, tmp_path: Path) -> None:
        """Detects speech segments from a mocked audio file."""
        from audio_processor.services.vad_processor import (
            SILERO_SAMPLE_RATE,
            VADProcessor,
        )

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 32)

        audio_data = np.ones(SILERO_SAMPLE_RATE, dtype=np.float32)

        mock_model = MagicMock()
        # get_speech_timestamps returns sample-index dicts
        mock_get_timestamps = MagicMock(
            return_value=[{"start": 0, "end": SILERO_SAMPLE_RATE}]
        )
        mock_utils = (mock_get_timestamps,)

        with (
            patch(
                "audio_processor.services.vad_processor.sf.read",
                return_value=(audio_data, SILERO_SAMPLE_RATE),
            ),
            patch.object(
                VADProcessor,
                "_load_model",
                return_value=(mock_model, mock_utils),
            ),
            patch(
                "audio_processor.services.vad_processor.torch.from_numpy",
                return_value=MagicMock(),
            ),
        ):
            vad = VADProcessor()
            result = vad.detect_speech(audio_file)

        assert len(result.segments) == 1
        assert abs(result.segments[0].start - 0.0) < 1e-6
        assert abs(result.segments[0].end - 1.0) < 1e-6
        assert result.speech_ratio > 0

    def test_detect_speech_resamples_non_16k(self, tmp_path: Path) -> None:
        """Audio at 44100 Hz is resampled to 16kHz before VAD."""
        from audio_processor.services.vad_processor import (
            SILERO_SAMPLE_RATE,
            VADProcessor,
        )

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 32)

        audio_data = np.ones(44100, dtype=np.float32)
        resampled = np.ones(SILERO_SAMPLE_RATE, dtype=np.float32)
        mock_model = MagicMock()
        mock_get_timestamps = MagicMock(return_value=[])
        mock_utils = (mock_get_timestamps,)

        with (
            patch(
                "audio_processor.services.vad_processor.sf.read",
                return_value=(audio_data, 44100),
            ),
            patch(
                "audio_processor.services.vad_processor.librosa.resample",
                return_value=resampled,
            ),
            patch.object(
                VADProcessor, "_load_model", return_value=(mock_model, mock_utils)
            ),
            patch(
                "audio_processor.services.vad_processor.torch.from_numpy",
                return_value=MagicMock(),
            ),
        ):
            vad = VADProcessor()
            result = vad.detect_speech(audio_file)

        assert result.segments == ()

    def test_detect_speech_error_wrapped(self, tmp_path: Path) -> None:
        """Exception during VAD is wrapped in AudioProcessorError."""
        from audio_processor.services.vad_processor import VADProcessor

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 32)

        with patch(
            "audio_processor.services.vad_processor.sf.read",
            side_effect=RuntimeError("read fail"),
        ):
            vad = VADProcessor()
            with pytest.raises(AudioProcessorError, match="VAD processing failed"):
                vad.detect_speech(audio_file)


class TestVADProcessorShouldProcess:
    """Tests for VADProcessor.should_process."""

    def test_returns_false_on_error(self) -> None:
        from audio_processor.services.vad_processor import VADProcessor

        vad = VADProcessor()
        assert vad.should_process("/no/file.wav") is False  # type: ignore[attr-defined]

    def test_returns_true_when_high_silence(self, tmp_path: Path) -> None:
        from audio_processor.services.vad_processor import VADProcessor, VADResult

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 32)

        high_silence_result = VADResult(
            segments=(),
            total_speech_duration=1.0,
            total_silence_duration=9.0,
            speech_ratio=0.1,
            original_duration=10.0,
        )

        vad = VADProcessor()
        with patch.object(vad, "detect_speech", return_value=high_silence_result):
            assert vad.should_process(audio_file) is True  # type: ignore[attr-defined]

    def test_returns_false_when_low_silence(self, tmp_path: Path) -> None:
        from audio_processor.services.vad_processor import VADProcessor, VADResult

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 32)

        low_silence_result = VADResult(
            segments=(),
            total_speech_duration=9.0,
            total_silence_duration=1.0,
            speech_ratio=0.9,
            original_duration=10.0,
        )

        vad = VADProcessor()
        with patch.object(vad, "detect_speech", return_value=low_silence_result):
            assert vad.should_process(audio_file) is False  # type: ignore[attr-defined]


class TestVADProcessorLoadModel:
    """Tests for VADProcessor._load_model caching."""

    def test_model_loaded_once_and_cached(self) -> None:
        """Second call returns the same cached model instance."""
        from audio_processor.services.vad_processor import VADProcessor

        # Reset cached model to force a fresh load
        original_model = VADProcessor._model
        original_utils = VADProcessor._utils
        VADProcessor._model = None
        VADProcessor._utils = None

        try:
            mock_model = MagicMock()
            mock_utils = (MagicMock(),)

            with patch(
                "audio_processor.services.vad_processor.torch.hub.load",
                return_value=(mock_model, mock_utils),
            ) as mock_load:
                vad = VADProcessor()
                m1, _u1 = vad._load_model()  # type: ignore[attr-defined]
                m2, _u2 = vad._load_model()  # type: ignore[attr-defined]

            assert m1 is m2
            assert mock_load.call_count == 1
        finally:
            VADProcessor._model = original_model
            VADProcessor._utils = original_utils


# ---------------------------------------------------------------------------
# AudioConverter (additional coverage for subprocess-based paths)
# ---------------------------------------------------------------------------


class TestAudioConverterProbeSuccess:
    """Tests for successful ffprobe calls."""

    def _make_probe_output(
        self,
        codec: str = "pcm_s16le",
        sample_rate: str = "16000",
        channels: int = 1,
        duration: float = 5.0,
        has_video: bool = False,
    ) -> str:
        streams = [
            {
                "codec_type": "audio",
                "codec_name": codec,
                "sample_rate": sample_rate,
                "channels": channels,
                "bit_rate": "256000",
            }
        ]
        if has_video:
            streams.append({"codec_type": "video", "codec_name": "h264"})
        return json.dumps(
            {
                "streams": streams,
                "format": {"format_name": "wav", "duration": str(duration)},
            }
        )

    @patch("subprocess.run")
    def test_probe_returns_audio_info(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 32)

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=self._make_probe_output(),
            stderr="",
        )
        converter = AudioConverter()
        info = converter.probe(audio_file)

        assert info.sample_rate == 16000
        assert info.duration_seconds == 5.0
        assert info.is_video is False

    @patch("subprocess.run")
    def test_probe_detects_video(self, mock_run: MagicMock, tmp_path: Path) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"\x00" * 32)

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=self._make_probe_output(has_video=True),
            stderr="",
        )
        converter = AudioConverter()
        info = converter.probe(video_file)

        assert info.is_video is True

    @patch("subprocess.run")
    def test_probe_ffprobe_timeout(self, mock_run: MagicMock, tmp_path: Path) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 32)

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffprobe", timeout=30)
        converter = AudioConverter()
        with pytest.raises(AudioProcessorError, match="timed out"):
            converter.probe(audio_file)

    @patch("subprocess.run")
    def test_probe_bad_json(self, mock_run: MagicMock, tmp_path: Path) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 32)

        mock_run.return_value = MagicMock(returncode=0, stdout="not json", stderr="")
        converter = AudioConverter()
        with pytest.raises(AudioProcessorError, match="Failed to parse"):
            converter.probe(audio_file)

    @patch("subprocess.run")
    def test_probe_no_audio_stream(self, mock_run: MagicMock, tmp_path: Path) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        audio_file = tmp_path / "video_only.mp4"
        audio_file.write_bytes(b"\x00" * 32)

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"streams": [], "format": {}}),
            stderr="",
        )
        converter = AudioConverter()
        with pytest.raises(ValidationError, match="No audio stream"):
            converter.probe(audio_file)

    @patch("subprocess.run")
    def test_probe_returncode_nonzero(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        audio_file = tmp_path / "audio.wav"
        audio_file.write_bytes(b"\x00" * 32)

        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error msg")
        converter = AudioConverter()
        with pytest.raises(AudioProcessorError, match="FFprobe failed"):
            converter.probe(audio_file)


class TestAudioConverterExtractAndConvert:
    """Tests for AudioConverter.extract_audio and convert_for_asr."""

    def _good_run(self) -> MagicMock:
        return MagicMock(returncode=0, stdout="", stderr="")

    @patch("subprocess.run")
    def test_extract_audio_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        input_file = tmp_path / "video.mp4"
        input_file.write_bytes(b"\x00" * 32)
        output_file = tmp_path / "audio.wav"

        mock_run.return_value = self._good_run()
        converter = AudioConverter()
        result = converter.extract_audio(input_file, output_file)

        assert result == output_file

    @patch("subprocess.run")
    def test_extract_audio_creates_temp_file(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        input_file = tmp_path / "video.mp4"
        input_file.write_bytes(b"\x00" * 32)

        mock_run.return_value = self._good_run()
        converter = AudioConverter(temp_dir=str(tmp_path))
        result = converter.extract_audio(input_file)

        assert result is not None

    @patch("subprocess.run")
    def test_extract_audio_timeout(self, mock_run: MagicMock, tmp_path: Path) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        input_file = tmp_path / "video.mp4"
        input_file.write_bytes(b"\x00" * 32)

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=600)
        converter = AudioConverter()
        with pytest.raises(AudioProcessorError, match="timed out"):
            converter.extract_audio(input_file, tmp_path / "out.wav")

    @patch("subprocess.run")
    def test_extract_audio_ffmpeg_not_found(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        input_file = tmp_path / "video.mp4"
        input_file.write_bytes(b"\x00" * 32)

        mock_run.side_effect = FileNotFoundError()
        converter = AudioConverter()
        with pytest.raises(AudioProcessorError, match="FFmpeg not found"):
            converter.extract_audio(input_file, tmp_path / "out.wav")

    @patch("subprocess.run")
    def test_extract_audio_returncode_error(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        input_file = tmp_path / "video.mp4"
        input_file.write_bytes(b"\x00" * 32)

        mock_run.return_value = MagicMock(returncode=1, stderr="codec error")
        converter = AudioConverter()
        with pytest.raises(AudioProcessorError, match="extraction failed"):
            converter.extract_audio(input_file, tmp_path / "out.wav")

    @patch("subprocess.run")
    def test_convert_for_asr_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        input_file = tmp_path / "audio.mp3"
        input_file.write_bytes(b"\x00" * 32)
        output_file = tmp_path / "audio.wav"

        mock_run.return_value = self._good_run()
        converter = AudioConverter()
        result = converter.convert_for_asr(input_file, output_file)

        assert result == output_file

    @patch("subprocess.run")
    def test_convert_for_asr_timeout(self, mock_run: MagicMock, tmp_path: Path) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        input_file = tmp_path / "audio.mp3"
        input_file.write_bytes(b"\x00" * 32)

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=600)
        converter = AudioConverter()
        with pytest.raises(AudioProcessorError, match="timed out"):
            converter.convert_for_asr(input_file, tmp_path / "out.wav")

    @patch("subprocess.run")
    def test_convert_for_asr_ffmpeg_not_found(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        input_file = tmp_path / "audio.mp3"
        input_file.write_bytes(b"\x00" * 32)

        mock_run.side_effect = FileNotFoundError()
        converter = AudioConverter()
        with pytest.raises(AudioProcessorError, match="FFmpeg not found"):
            converter.convert_for_asr(input_file, tmp_path / "out.wav")

    @patch("subprocess.run")
    def test_convert_for_asr_returncode_error(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        input_file = tmp_path / "audio.mp3"
        input_file.write_bytes(b"\x00" * 32)

        mock_run.return_value = MagicMock(returncode=1, stderr="no codec")
        converter = AudioConverter()
        with pytest.raises(AudioProcessorError, match="conversion failed"):
            converter.convert_for_asr(input_file, tmp_path / "out.wav")

    @patch("subprocess.run")
    def test_convert_for_asr_creates_temp_file(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        input_file = tmp_path / "audio.mp3"
        input_file.write_bytes(b"\x00" * 32)

        mock_run.return_value = self._good_run()
        converter = AudioConverter(temp_dir=str(tmp_path))
        result = converter.convert_for_asr(input_file)
        assert result is not None


class TestAudioConverterValidateFile:
    """Tests for AudioConverter.validate_file."""

    def _probe_info(
        self,
        duration: float = 5.0,
        sample_rate: int = 16000,
    ) -> MagicMock:
        from audio_processor.services.audio_converter import AudioInfo

        return AudioInfo(
            duration_seconds=duration,
            sample_rate=sample_rate,
            channels=1,
            codec="pcm_s16le",
            bit_rate=None,
            format_name="wav",
            is_video=False,
        )

    def test_validate_file_not_found(self) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        converter = AudioConverter()
        with pytest.raises(ValidationError, match="File not found"):
            converter.validate_file("/no/file.wav")

    def test_validate_file_too_large(self, tmp_path: Path) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        audio_file = tmp_path / "big.wav"
        audio_file.write_bytes(b"\x00" * 32)

        converter = AudioConverter()
        with pytest.raises(ValidationError, match="File size"):
            converter.validate_file(audio_file, max_size_bytes=10)

    def test_validate_file_duration_too_long(self, tmp_path: Path) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        audio_file = tmp_path / "long.wav"
        audio_file.write_bytes(b"\x00" * 32)

        with patch.object(
            AudioConverter,
            "probe",
            return_value=self._probe_info(duration=7200.0),
        ):
            converter = AudioConverter()
            with pytest.raises(ValidationError, match="exceeds maximum"):
                converter.validate_file(audio_file, max_duration_seconds=60.0)

    def test_validate_file_duration_too_short(self, tmp_path: Path) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        audio_file = tmp_path / "short.wav"
        audio_file.write_bytes(b"\x00" * 32)

        with patch.object(
            AudioConverter,
            "probe",
            return_value=self._probe_info(duration=0.5),
        ):
            converter = AudioConverter()
            with pytest.raises(ValidationError, match="too short"):
                converter.validate_file(audio_file)

    def test_validate_file_success(self, tmp_path: Path) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        audio_file = tmp_path / "good.wav"
        audio_file.write_bytes(b"\x00" * 32)

        with patch.object(
            AudioConverter,
            "probe",
            return_value=self._probe_info(duration=5.0),
        ):
            converter = AudioConverter()
            info = converter.validate_file(audio_file)

        assert info.duration_seconds == 5.0


class TestAudioConverterDetectFormat:
    """Tests for AudioConverter.detect_format."""

    def test_detect_from_mime_type(self) -> None:
        from audio_processor.core.models import AudioFormat
        from audio_processor.services.audio_converter import AudioConverter

        converter = AudioConverter()
        fmt = converter.detect_format("file.unknown", content_type="audio/mpeg")
        assert fmt == AudioFormat.MP3

    def test_detect_from_extension(self, tmp_path: Path) -> None:
        from audio_processor.core.models import AudioFormat
        from audio_processor.services.audio_converter import AudioConverter

        converter = AudioConverter()
        fmt = converter.detect_format(tmp_path / "audio.flac")
        assert fmt == AudioFormat.FLAC

    def test_detect_unknown_raises(self, tmp_path: Path) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        audio_file = tmp_path / "audio.xyz"
        audio_file.write_bytes(b"\x00" * 32)

        with patch.object(
            AudioConverter, "probe", side_effect=AudioProcessorError("fail")
        ):
            converter = AudioConverter()
            with pytest.raises(ValidationError, match="Unsupported"):
                converter.detect_format(audio_file)

    def test_is_video_true(self, tmp_path: Path) -> None:
        from audio_processor.services.audio_converter import AudioConverter, AudioInfo

        video_file = tmp_path / "video.mp4"
        video_file.write_bytes(b"\x00" * 32)

        video_info = AudioInfo(
            duration_seconds=10.0,
            sample_rate=44100,
            channels=2,
            codec="aac",
            bit_rate=None,
            format_name="mp4",
            is_video=True,
        )
        with patch.object(AudioConverter, "probe", return_value=video_info):
            converter = AudioConverter()
            assert converter.is_video(video_file) is True

    def test_is_video_false_on_error(self) -> None:
        from audio_processor.services.audio_converter import AudioConverter

        converter = AudioConverter()
        assert converter.is_video("/nonexistent/file.mp4") is False
