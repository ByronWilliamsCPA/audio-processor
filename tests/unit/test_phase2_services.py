"""Unit tests for Phase 2 services.

Tests for:
- DOMBuilder: Docling DOM document generation
- TranscriptFormatter: Output format generators (TXT, SRT, VTT)
- ArtifactGenerator: Multi-format artifact generation
"""

from __future__ import annotations

import pytest

from audio_processor.core.models import (
    Speaker,
    TranscriptionMetadata,
    TranscriptionResult,
    Utterance,
    Word,
)
from audio_processor.services.dom_builder import DOMBuilder, DOMBuildResult
from audio_processor.services.transcript_formatter import (
    ArtifactGenerator,
    TranscriptFormatter,
)


@pytest.fixture
def sample_words() -> list[Word]:
    """Create sample words for testing."""
    return [
        Word(word="Hello", start=0.0, end=0.5, confidence=0.95),
        Word(word="world", start=0.5, end=1.0, confidence=0.92),
    ]


@pytest.fixture
def sample_speakers() -> list[Speaker]:
    """Create sample speakers for testing."""
    return [
        Speaker(
            id=0,
            label="Speaker 1",
            total_duration=5.0,
            utterance_count=2,
        ),
        Speaker(
            id=1,
            label="Speaker 2",
            total_duration=3.0,
            utterance_count=1,
        ),
    ]


@pytest.fixture
def sample_utterances(sample_words: list[Word]) -> list[Utterance]:
    """Create sample utterances for testing."""
    return [
        Utterance(
            id="utt_1",
            speaker=0,
            text="Hello world, how are you today?",
            start=0.0,
            end=2.0,
            confidence=0.93,
            words=tuple(sample_words),
        ),
        Utterance(
            id="utt_2",
            speaker=1,
            text="I'm doing great, thank you!",
            start=2.0,
            end=4.0,
            confidence=0.88,
            words=tuple(sample_words),
        ),
        Utterance(
            id="utt_3",
            speaker=0,
            text="That's wonderful to hear.",
            start=4.0,
            end=5.5,
            confidence=0.91,
            words=(),
        ),
    ]


@pytest.fixture
def sample_transcription(
    sample_speakers: list[Speaker],
    sample_utterances: list[Utterance],
) -> TranscriptionResult:
    """Create a sample transcription result for testing."""
    return TranscriptionResult(
        transcript="Hello world, how are you today? I'm doing great, thank you! That's wonderful to hear.",
        speakers=tuple(sample_speakers),
        utterances=tuple(sample_utterances),
        metadata=TranscriptionMetadata(
            duration_seconds=5.5,
            word_count=15,
            confidence_mean=0.90,
            confidence_min=0.85,
        ),
    )


class TestDOMBuilder:
    """Tests for DOMBuilder service."""

    def test_build_creates_document(
        self, sample_transcription: TranscriptionResult
    ) -> None:
        """Test that build creates a valid Docling document."""
        builder = DOMBuilder()
        result = builder.build(sample_transcription)

        assert isinstance(result, DOMBuildResult)
        assert result.document is not None
        assert result.speaker_count == 2
        assert result.utterance_count == 3
        assert result.total_duration_ms == 5500

    def test_build_with_custom_name(
        self, sample_transcription: TranscriptionResult
    ) -> None:
        """Test building document with custom name."""
        builder = DOMBuilder(document_name="my_transcript")
        result = builder.build(sample_transcription)

        assert result.document.name == "my_transcript"

    def test_export_to_json(self, sample_transcription: TranscriptionResult) -> None:
        """Test exporting DOM result to JSON."""
        builder = DOMBuilder()
        result = builder.build(sample_transcription)
        json_dict = builder.export_to_json(result)

        assert isinstance(json_dict, dict)
        assert "texts" in json_dict
        assert "_audio_processor" in json_dict
        assert json_dict["_audio_processor"]["speaker_count"] == 2
        assert json_dict["_audio_processor"]["utterance_count"] == 3

    def test_speaker_sections_created(
        self, sample_transcription: TranscriptionResult
    ) -> None:
        """Test that speaker sections are created."""
        builder = DOMBuilder()
        result = builder.build(sample_transcription)
        json_dict = builder.export_to_json(result)

        # Check for section headers
        texts = json_dict.get("texts", [])
        section_headers = [t for t in texts if t.get("label") == "section_header"]

        assert len(section_headers) == 2
        assert section_headers[0]["text"] == "Speaker 1"
        assert section_headers[1]["text"] == "Speaker 2"

    def test_utterance_paragraphs_created(
        self, sample_transcription: TranscriptionResult
    ) -> None:
        """Test that utterance paragraphs are created."""
        builder = DOMBuilder()
        result = builder.build(sample_transcription)
        json_dict = builder.export_to_json(result)

        # Check for paragraphs
        texts = json_dict.get("texts", [])
        paragraphs = [t for t in texts if t.get("label") == "paragraph"]

        assert len(paragraphs) == 3

    def test_utterance_metadata(
        self, sample_transcription: TranscriptionResult
    ) -> None:
        """Test that utterances have correct metadata."""
        builder = DOMBuilder()
        result = builder.build(sample_transcription)
        json_dict = builder.export_to_json(result)

        texts = json_dict.get("texts", [])
        paragraphs = [t for t in texts if t.get("label") == "paragraph"]

        first_para = paragraphs[0]
        assert "meta" in first_para
        meta = first_para["meta"]
        assert meta.get("audio__start_ms") == 0
        assert meta.get("audio__end_ms") == 2000
        assert "audio__playback_url" in meta
        assert "audio__confidence" in meta

    def test_playback_url_format(
        self, sample_transcription: TranscriptionResult
    ) -> None:
        """Test that playback URLs use Media Fragment syntax."""
        builder = DOMBuilder()
        result = builder.build(sample_transcription)
        json_dict = builder.export_to_json(result)

        texts = json_dict.get("texts", [])
        paragraphs = [t for t in texts if t.get("label") == "paragraph"]

        first_para = paragraphs[0]
        playback_url = first_para["meta"]["audio__playback_url"]

        # Should be #t=start,end format
        assert playback_url.startswith("#t=")
        assert "0,2" in playback_url

    def test_playback_url_with_base_url(
        self, sample_transcription: TranscriptionResult
    ) -> None:
        """Test playback URLs with custom base URL."""
        builder = DOMBuilder(media_base_url="https://example.com/audio.mp3")
        result = builder.build(sample_transcription)
        json_dict = builder.export_to_json(result)

        texts = json_dict.get("texts", [])
        paragraphs = [t for t in texts if t.get("label") == "paragraph"]

        first_para = paragraphs[0]
        playback_url = first_para["meta"]["audio__playback_url"]

        assert playback_url.startswith("https://example.com/audio.mp3#t=")


