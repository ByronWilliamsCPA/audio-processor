"""Docling DOM builder for audio transcriptions.

This module provides Docling DOM generation for:
- Mapping speakers to SectionHeaderItems
- Mapping utterances to TextItems with timestamps
- Generating Media Fragment URIs for playback
- Creating pipeline-compatible output format
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from docling_core.types.doc import (
    BaseMeta,  # pyright: ignore[reportPrivateImportUsage]
    DocItemLabel,  # pyright: ignore[reportPrivateImportUsage]
    DoclingDocument,  # pyright: ignore[reportPrivateImportUsage]
)

from audio_processor.core.exceptions import ValidationError
from audio_processor.utils.logging import get_logger

if TYPE_CHECKING:
    from audio_processor.core.models import Speaker, TranscriptionResult, Utterance

logger = get_logger(__name__)

# Metadata namespace for audio-related fields
AUDIO_META_NAMESPACE = "audio"


@dataclass(frozen=True)
class DOMBuildResult:
    """Result of building a Docling DOM document.

    Attributes:
        document (DoclingDocument): The generated Docling document.
        speaker_count (int): Number of speakers in the document.
        utterance_count (int): Number of utterances in the document.
        total_duration_ms (int): Total audio duration in milliseconds.
    """

    document: DoclingDocument
    speaker_count: int
    utterance_count: int
    total_duration_ms: int


class DOMBuilder:
    """Builder for Docling DOM documents from audio transcriptions.

    Converts transcription results into a structured Docling document
    format suitable for RAG pipelines and document processing.

    The document structure is:
    - Document root with audio metadata
    - Speaker sections (SectionHeaderItem) for each speaker
    - Utterance paragraphs (TextItem) under each speaker section
    - Metadata includes timestamps, confidence, and playback URLs

    Args:
        document_name (str): Name for the generated document.
        media_base_url (str | None): Base URL for media fragment links.
            If None, uses relative fragment URIs (#t=start,end).

    Example:
        >>> builder = DOMBuilder()
        >>> result = builder.build(transcription_result)
        >>> doc_dict = result.document.export_to_dict()
        >>> print(doc_dict["name"])
        'audio_transcript'
    """

    def __init__(
        self,
        document_name: str = "audio_transcript",
        media_base_url: str | None = None,
    ) -> None:
        self.document_name = document_name
        self.media_base_url = media_base_url

    def build(
        self,
        transcription: TranscriptionResult,
        *,
        include_word_timestamps: bool = False,
    ) -> DOMBuildResult:
        """Build a Docling document from transcription results.

        Args:
            transcription (TranscriptionResult): The transcription result to convert.
            include_word_timestamps (bool): Whether to include word-level timestamps.

        Returns:
            DOMBuildResult: DOMBuildResult with the generated document and statistics.

        Raises:
            ValidationError: If transcription data is invalid.
        """
        if not transcription.speakers and not transcription.utterances:
            msg = "Transcription has no speakers or utterances"
            raise ValidationError(msg, field="transcription", value="empty")

        logger.info(
            "building_docling_dom",
            speaker_count=len(transcription.speakers),
            utterance_count=len(transcription.utterances),
        )

        # Create document with metadata
        doc = DoclingDocument(name=self.document_name)

        # Add document-level metadata
        self._add_document_metadata(doc, transcription)

        # Group utterances by speaker
        utterances_by_speaker = self._group_utterances_by_speaker(
            transcription.utterances
        )

        # Add speakers and their utterances
        utterance_count = 0
        for speaker in transcription.speakers:
            speaker_utterances = utterances_by_speaker.get(speaker.id, [])
            self._add_speaker_section(
                doc,
                speaker,
                speaker_utterances,
                include_word_timestamps=include_word_timestamps,
            )
            utterance_count += len(speaker_utterances)

        # Handle any utterances without a matching speaker
        orphan_utterances = utterances_by_speaker.get(None, [])
        if orphan_utterances:
            self._add_orphan_utterances(
                doc,
                orphan_utterances,
                include_word_timestamps=include_word_timestamps,
            )
            utterance_count += len(orphan_utterances)

        logger.info(
            "docling_dom_built",
            speaker_count=len(transcription.speakers),
            utterance_count=utterance_count,
            document_name=self.document_name,
        )

        # Get duration in ms from metadata
        duration_ms = int(transcription.metadata.duration_seconds * 1000)

        return DOMBuildResult(
            document=doc,
            speaker_count=len(transcription.speakers),
            utterance_count=utterance_count,
            total_duration_ms=duration_ms,
        )

    def _add_document_metadata(
        self,
        doc: DoclingDocument,
        transcription: TranscriptionResult,
    ) -> None:
        """Add document-level metadata from transcription.

        Args:
            doc (DoclingDocument): The Docling document.
            transcription (TranscriptionResult): The transcription result.
        """
        # Note: DoclingDocument doesn't have a direct meta attribute
        # Metadata will be added to individual items
        _ = doc, transcription  # Acknowledge unused parameters

    def _group_utterances_by_speaker(
        self,
        utterances: tuple[Utterance, ...],
    ) -> dict[int | None, list[Utterance]]:
        """Group utterances by their speaker ID.

        Args:
            utterances (tuple[Utterance, ...]): Tuple of utterances.

        Returns:
            dict[int | None, list[Utterance]]: Dictionary mapping speaker_id to list of utterances.
        """
        grouped: dict[int | None, list[Utterance]] = defaultdict(list)

        for utterance in utterances:
            # Utterance.speaker is the speaker index (int)
            speaker_id = utterance.speaker
            grouped[speaker_id].append(utterance)

        return dict(grouped)

    def _add_speaker_section(
        self,
        doc: DoclingDocument,
        speaker: Speaker,
        utterances: list[Utterance],
        *,
        include_word_timestamps: bool = False,
    ) -> None:
        """Add a speaker section with their utterances.

        Args:
            doc (DoclingDocument): The Docling document.
            speaker (Speaker): The speaker to add.
            utterances (list[Utterance]): The speaker's utterances.
            include_word_timestamps (bool): Whether to include word timestamps.
        """
        # Create section header for speaker
        speaker_section = doc.add_heading(
            text=speaker.label or f"Speaker {speaker.id}",
            level=1,
        )

        # Add speaker metadata
        # total_duration is in seconds, convert to ms for consistency
        duration_ms = int(speaker.total_duration * 1000)
        speaker_section.meta = BaseMeta(
            **{  # pyright: ignore[reportArgumentType]
                f"{AUDIO_META_NAMESPACE}__speaker_id": speaker.id,
                f"{AUDIO_META_NAMESPACE}__duration_ms": duration_ms,
                f"{AUDIO_META_NAMESPACE}__utterance_count": speaker.utterance_count,
            }
        )

        # Add utterances under this speaker
        for utterance in utterances:
            self._add_utterance(
                doc,
                utterance,
                parent=speaker_section,
                include_word_timestamps=include_word_timestamps,
            )

    def _add_orphan_utterances(
        self,
        doc: DoclingDocument,
        utterances: list[Utterance],
        *,
        include_word_timestamps: bool = False,
    ) -> None:
        """Add utterances without a speaker assignment.

        Args:
            doc (DoclingDocument): The Docling document.
            utterances (list[Utterance]): Utterances without speaker assignment.
            include_word_timestamps (bool): Whether to include word timestamps.
        """
        # Create a section for unknown speaker
        unknown_section = doc.add_heading(
            text="Unknown Speaker",
            level=1,
        )
        unknown_section.meta = BaseMeta(
            **{  # pyright: ignore[reportArgumentType]
                f"{AUDIO_META_NAMESPACE}__speaker_id": "unknown",
                f"{AUDIO_META_NAMESPACE}__utterance_count": len(utterances),
            }
        )

        for utterance in utterances:
            self._add_utterance(
                doc,
                utterance,
                parent=unknown_section,
                include_word_timestamps=include_word_timestamps,
            )

    def _add_utterance(
        self,
        doc: DoclingDocument,
        utterance: Utterance,
        parent: object,
        *,
        include_word_timestamps: bool = False,
    ) -> None:
        """Add an utterance as a text item.

        Args:
            doc (DoclingDocument): The Docling document.
            utterance (Utterance): The utterance to add.
            parent (object): The parent section header.
            include_word_timestamps (bool): Whether to include word timestamps.
        """
        # Convert seconds to milliseconds
        start_ms = int(utterance.start * 1000)
        end_ms = int(utterance.end * 1000)

        # Generate playback URL
        playback_url = self._generate_playback_url(start_ms, end_ms)

        # Create metadata dictionary
        meta_dict = {
            f"{AUDIO_META_NAMESPACE}__utterance_id": utterance.id,
            f"{AUDIO_META_NAMESPACE}__start_ms": start_ms,
            f"{AUDIO_META_NAMESPACE}__end_ms": end_ms,
            f"{AUDIO_META_NAMESPACE}__confidence": round(
                float(utterance.confidence), 4
            ),
            f"{AUDIO_META_NAMESPACE}__playback_url": playback_url,
        }

        # Speaker is an int (speaker index)
        meta_dict[f"{AUDIO_META_NAMESPACE}__speaker_id"] = utterance.speaker

        # Add word timestamps if requested
        if include_word_timestamps and utterance.words:
            word_data = [
                {
                    "text": w.word,  # Word model uses 'word' not 'text'
                    "start_ms": int(w.start * 1000),
                    "end_ms": int(w.end * 1000),
                    "confidence": round(float(w.confidence), 4),
                }
                for w in utterance.words
            ]
            meta_dict[f"{AUDIO_META_NAMESPACE}__words"] = word_data  # pyright: ignore[reportArgumentType]

        # Add text item
        text_item = doc.add_text(
            label=DocItemLabel.PARAGRAPH,
            text=utterance.text,
            parent=parent,  # pyright: ignore[reportArgumentType]
        )
        text_item.meta = BaseMeta(**meta_dict)  # pyright: ignore[reportAttributeAccessIssue, reportArgumentType]

    def _generate_playback_url(self, start_ms: int, end_ms: int) -> str:
        """Generate a Media Fragment URI for playback.

        Creates a URL using the W3C Media Fragment URI standard:
        https://www.w3.org/TR/media-frags/

        Args:
            start_ms (int): Start time in milliseconds.
            end_ms (int): End time in milliseconds.

        Returns:
            str: Media fragment URI (e.g., '#t=1.5,3.2' or 'http://example.com/audio.mp3#t=1.5,3.2').
        """
        # Convert milliseconds to seconds with 3 decimal places
        start_sec = start_ms / 1000
        end_sec = end_ms / 1000

        # Format with up to 3 decimal places, removing trailing zeros
        start_str = f"{start_sec:.3f}".rstrip("0").rstrip(".")
        end_str = f"{end_sec:.3f}".rstrip("0").rstrip(".")

        fragment = f"#t={start_str},{end_str}"

        if self.media_base_url:
            return f"{self.media_base_url}{fragment}"
        return fragment

    def export_to_json(self, result: DOMBuildResult) -> dict[str, object]:
        """Export the DOM result to a JSON-serializable dictionary.

        Args:
            result (DOMBuildResult): The DOM build result.

        Returns:
            dict[str, object]: JSON-serializable dictionary.
        """
        doc_dict = result.document.export_to_dict()

        # Add build metadata
        doc_dict["_audio_processor"] = {
            "speaker_count": result.speaker_count,
            "utterance_count": result.utterance_count,
            "total_duration_ms": result.total_duration_ms,
        }

        return doc_dict

    def export_to_markdown(self, result: DOMBuildResult) -> str:
        """Export the DOM result to Markdown format.

        Args:
            result (DOMBuildResult): The DOM build result.

        Returns:
            str: Markdown string representation.
        """
        return result.document.export_to_markdown()

    def export_to_text(self, result: DOMBuildResult) -> str:
        """Export the DOM result to plain text.

        Args:
            result (DOMBuildResult): The DOM build result.

        Returns:
            str: Plain text representation.
        """
        return result.document.export_to_text()
