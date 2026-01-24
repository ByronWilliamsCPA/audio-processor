"""Audio processing services.

This package contains the core services for audio file processing:
- AudioConverter: FFmpeg wrapper for format conversion and extraction
- AudioConditioner: Signal preprocessing (resampling, normalization)
- VADProcessor: Voice Activity Detection for silence removal
- QualityAssessor: Audio quality analysis and scoring
- DeepgramTranscriptionClient: Transcription service integration
"""

from __future__ import annotations

from audio_processor.services.audio_converter import AudioConverter
from audio_processor.services.deepgram_client import DeepgramTranscriptionClient
from audio_processor.services.quality_assessor import QualityAssessor

__all__ = [
    "AudioConverter",
    "DeepgramTranscriptionClient",
    "QualityAssessor",
]