class TestTranscriptFormatter:
    """Tests for TranscriptFormatter service."""

    def test_to_text_basic(self, sample_transcription: TranscriptionResult) -> None:
        """Test basic text transcript generation."""
        formatter = TranscriptFormatter()
        result = formatter.to_text(sample_transcription, include_speakers=True)

        assert result.format == "txt"
        assert result.line_count == 3
        assert "Speaker 1:" in result.content
        assert "Speaker 2:" in result.content
        assert "Hello world" in result.content

    def test_to_text_with_timestamps(
        self, sample_transcription: TranscriptionResult
    ) -> None:
        """Test text transcript with timestamps."""
        formatter = TranscriptFormatter()
        result = formatter.to_text(
            sample_transcription, include_speakers=True, include_timestamps=True
        )

        assert "[00:00]" in result.content
        assert "[00:02]" in result.content
        assert "[00:04]" in result.content

    def test_to_text_without_speakers(
        self, sample_transcription: TranscriptionResult
    ) -> None:
        """Test text transcript without speaker labels."""
        formatter = TranscriptFormatter()
        result = formatter.to_text(sample_transcription, include_speakers=False)

        assert "Speaker 1:" not in result.content
        assert "Speaker 2:" not in result.content
        assert "Hello world" in result.content

    def test_to_srt_format(self, sample_transcription: TranscriptionResult) -> None:
        """Test SRT subtitle generation."""
        formatter = TranscriptFormatter()
        result = formatter.to_srt(sample_transcription)

        assert result.format == "srt"
        assert result.line_count == 3

        # Check SRT format
        lines = result.content.split("\n")
        assert lines[0] == "1"  # First subtitle index
        assert "-->" in lines[1]  # Timestamp line
        assert "00:00:00,000 --> 00:00:02,000" in lines[1]

    def test_to_srt_timestamps(self, sample_transcription: TranscriptionResult) -> None:
        """Test SRT timestamp format (HH:MM:SS,mmm)."""
        formatter = TranscriptFormatter()
        result = formatter.to_srt(sample_transcription)

        # Check timestamp format
        assert "00:00:00,000" in result.content
        assert "00:00:02,000" in result.content
        assert "00:00:04,000" in result.content

    def test_to_vtt_format(self, sample_transcription: TranscriptionResult) -> None:
        """Test WebVTT subtitle generation."""
        formatter = TranscriptFormatter()
        result = formatter.to_vtt(sample_transcription)

        assert result.format == "vtt"
        assert result.line_count == 3

        # Check VTT header
        assert result.content.startswith("WEBVTT")

        # Check timestamp format (periods instead of commas)
        assert "00:00:00.000" in result.content

    def test_to_vtt_with_speakers(
        self, sample_transcription: TranscriptionResult
    ) -> None:
        """Test VTT with speaker labels."""
        formatter = TranscriptFormatter()
        result = formatter.to_vtt(sample_transcription, include_speakers=True)

        assert "Speaker 1:" in result.content
        assert "Speaker 2:" in result.content


