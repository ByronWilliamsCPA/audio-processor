"""Transcript output formatters.

This module provides transcript formatting for multiple output formats:
- Plain text with speaker labels
- SRT subtitles
- VTT subtitles (future)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from audio_processor.utils.logging import get_logger

if TYPE_CHECKING:
    from audio_processor.core.models import TranscriptionResult

logger = get_logger(__name__)


@dataclass(frozen=True)
class FormattedTranscript:
    """A formatted transcript in a specific format.

    Attributes:
        content: The formatted transcript content.
        format: The format type (txt, srt, vtt).
        line_count: Number of lines/entries in the transcript.
    """

    content: str
    format: str
    line_count: int


class TranscriptFormatter:
    """Formatter for converting transcriptions to various output formats.

    Supports multiple output formats:
    - Plain text with optional speaker labels and timestamps
    - SRT subtitle format for video players
    - VTT subtitle format (WebVTT)

    Example:
        >>> formatter = TranscriptFormatter()
        >>> text = formatter.to_text(result, include_speakers=True)
        >>> srt = formatter.to_srt(result)
    """

    def to_text(
        self,
        transcription: TranscriptionResult,
        *,
        include_speakers: bool = True,
        include_timestamps: bool = False,
    ) -> FormattedTranscript:
        """Convert transcription to plain text format.

        Args:
            transcription: The transcription result.
            include_speakers: Whether to include speaker labels.
            include_timestamps: Whether to include timestamps.

        Returns:
            FormattedTranscript with plain text content.
        """
        lines: list[str] = []

        # Build speaker label lookup (speaker.id is an int)
        speaker_labels: dict[int, str] = {}
        for speaker in transcription.speakers:
            speaker_labels[speaker.id] = speaker.label or f"Speaker {speaker.id}"

        for utterance in transcription.utterances:
            line_parts: list[str] = []

            # Add timestamp if requested (start is in seconds, convert to ms)
            if include_timestamps:
                start_ms = int(utterance.start * 1000)
                timestamp = self._format_timestamp_hms(start_ms)
                line_parts.append(f"[{timestamp}]")

            # Add speaker label if requested (utterance.speaker is an int)
            if include_speakers:
                label = speaker_labels.get(
                    utterance.speaker, f"Speaker {utterance.speaker}"
                )
                line_parts.append(f"{label}:")

            # Add text
            line_parts.append(utterance.text)

            lines.append(" ".join(line_parts))

        content = "\n".join(lines)

        logger.info(
            "transcript_formatted_text",
            line_count=len(lines),
            include_speakers=include_speakers,
            include_timestamps=include_timestamps,
        )

        return FormattedTranscript(
            content=content,
            format="txt",
            line_count=len(lines),
        )

    def to_srt(
        self,
        transcription: TranscriptionResult,
        *,
        include_speakers: bool = True,
        max_chars_per_line: int = 42,
    ) -> FormattedTranscript:
        """Convert transcription to SRT subtitle format.

        SRT format:
        ```
        1
        00:00:01,500 --> 00:00:04,000
        Speaker 1: Hello, how are you?

        2
        00:00:04,500 --> 00:00:07,000
        Speaker 2: I'm doing great, thanks!
        ```

        Args:
            transcription: The transcription result.
            include_speakers: Whether to include speaker labels.
            max_chars_per_line: Maximum characters per subtitle line.

        Returns:
            FormattedTranscript with SRT content.
        """
        entries: list[str] = []

        # Build speaker label lookup (speaker.id is an int)
        speaker_labels: dict[int, str] = {}
        for speaker in transcription.speakers:
            speaker_labels[speaker.id] = speaker.label or f"Speaker {speaker.id}"

        for idx, utterance in enumerate(transcription.utterances, start=1):
            # Format timestamps (start/end are in seconds, convert to ms)
            start_ms = int(utterance.start * 1000)
            end_ms = int(utterance.end * 1000)
            start_time = self._format_srt_timestamp(start_ms)
            end_time = self._format_srt_timestamp(end_ms)

            # Build subtitle text
            text = utterance.text
            if include_speakers:
                label = speaker_labels.get(
                    utterance.speaker, f"Speaker {utterance.speaker}"
                )
                text = f"{label}: {text}"

            # Wrap long lines
            wrapped_text = self._wrap_subtitle_text(text, max_chars_per_line)

            # Build SRT entry
            entry = f"{idx}\n{start_time} --> {end_time}\n{wrapped_text}\n"
            entries.append(entry)

        content = "\n".join(entries)

        logger.info(
            "transcript_formatted_srt",
            subtitle_count=len(entries),
            include_speakers=include_speakers,
        )

        return FormattedTranscript(
            content=content,
            format="srt",
            line_count=len(entries),
        )

    def to_vtt(
        self,
        transcription: TranscriptionResult,
        *,
        include_speakers: bool = True,
        max_chars_per_line: int = 42,
    ) -> FormattedTranscript:
        """Convert transcription to WebVTT subtitle format.

        VTT format:
        ```
        WEBVTT

        00:00:01.500 --> 00:00:04.000
        Speaker 1: Hello, how are you?

        00:00:04.500 --> 00:00:07.000
        Speaker 2: I'm doing great, thanks!
        ```

        Args:
            transcription: The transcription result.
            include_speakers: Whether to include speaker labels.
            max_chars_per_line: Maximum characters per subtitle line.

        Returns:
            FormattedTranscript with VTT content.
        """
        lines: list[str] = ["WEBVTT", ""]

        # Build speaker label lookup (speaker.id is an int)
        speaker_labels: dict[int, str] = {}
        for speaker in transcription.speakers:
            speaker_labels[speaker.id] = speaker.label or f"Speaker {speaker.id}"

        for utterance in transcription.utterances:
            # Format timestamps (VTT uses period instead of comma)
            # start/end are in seconds, convert to ms
            start_ms = int(utterance.start * 1000)
            end_ms = int(utterance.end * 1000)
            start_time = self._format_vtt_timestamp(start_ms)
            end_time = self._format_vtt_timestamp(end_ms)

            # Build subtitle text
            text = utterance.text
            if include_speakers:
                label = speaker_labels.get(
                    utterance.speaker, f"Speaker {utterance.speaker}"
                )
                text = f"{label}: {text}"

            # Wrap long lines
            wrapped_text = self._wrap_subtitle_text(text, max_chars_per_line)

            # Add cue
            lines.append(f"{start_time} --> {end_time}")
            lines.append(wrapped_text)
            lines.append("")

        content = "\n".join(lines)

        cue_count = len(transcription.utterances)

        logger.info(
            "transcript_formatted_vtt",
            cue_count=cue_count,
            include_speakers=include_speakers,
        )

        return FormattedTranscript(
            content=content,
            format="vtt",
            line_count=cue_count,
        )

    def _format_timestamp_hms(self, ms: int) -> str:
        """Format milliseconds to HH:MM:SS format.

        Args:
            ms: Time in milliseconds.

        Returns:
            Formatted timestamp string.
        """
        total_seconds = ms // 1000
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _format_srt_timestamp(self, ms: int) -> str:
        """Format milliseconds to SRT timestamp format (HH:MM:SS,mmm).

        Args:
            ms: Time in milliseconds.

        Returns:
            SRT-formatted timestamp string.
        """
        hours = ms // 3600000
        minutes = (ms % 3600000) // 60000
        seconds = (ms % 60000) // 1000
        milliseconds = ms % 1000

        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    def _format_vtt_timestamp(self, ms: int) -> str:
        """Format milliseconds to WebVTT timestamp format (HH:MM:SS.mmm).

        Args:
            ms: Time in milliseconds.

        Returns:
            VTT-formatted timestamp string.
        """
        hours = ms // 3600000
        minutes = (ms % 3600000) // 60000
        seconds = (ms % 60000) // 1000
        milliseconds = ms % 1000

        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

    def _wrap_subtitle_text(self, text: str, max_chars: int) -> str:
        """Wrap text to fit within subtitle line limits.

        Args:
            text: The text to wrap.
            max_chars: Maximum characters per line.

        Returns:
            Wrapped text with newlines.
        """
        if len(text) <= max_chars:
            return text

        words = text.split()
        lines: list[str] = []
        current_line: list[str] = []
        current_length = 0

        for word in words:
            word_length = len(word)

            if current_length + word_length + len(current_line) > max_chars:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_length
            else:
                current_line.append(word)
                current_length += word_length

        if current_line:
            lines.append(" ".join(current_line))

        return "\n".join(lines)


class ArtifactGenerator:
    """Generator for all transcript artifacts.

    Coordinates the generation of multiple output formats from
    a single transcription result.

    Example:
        >>> generator = ArtifactGenerator()
        >>> artifacts = generator.generate_all(result)
        >>> for name, content in artifacts.items():
        ...     print(f"{name}: {len(content)} bytes")
    """

    def __init__(self) -> None:
        """Initialize the artifact generator."""
        self.formatter = TranscriptFormatter()

    def generate_all(
        self,
        transcription: TranscriptionResult,
        *,
        include_docling: bool = True,
    ) -> dict[str, str]:
        """Generate all artifact formats.

        Args:
            transcription: The transcription result.
            include_docling: Whether to include Docling DOM (requires DOMBuilder).

        Returns:
            Dictionary mapping artifact names to content.
        """
        # Import here to avoid circular imports
        from audio_processor.services.dom_builder import DOMBuilder  # noqa: PLC0415

        artifacts: dict[str, str] = {}

        # Plain text transcript
        text_result = self.formatter.to_text(
            transcription, include_speakers=True, include_timestamps=True
        )
        artifacts["transcript.txt"] = text_result.content

        # Plain text without timestamps
        text_simple = self.formatter.to_text(
            transcription, include_speakers=True, include_timestamps=False
        )
        artifacts["transcript_simple.txt"] = text_simple.content

        # SRT subtitles
        srt_result = self.formatter.to_srt(transcription, include_speakers=True)
        artifacts["transcript.srt"] = srt_result.content

        # VTT subtitles
        vtt_result = self.formatter.to_vtt(transcription, include_speakers=True)
        artifacts["transcript.vtt"] = vtt_result.content

        # Docling DOM
        if include_docling:
            builder = DOMBuilder()
            dom_result = builder.build(transcription)
            dom_dict = builder.export_to_json(dom_result)
            artifacts["docling_dom.json"] = json.dumps(dom_dict, indent=2)

        logger.info(
            "artifacts_generated",
            artifact_count=len(artifacts),
            artifact_names=list(artifacts.keys()),
        )

        return artifacts

    def generate_artifact(
        self,
        transcription: TranscriptionResult,
        artifact_name: str,
    ) -> str | None:
        """Generate a specific artifact.

        Args:
            transcription: The transcription result.
            artifact_name: Name of the artifact to generate.

        Returns:
            Artifact content string, or None if not found.
        """
        # Import here to avoid circular imports
        from audio_processor.services.dom_builder import DOMBuilder  # noqa: PLC0415

        if artifact_name == "transcript.txt":
            result = self.formatter.to_text(
                transcription, include_speakers=True, include_timestamps=True
            )
            return result.content

        if artifact_name == "transcript_simple.txt":
            result = self.formatter.to_text(
                transcription, include_speakers=True, include_timestamps=False
            )
            return result.content

        if artifact_name == "transcript.srt":
            result = self.formatter.to_srt(transcription, include_speakers=True)
            return result.content

        if artifact_name == "transcript.vtt":
            result = self.formatter.to_vtt(transcription, include_speakers=True)
            return result.content

        if artifact_name == "docling_dom.json":
            builder = DOMBuilder()
            dom_result = builder.build(transcription)
            dom_dict = builder.export_to_json(dom_result)
            return json.dumps(dom_dict, indent=2)

        return None
