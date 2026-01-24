"""Audio processing services.

This package contains the core services for audio file processing:
- AudioConverter: FFmpeg wrapper for format conversion and extraction
- AudioConditioner: Signal preprocessing (resampling, normalization)
- VADProcessor: Voice Activity Detection for silence removal
- QualityAssessor: Audio quality analysis and scoring
- DeepgramTranscriptionClient: Transcription service integration
- DOMBuilder: Docling DOM document generation
- TranscriptFormatter: Output format generators (TXT, SRT, VTT)
- ArtifactGenerator: Multi-format artifact generation
"""

from __future__ import annotations

from audio_processor.services.audio_conditioner import AudioConditioner
from audio_processor.services.audio_converter import AudioConverter
from audio_processor.services.deepgram_client import DeepgramTranscriptionClient
from audio_processor.services.dom_builder import DOMBuilder
from audio_processor.services.quality_assessor import QualityAssessor
from audio_processor.services.transcript_formatter import (
    ArtifactGenerator,
    TranscriptFormatter,
)
from audio_processor.services.vad_processor import VADProcessor

__all__ = [
    "ArtifactGenerator",
    "AudioConditioner",
    "AudioConverter",
    "DOMBuilder",
    "DeepgramTranscriptionClient",
    "QualityAssessor",
    "TranscriptFormatter",
    "VADProcessor",
]