class TestArtifactGenerator:
    """Tests for ArtifactGenerator service."""

    def test_generate_all(self, sample_transcription: TranscriptionResult) -> None:
        """Test generating all artifact formats."""
        generator = ArtifactGenerator()
        artifacts = generator.generate_all(sample_transcription)

        assert "transcript.txt" in artifacts
        assert "transcript_simple.txt" in artifacts
        assert "transcript.srt" in artifacts
        assert "transcript.vtt" in artifacts
        assert "docling_dom.json" in artifacts

    def test_generate_all_content(
        self, sample_transcription: TranscriptionResult
    ) -> None:
        """Test that all artifacts have valid content."""
        generator = ArtifactGenerator()
        artifacts = generator.generate_all(sample_transcription)

        # All artifacts should be non-empty strings
        for content in artifacts.values():
            assert isinstance(content, str)
            assert len(content) > 0

    def test_generate_artifact_txt(
        self, sample_transcription: TranscriptionResult
    ) -> None:
        """Test generating specific text artifact."""
        generator = ArtifactGenerator()
        content = generator.generate_artifact(sample_transcription, "transcript.txt")

        assert content is not None
        assert "Speaker 1:" in content

    def test_generate_artifact_srt(
        self, sample_transcription: TranscriptionResult
    ) -> None:
        """Test generating specific SRT artifact."""
        generator = ArtifactGenerator()
        content = generator.generate_artifact(sample_transcription, "transcript.srt")

        assert content is not None
        assert "-->" in content
        assert "1\n" in content

    def test_generate_artifact_unknown(
        self, sample_transcription: TranscriptionResult
    ) -> None:
        """Test generating unknown artifact returns None."""
        generator = ArtifactGenerator()
        content = generator.generate_artifact(sample_transcription, "unknown.xyz")

        assert content is None


class TestMediaFragmentURLs:
    """Tests for Media Fragment URI generation."""

    def test_simple_timestamp(self) -> None:
        """Test simple timestamp formatting."""
        builder = DOMBuilder()
        url = builder._generate_playback_url(0, 2000)

        assert url == "#t=0,2"

    def test_millisecond_precision(self) -> None:
        """Test timestamps with milliseconds."""
        builder = DOMBuilder()
        url = builder._generate_playback_url(1500, 3200)

        assert url == "#t=1.5,3.2"

    def test_long_duration(self) -> None:
        """Test timestamps for long durations."""
        builder = DOMBuilder()
        # 1 hour, 30 minutes
        url = builder._generate_playback_url(5400000, 5460000)

        assert url == "#t=5400,5460"

    def test_with_base_url(self) -> None:
        """Test timestamps with base URL."""
        builder = DOMBuilder(media_base_url="https://cdn.example.com/file.mp3")
        url = builder._generate_playback_url(1000, 2000)

        assert url == "https://cdn.example.com/file.mp3#t=1,2"


class TestSRTTimestampFormatting:
    """Tests for SRT timestamp formatting."""

    def test_zero_timestamp(self) -> None:
        """Test formatting zero timestamp."""
        formatter = TranscriptFormatter()
        timestamp = formatter._format_srt_timestamp(0)

        assert timestamp == "00:00:00,000"

    def test_seconds_timestamp(self) -> None:
        """Test formatting seconds timestamp."""
        formatter = TranscriptFormatter()
        timestamp = formatter._format_srt_timestamp(5000)

        assert timestamp == "00:00:05,000"

    def test_minutes_timestamp(self) -> None:
        """Test formatting minutes timestamp."""
        formatter = TranscriptFormatter()
        timestamp = formatter._format_srt_timestamp(125000)  # 2:05

        assert timestamp == "00:02:05,000"

    def test_hours_timestamp(self) -> None:
        """Test formatting hours timestamp."""
        formatter = TranscriptFormatter()
        timestamp = formatter._format_srt_timestamp(3665500)  # 1:01:05.5

        assert timestamp == "01:01:05,500"

    def test_milliseconds_preserved(self) -> None:
        """Test that milliseconds are preserved."""
        formatter = TranscriptFormatter()
        timestamp = formatter._format_srt_timestamp(1234)

        assert timestamp == "00:00:01,234"


class TestVTTTimestampFormatting:
    """Tests for VTT timestamp formatting."""

    def test_vtt_uses_period(self) -> None:
        """Test that VTT uses period instead of comma."""
        formatter = TranscriptFormatter()
        timestamp = formatter._format_vtt_timestamp(1234)

        assert "." in timestamp
        assert "," not in timestamp
        assert timestamp == "00:00:01.234"
