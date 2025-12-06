---
title: "Project E - Audio Preprocessing Engine - Technical Implementation Specification"
schema_type: common
status: draft
owner: core-maintainer
purpose: "Draft technical specification for Project E audio preprocessing engine."
tags:
  - research
---

## Audio Preprocessing Engine

### Technical Implementation Specification

**Version 1.0** | December 2024
*RAG Pipeline Project Suite*
*Document 3 of 4*

---

## Document Information

| Field | Value |
|-------|-------|
| Project Name | audio-preprocessing-engine (Project E) |
| Document Type | Technical Implementation Specification (Document 3 of 4) |
| Version | 1.0 |
| Status | Draft |
| Last Updated | December 2024 |
| Prerequisites | Vision & Scope v1.0, ADR v1.0 |

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [API Specification](#2-api-specification)
3. [Data Models](#3-data-models)
4. [Processing Pipeline](#4-processing-pipeline)
5. [Deepgram Integration](#5-deepgram-integration)
6. [Docling DOM Mapping](#6-docling-dom-mapping)
7. [Configuration](#7-configuration)
8. [Error Handling](#8-error-handling)
9. [Testing Strategy](#9-testing-strategy)
10. [Monitoring & Observability](#10-monitoring--observability)
11. [Deployment](#11-deployment)

---

## 1. System Overview

### 1.1 Component Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PROJECT E INTERNAL ARCHITECTURE                      │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────────┐
                              │   FastAPI App    │
                              │   (main.py)      │
                              └────────┬─────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼
     ┌────────────────┐      ┌────────────────┐      ┌────────────────┐
     │   /ingest      │      │   /status      │      │   /health      │
     │   endpoint     │      │   endpoint     │      │   endpoint     │
     └───────┬────────┘      └───────┬────────┘      └────────────────┘
             │                       │
             ▼                       ▼
     ┌────────────────┐      ┌────────────────┐
     │  Job Queue     │      │  Job Status    │
     │  (Redis/RQ)    │◄────►│  Store (Redis) │
     └───────┬────────┘      └────────────────┘
             │
             ▼
     ┌────────────────────────────────────────────────────────────────┐
     │                      WORKER PROCESS                             │
     │  ┌──────────────────────────────────────────────────────────┐  │
     │  │                  AudioProcessor                           │  │
     │  │                                                           │  │
     │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │  │
     │  │  │   Ingest    │  │  Condition  │  │   Quality   │       │  │
     │  │  │  & Validate │─►│   Signal    │─►│  Assess     │       │  │
     │  │  └─────────────┘  └─────────────┘  └──────┬──────┘       │  │
     │  │                                          │               │  │
     │  │                                          ▼               │  │
     │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │  │
     │  │  │  Build DOM  │◄─┤   Process   │◄─┤  Deepgram   │       │  │
     │  │  │  & Output   │  │  Response   │  │  API Call   │       │  │
     │  │  └─────────────┘  └─────────────┘  └─────────────┘       │  │
     │  │                                                           │  │
     │  └──────────────────────────────────────────────────────────┘  │
     └────────────────────────────────────────────────────────────────┘
```

### 1.2 Technology Stack

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| Framework | FastAPI | 0.109+ | API server |
| Queue | Redis + RQ | 7.x / 1.x | Job management |
| Audio | FFmpeg | 6.x | Media processing |
| Audio Analysis | librosa | 0.10+ | Quality assessment |
| ASR | Deepgram SDK | 3.x | Transcription |
| Validation | Pydantic | 2.x | Data models |
| HTTP | httpx | 0.27+ | Async HTTP client |
| Testing | pytest | 8.x | Test framework |

### 1.3 Directory Structure

```
project-e/
├── src/
│   └── audio_preprocessing/
│       ├── __init__.py
│       ├── main.py              # FastAPI application
│       ├── config.py            # Settings and configuration
│       ├── models/
│       │   ├── __init__.py
│       │   ├── audio.py         # Audio-specific models
│       │   ├── job.py           # Job models
│       │   ├── deepgram.py      # Deepgram response models
│       │   └── docling.py       # Docling DOM models
│       ├── services/
│       │   ├── __init__.py
│       │   ├── processor.py     # Main processing orchestrator
│       │   ├── deepgram.py      # Deepgram API client
│       │   ├── quality.py       # Audio quality assessment
│       │   ├── converter.py     # FFmpeg operations
│       │   └── dom_builder.py   # Docling DOM construction
│       ├── workers/
│       │   ├── __init__.py
│       │   └── audio_worker.py  # RQ worker tasks
│       └── api/
│           ├── __init__.py
│           ├── routes.py        # API endpoints
│           └── dependencies.py  # FastAPI dependencies
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── Dockerfile
├── pyproject.toml
└── README.md
```

---

## 2. API Specification

### 2.1 Base URL

```
http://project-e:8000/api/v1
```

### 2.2 Endpoints

#### 2.2.1 Submit Audio for Processing

```
POST /api/v1/process
```

Submit an audio or video file for transcription and processing.

**Request:**

```
Content-Type: multipart/form-data
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | Audio or video file |
| `job_id` | string | No | Custom job ID (auto-generated if not provided) |
| `source_batch_id` | string | No | Parent batch ID from Web UI |
| `priority` | string | No | `low`, `normal`, `high` (default: `normal`) |
| `options` | JSON | No | Processing options (see below) |
| `callback_url` | string | No | Webhook URL for completion |

**Options Schema:**

```json
{
  "language": "en",           // ISO language code or "auto"
  "diarize": true,            // Enable speaker diarization
  "summarize": true,          // Generate summary
  "detect_language": true,    // Auto-detect language
  "skip_quality_check": false // Skip audio quality assessment
}
```

**Response:** `202 Accepted`

```json
{
  "job_id": "audio_abc123",
  "status": "queued",
  "created_at": "2024-12-04T10:30:00Z",
  "estimated_duration_seconds": 720,
  "status_url": "/api/v1/status/audio_abc123",
  "source_file": {
    "filename": "meeting.mp3",
    "size_bytes": 15728640,
    "duration_seconds": 3600
  }
}
```

**Error Responses:**

| Status | Code | Description |
|--------|------|-------------|
| 400 | `INVALID_FILE_TYPE` | Unsupported file format |
| 400 | `FILE_TOO_LARGE` | File exceeds 2GB limit |
| 400 | `FILE_TOO_SHORT` | File shorter than 1 second |
| 413 | `PAYLOAD_TOO_LARGE` | Request body exceeds limit |
| 422 | `VALIDATION_ERROR` | Invalid request parameters |

---

#### 2.2.2 Get Job Status

```
GET /api/v1/status/{job_id}
```

Retrieve current status and progress of a processing job.

**Response:** `200 OK`

```json
{
  "job_id": "audio_abc123",
  "status": "processing",
  "progress": {
    "stage": "transcribing",
    "percent": 45,
    "stage_started_at": "2024-12-04T10:31:00Z"
  },
  "stages_completed": ["ingested", "validated", "conditioned", "quality_assessed"],
  "stages_remaining": ["transcribing", "diarizing", "summarizing", "building_dom"],
  "created_at": "2024-12-04T10:30:00Z",
  "updated_at": "2024-12-04T10:32:00Z",
  "source_file": {
    "filename": "meeting.mp3",
    "duration_seconds": 3600
  },
  "quality": {
    "snr_db": 25.5,
    "quality_score": 0.85,
    "warnings": []
  }
}
```

**Job Status Values:**

| Status | Description |
|--------|-------------|
| `queued` | Job is waiting in queue |
| `processing` | Job is actively being processed |
| `completed` | Job finished successfully |
| `failed` | Job failed with error |
| `cancelled` | Job was cancelled |

---

#### 2.2.3 Get Job Results

```
GET /api/v1/results/{job_id}
```

Retrieve completed job results including transcription and Docling DOM.

**Response:** `200 OK`

```json
{
  "job_id": "audio_abc123",
  "status": "completed",
  "processing": {
    "started_at": "2024-12-04T10:30:15Z",
    "completed_at": "2024-12-04T10:36:45Z",
    "duration_seconds": 390,
    "deepgram_cost_usd": 0.348
  },
  "source_file": {
    "filename": "meeting.mp3",
    "file_hash": "sha256:a1b2c3...",
    "size_bytes": 15728640,
    "mime_type": "audio/mpeg"
  },
  "audio_properties": {
    "duration_ms": 3600000,
    "sample_rate": 44100,
    "channels": 2,
    "format": "mp3"
  },
  "audio_quality": {
    "snr_db": 25.5,
    "silence_ratio": 0.08,
    "clipping_ratio": 0.001,
    "quality_score": 0.85,
    "warnings": []
  },
  "transcription": {
    "language": "en",
    "language_confidence": 0.98,
    "word_count": 8500,
    "speaker_count": 3,
    "confidence_mean": 0.94
  },
  "speakers": [
    {
      "id": "speaker_0",
      "label": "Speaker 1",
      "duration_ms": 1200000,
      "utterance_count": 45,
      "word_count": 2800
    }
  ],
  "summary": {
    "text": "The meeting covered Q4 planning, budget allocation, and team restructuring...",
    "type": "deepgram_v2"
  },
  "outputs": {
    "audio_document_url": "/api/v1/artifacts/audio_abc123/audio_document.json",
    "docling_dom_url": "/api/v1/artifacts/audio_abc123/docling_dom.json",
    "transcript_txt_url": "/api/v1/artifacts/audio_abc123/transcript.txt"
  }
}
```

---

#### 2.2.4 Get Artifact

```
GET /api/v1/artifacts/{job_id}/{artifact_name}
```

Download a specific output artifact.

**Available Artifacts:**

| Artifact | Description |
|----------|-------------|
| `audio_document.json` | Full AudioDocument with all metadata |
| `docling_dom.json` | Docling DOM structure for pipeline |
| `transcript.txt` | Plain text transcript |
| `transcript_srt.srt` | SRT subtitle format |
| `speakers.json` | Speaker-only data |

**Response:** `200 OK` with appropriate `Content-Type`

---

#### 2.2.5 Cancel Job

```
POST /api/v1/cancel/{job_id}
```

Cancel a queued or processing job.

**Response:** `200 OK`

```json
{
  "job_id": "audio_abc123",
  "status": "cancelled",
  "cancelled_at": "2024-12-04T10:35:00Z"
}
```

---

#### 2.2.6 Health Check

```
GET /health
```

**Response:** `200 OK`

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "dependencies": {
    "redis": "connected",
    "deepgram": "reachable",
    "ffmpeg": "available"
  },
  "queue": {
    "pending": 5,
    "processing": 2
  }
}
```

---

## 3. Data Models

### 3.1 Core Models

#### 3.1.1 AudioFile

```python
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class AudioFormat(str, Enum):
    MP3 = "mp3"
    WAV = "wav"
    M4A = "m4a"
    FLAC = "flac"
    OGG = "ogg"
    AAC = "aac"
    WMA = "wma"
    # Video formats (audio extracted)
    MP4 = "mp4"
    MOV = "mov"
    AVI = "avi"
    MKV = "mkv"
    WEBM = "webm"

class AudioFile(BaseModel):
    """Input audio/video file metadata."""
    filename: str
    file_hash: str = Field(..., description="SHA-256 hash")
    size_bytes: int
    mime_type: str
    format: AudioFormat

class AudioProperties(BaseModel):
    """Technical audio properties."""
    duration_ms: int
    sample_rate: int
    channels: int
    bit_depth: int | None = None
    bitrate_kbps: int | None = None
    format: AudioFormat

class AudioQuality(BaseModel):
    """Audio quality assessment results."""
    snr_db: float = Field(..., description="Signal-to-noise ratio in dB")
    silence_ratio: float = Field(..., ge=0, le=1, description="Fraction of silence")
    clipping_ratio: float = Field(..., ge=0, le=1, description="Fraction of clipped samples")
    quality_score: float = Field(..., ge=0, le=1, description="Composite quality score")
    warnings: list[str] = Field(default_factory=list)
```

#### 3.1.2 Speaker

```python
class Speaker(BaseModel):
    """Speaker identification and statistics."""
    id: str = Field(..., description="Internal speaker ID (speaker_0, speaker_1, ...)")
    label: str = Field(..., description="Display label (Speaker 1, Speaker 2, ...)")
    duration_ms: int = Field(..., description="Total speaking time")
    utterance_count: int
    word_count: int
    confidence_mean: float = Field(..., ge=0, le=1)

class Utterance(BaseModel):
    """A single speaker utterance (continuous speech segment)."""
    id: str
    speaker_id: str
    text: str
    start_ms: int
    end_ms: int
    confidence: float = Field(..., ge=0, le=1)
    words: list["Word"] = Field(default_factory=list)

class Word(BaseModel):
    """Individual word with timing."""
    text: str
    start_ms: int
    end_ms: int
    confidence: float
    speaker_id: str | None = None
```

#### 3.1.3 Transcription

```python
class TranscriptionMetadata(BaseModel):
    """Transcription results metadata."""
    language: str = Field(..., description="ISO 639-1 language code")
    language_confidence: float
    word_count: int
    speaker_count: int
    confidence_mean: float
    confidence_min: float

class Summary(BaseModel):
    """Auto-generated summary."""
    text: str
    type: str = "deepgram_v2"
    word_count: int
```

#### 3.1.4 Job

```python
class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ProcessingStage(str, Enum):
    INGESTED = "ingested"
    VALIDATED = "validated"
    CONDITIONED = "conditioned"
    QUALITY_ASSESSED = "quality_assessed"
    TRANSCRIBING = "transcribing"
    DIARIZING = "diarizing"
    SUMMARIZING = "summarizing"
    BUILDING_DOM = "building_dom"
    COMPLETED = "completed"

class JobProgress(BaseModel):
    """Current job progress."""
    stage: ProcessingStage
    percent: int = Field(..., ge=0, le=100)
    stage_started_at: datetime
    message: str | None = None

class Job(BaseModel):
    """Audio processing job."""
    job_id: str
    status: JobStatus
    priority: str = "normal"
    progress: JobProgress | None = None
    stages_completed: list[ProcessingStage] = Field(default_factory=list)
    stages_remaining: list[ProcessingStage] = Field(default_factory=list)

    source_file: AudioFile
    source_batch_id: str | None = None

    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime

    error: "JobError | None" = None

class JobError(BaseModel):
    """Job error details."""
    code: str
    message: str
    stage: ProcessingStage
    details: dict | None = None
    recoverable: bool = False
```

### 3.2 Output Models

#### 3.2.1 AudioDocument

```python
class DeepgramMetadata(BaseModel):
    """Deepgram API call metadata."""
    model: str = "nova-2"
    request_id: str
    processing_time_ms: int
    cost_usd: float

class AudioDocument(BaseModel):
    """
    Complete audio processing output.
    This is the primary output of Project E.
    """
    document_id: str
    source_file: AudioFile
    audio_properties: AudioProperties
    audio_quality: AudioQuality
    deepgram_metadata: DeepgramMetadata
    transcription: TranscriptionMetadata
    speakers: list[Speaker]
    utterances: list[Utterance]
    summary: Summary | None = None
    docling_document: "DoclingDocument"

    created_at: datetime
    pipeline_version: str = "1.0.0"
```

---

## 4. Processing Pipeline

### 4.1 Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PROCESSING PIPELINE STAGES                           │
└─────────────────────────────────────────────────────────────────────────────┘

Stage 1: INGEST
├── Receive file from API
├── Generate file hash (SHA-256)
├── Extract basic metadata
└── Store to processing directory

Stage 2: VALIDATE
├── Verify file format (magic bytes)
├── Check file size limits
├── Verify minimum duration
└── Detect if video (needs audio extraction)

Stage 3: CONDITION
├── Extract audio from video (if needed)
├── Convert to optimal format for Deepgram
├── Split long files (>4 hours)
└── Normalize audio levels (optional)

Stage 4: QUALITY ASSESS
├── Calculate SNR
├── Detect silence ratio
├── Check for clipping
├── Generate quality score
└── Produce warnings (if applicable)

Stage 5: TRANSCRIBE (Deepgram API)
├── Upload audio to Deepgram
├── Request transcription with options:
│   ├── model: nova-2
│   ├── smart_format: true
│   ├── diarize: true
│   ├── paragraphs: true
│   ├── utterances: true
│   └── summarize: v2
└── Receive JSON response

Stage 6: PROCESS RESPONSE
├── Parse Deepgram JSON
├── Extract utterances and words
├── Build speaker profiles
├── Extract summary
└── Calculate statistics

Stage 7: BUILD DOM
├── Create DoclingDocument
├── Map speakers → SectionItems
├── Map utterances → TextItems
├── Attach timestamps as provenance
└── Add summary section

Stage 8: OUTPUT
├── Generate AudioDocument.json
├── Serialize Docling DOM
├── Generate plain text transcript
├── Update job status
└── Trigger callback (if configured)
```

### 4.2 Core Processor Implementation

```python
# src/audio_preprocessing/services/processor.py

from dataclasses import dataclass
from pathlib import Path
import asyncio

from ..models.audio import AudioFile, AudioProperties, AudioQuality
from ..models.job import Job, JobStatus, ProcessingStage
from ..services.deepgram import DeepgramClient
from ..services.quality import QualityAssessor
from ..services.converter import AudioConverter
from ..services.dom_builder import DoclingDOMBuilder

@dataclass
class ProcessingResult:
    """Result of audio processing."""
    audio_document: "AudioDocument"
    docling_dom: "DoclingDocument"
    processing_time_ms: int
    deepgram_cost_usd: float

class AudioProcessor:
    """
    Main audio processing orchestrator.
    Coordinates all processing stages.
    """

    def __init__(
        self,
        deepgram_client: DeepgramClient,
        quality_assessor: QualityAssessor,
        converter: AudioConverter,
        dom_builder: DoclingDOMBuilder,
    ):
        self.deepgram = deepgram_client
        self.quality = quality_assessor
        self.converter = converter
        self.dom_builder = dom_builder

    async def process(
        self,
        job: Job,
        file_path: Path,
        options: dict,
        progress_callback: callable | None = None,
    ) -> ProcessingResult:
        """
        Process an audio file through the complete pipeline.

        Args:
            job: Job metadata
            file_path: Path to input file
            options: Processing options
            progress_callback: Optional callback for progress updates

        Returns:
            ProcessingResult with AudioDocument and DoclingDOM
        """

        # Stage 1: Validate
        await self._update_progress(progress_callback, ProcessingStage.VALIDATED, 10)
        audio_props = await self._validate_file(file_path)

        # Stage 2: Condition (convert/extract if needed)
        await self._update_progress(progress_callback, ProcessingStage.CONDITIONED, 20)
        processed_path = await self._condition_audio(file_path, audio_props)

        # Stage 3: Quality assessment
        await self._update_progress(progress_callback, ProcessingStage.QUALITY_ASSESSED, 30)
        quality = await self._assess_quality(processed_path)

        # Stage 4: Transcribe with Deepgram
        await self._update_progress(progress_callback, ProcessingStage.TRANSCRIBING, 40)
        deepgram_response = await self.deepgram.transcribe(
            file_path=processed_path,
            options=self._build_deepgram_options(options),
        )

        # Stage 5: Process response
        await self._update_progress(progress_callback, ProcessingStage.BUILDING_DOM, 80)
        speakers, utterances, summary = self._process_deepgram_response(deepgram_response)

        # Stage 6: Build Docling DOM
        docling_dom = self.dom_builder.build(
            speakers=speakers,
            utterances=utterances,
            summary=summary,
            source_file=job.source_file,
            audio_props=audio_props,
        )

        # Stage 7: Build AudioDocument
        await self._update_progress(progress_callback, ProcessingStage.COMPLETED, 100)
        audio_document = self._build_audio_document(
            job=job,
            audio_props=audio_props,
            quality=quality,
            deepgram_response=deepgram_response,
            speakers=speakers,
            utterances=utterances,
            summary=summary,
            docling_dom=docling_dom,
        )

        return ProcessingResult(
            audio_document=audio_document,
            docling_dom=docling_dom,
            processing_time_ms=deepgram_response.metadata.processing_time_ms,
            deepgram_cost_usd=self._calculate_cost(audio_props.duration_ms),
        )

    async def _validate_file(self, file_path: Path) -> AudioProperties:
        """Validate file and extract properties."""
        return await self.converter.get_properties(file_path)

    async def _condition_audio(
        self,
        file_path: Path,
        props: AudioProperties
    ) -> Path:
        """Convert/extract audio as needed."""
        # Extract audio from video
        if props.format in ['mp4', 'mov', 'avi', 'mkv', 'webm']:
            file_path = await self.converter.extract_audio(file_path)

        # Convert to optimal format for Deepgram (16kHz mono MP3)
        if props.sample_rate != 16000 or props.channels != 1:
            file_path = await self.converter.convert(
                file_path,
                sample_rate=16000,
                channels=1,
                format='mp3',
            )

        return file_path

    async def _assess_quality(self, file_path: Path) -> AudioQuality:
        """Assess audio quality."""
        return await self.quality.assess(file_path)

    def _build_deepgram_options(self, options: dict) -> dict:
        """Build Deepgram API options."""
        return {
            "model": "nova-2",
            "smart_format": True,
            "diarize": options.get("diarize", True),
            "paragraphs": True,
            "utterances": True,
            "summarize": "v2" if options.get("summarize", True) else False,
            "detect_language": options.get("detect_language", True),
            "language": options.get("language", "en"),
            "punctuate": True,
            "profanity_filter": False,
        }
```

---

## 5. Deepgram Integration

### 5.1 Client Implementation

```python
# src/audio_preprocessing/services/deepgram.py

from pathlib import Path
from deepgram import DeepgramClient, PrerecordedOptions, FileSource
import httpx

from ..config import settings
from ..models.deepgram import DeepgramResponse

class DeepgramService:
    """
    Deepgram API client for transcription.
    """

    def __init__(self):
        self.client = DeepgramClient(settings.DEEPGRAM_API_KEY)
        self.timeout = settings.DEEPGRAM_TIMEOUT_SECONDS

    async def transcribe(
        self,
        file_path: Path,
        options: dict,
    ) -> DeepgramResponse:
        """
        Transcribe audio file using Deepgram Nova-2.

        Args:
            file_path: Path to audio file
            options: Deepgram API options

        Returns:
            Parsed DeepgramResponse
        """
        # Read file
        with open(file_path, "rb") as f:
            audio_data = f.read()

        # Build options
        dg_options = PrerecordedOptions(
            model=options.get("model", "nova-2"),
            smart_format=options.get("smart_format", True),
            diarize=options.get("diarize", True),
            paragraphs=options.get("paragraphs", True),
            utterances=options.get("utterances", True),
            summarize=options.get("summarize", "v2"),
            detect_language=options.get("detect_language", True),
            language=options.get("language"),
            punctuate=options.get("punctuate", True),
            profanity_filter=options.get("profanity_filter", False),
        )

        # Make API call
        source = FileSource(buffer=audio_data)

        response = await self.client.listen.asyncrest.v1.transcribe_file(
            source,
            dg_options,
            timeout=httpx.Timeout(self.timeout, connect=10.0),
        )

        return DeepgramResponse.from_api_response(response)

    async def check_health(self) -> bool:
        """Check Deepgram API connectivity."""
        try:
            # Simple connectivity check
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.deepgram.com/v1/projects",
                    headers={"Authorization": f"Token {settings.DEEPGRAM_API_KEY}"},
                    timeout=5.0,
                )
                return response.status_code == 200
        except Exception:
            return False
```

### 5.2 Response Parsing

```python
# src/audio_preprocessing/models/deepgram.py

from pydantic import BaseModel
from typing import Any

class DeepgramWord(BaseModel):
    """Word from Deepgram response."""
    word: str
    start: float
    end: float
    confidence: float
    speaker: int | None = None
    punctuated_word: str | None = None

class DeepgramUtterance(BaseModel):
    """Utterance from Deepgram response."""
    start: float
    end: float
    confidence: float
    channel: int
    transcript: str
    words: list[DeepgramWord]
    speaker: int | None = None
    id: str

class DeepgramParagraph(BaseModel):
    """Paragraph from Deepgram response."""
    sentences: list[dict]
    start: float
    end: float
    num_words: int
    speaker: int | None = None

class DeepgramSummary(BaseModel):
    """Summary from Deepgram response."""
    short: str | None = None

class DeepgramMetadata(BaseModel):
    """Metadata from Deepgram response."""
    request_id: str
    model_info: dict
    duration: float
    channels: int

class DeepgramResponse(BaseModel):
    """Parsed Deepgram API response."""
    metadata: DeepgramMetadata
    transcript: str
    confidence: float
    words: list[DeepgramWord]
    utterances: list[DeepgramUtterance]
    paragraphs: list[DeepgramParagraph]
    summaries: list[DeepgramSummary] | None = None
    detected_language: str | None = None
    language_confidence: float | None = None

    @classmethod
    def from_api_response(cls, response: Any) -> "DeepgramResponse":
        """Parse raw Deepgram API response."""
        results = response.results
        channels = results.channels[0]
        alternatives = channels.alternatives[0]

        return cls(
            metadata=DeepgramMetadata(
                request_id=response.metadata.request_id,
                model_info=response.metadata.model_info,
                duration=response.metadata.duration,
                channels=response.metadata.channels,
            ),
            transcript=alternatives.transcript,
            confidence=alternatives.confidence,
            words=[DeepgramWord(**w) for w in alternatives.words],
            utterances=[
                DeepgramUtterance(**u)
                for u in (results.utterances or [])
            ],
            paragraphs=[
                DeepgramParagraph(**p)
                for p in (alternatives.paragraphs.paragraphs if alternatives.paragraphs else [])
            ],
            summaries=[
                DeepgramSummary(**s)
                for s in (results.summary.short if results.summary else [])
            ],
            detected_language=channels.detected_language,
            language_confidence=channels.language_confidence,
        )
```

---

## 6. Docling DOM Mapping

### 6.1 Mapping Strategy

```python
# src/audio_preprocessing/services/dom_builder.py

from docling_core.types.doc import (
    DoclingDocument,
    DocumentOrigin,
    SectionItem,
    TextItem,
    ProvenanceItem,
)
from datetime import datetime

from ..models.audio import AudioFile, AudioProperties, Speaker, Utterance, Summary

class DoclingDOMBuilder:
    """
    Builds Docling Document Object Model from audio transcription.

    Mapping:
    - Full transcript → DoclingDocument
    - Speaker turn → SectionItem (with speaker metadata)
    - Utterance → TextItem (with timestamps in provenance)
    - Summary → SectionItem (special, marked as summary)
    """

    def build(
        self,
        speakers: list[Speaker],
        utterances: list[Utterance],
        summary: Summary | None,
        source_file: AudioFile,
        audio_props: AudioProperties,
    ) -> DoclingDocument:
        """
        Build Docling DOM from transcription data.
        """
        # Create document
        doc = DoclingDocument(
            name=source_file.filename,
            origin=DocumentOrigin(
                filename=source_file.filename,
                mimetype=source_file.mime_type,
                binary_hash=source_file.file_hash,
            ),
        )

        # Add document-level metadata
        doc.meta = {
            "source_type": "audio",
            "duration_ms": audio_props.duration_ms,
            "sample_rate": audio_props.sample_rate,
            "channels": audio_props.channels,
            "speaker_count": len(speakers),
            "speakers": [s.model_dump() for s in speakers],
        }

        # Group utterances by speaker
        speaker_utterances = self._group_by_speaker(utterances)

        # Add speaker sections
        for speaker in speakers:
            section = self._build_speaker_section(
                speaker=speaker,
                utterances=speaker_utterances.get(speaker.id, []),
                source_file=source_file,
            )
            doc.add_section(section)

        # Add summary section (if available)
        if summary:
            summary_section = self._build_summary_section(summary)
            doc.add_section(summary_section)

        return doc

    def _build_speaker_section(
        self,
        speaker: Speaker,
        utterances: list[Utterance],
        source_file: AudioFile,
    ) -> SectionItem:
        """Build a section for a single speaker."""
        section = SectionItem(
            name=speaker.label,
            level=1,
        )

        # Add speaker metadata
        section.meta = {
            "speaker_id": speaker.id,
            "speaker_label": speaker.label,
            "duration_ms": speaker.duration_ms,
            "utterance_count": speaker.utterance_count,
            "word_count": speaker.word_count,
        }

        # Add utterances as text items
        for utterance in utterances:
            text_item = self._build_text_item(utterance, source_file)
            section.add_child(text_item)

        return section

    def _build_text_item(
        self,
        utterance: Utterance,
        source_file: AudioFile,
    ) -> TextItem:
        """Build a text item from an utterance."""
        text_item = TextItem(
            text=utterance.text,
            label="paragraph",
        )

        # Add provenance with timestamps
        text_item.prov = [
            ProvenanceItem(
                page_no=0,  # No page concept for audio
                bbox=None,
                charspan=(0, len(utterance.text)),
            )
        ]

        # Add audio-specific metadata
        text_item.meta = {
            "utterance_id": utterance.id,
            "speaker_id": utterance.speaker_id,
            "start_ms": utterance.start_ms,
            "end_ms": utterance.end_ms,
            "confidence": utterance.confidence,
            "playback_url": self._build_playback_url(
                source_file.filename,
                utterance.start_ms,
                utterance.end_ms,
            ),
        }

        return text_item

    def _build_summary_section(self, summary: Summary) -> SectionItem:
        """Build summary section."""
        section = SectionItem(
            name="Summary",
            level=0,  # Top-level section
        )

        section.meta = {
            "is_summary": True,
            "summary_type": summary.type,
        }

        text_item = TextItem(
            text=summary.text,
            label="summary",
        )
        section.add_child(text_item)

        return section

    def _group_by_speaker(
        self,
        utterances: list[Utterance]
    ) -> dict[str, list[Utterance]]:
        """Group utterances by speaker ID."""
        grouped = {}
        for utt in utterances:
            if utt.speaker_id not in grouped:
                grouped[utt.speaker_id] = []
            grouped[utt.speaker_id].append(utt)
        return grouped

    def _build_playback_url(
        self,
        filename: str,
        start_ms: int,
        end_ms: int,
    ) -> str:
        """Build playback URL with timestamp fragment."""
        # Format: filename#t=start,end (Media Fragments URI)
        start_sec = start_ms / 1000
        end_sec = end_ms / 1000
        return f"{filename}#t={start_sec:.1f},{end_sec:.1f}"
```

### 6.2 Example Output

```json
{
  "name": "meeting_2024-12-03.mp3",
  "origin": {
    "filename": "meeting_2024-12-03.mp3",
    "mimetype": "audio/mpeg",
    "binary_hash": "sha256:a1b2c3..."
  },
  "meta": {
    "source_type": "audio",
    "duration_ms": 3600000,
    "sample_rate": 44100,
    "channels": 2,
    "speaker_count": 3,
    "speakers": [
      {"id": "speaker_0", "label": "Speaker 1", "duration_ms": 1200000}
    ]
  },
  "body": [
    {
      "type": "section",
      "name": "Speaker 1",
      "level": 1,
      "meta": {
        "speaker_id": "speaker_0",
        "speaker_label": "Speaker 1"
      },
      "children": [
        {
          "type": "text",
          "text": "Good morning everyone. Let's start with the Q4 review.",
          "label": "paragraph",
          "meta": {
            "utterance_id": "utt_001",
            "speaker_id": "speaker_0",
            "start_ms": 1500,
            "end_ms": 5200,
            "confidence": 0.96,
            "playback_url": "meeting_2024-12-03.mp3#t=1.5,5.2"
          }
        }
      ]
    },
    {
      "type": "section",
      "name": "Summary",
      "level": 0,
      "meta": {
        "is_summary": true,
        "summary_type": "deepgram_v2"
      },
      "children": [
        {
          "type": "text",
          "text": "The meeting covered Q4 planning and budget allocation...",
          "label": "summary"
        }
      ]
    }
  ]
}
```

---

## 7. Configuration

### 7.1 Environment Variables

```python
# src/audio_preprocessing/config.py

from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """Application settings."""

    # Service
    SERVICE_NAME: str = "project-e"
    SERVICE_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Deepgram
    DEEPGRAM_API_KEY: str
    DEEPGRAM_TIMEOUT_SECONDS: int = 3600  # 1 hour max
    DEEPGRAM_MODEL: str = "nova-2"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_JOB_TTL_SECONDS: int = 86400  # 24 hours

    # Processing
    MAX_FILE_SIZE_BYTES: int = 2 * 1024 * 1024 * 1024  # 2GB
    MAX_DURATION_SECONDS: int = 14400  # 4 hours (split if longer)
    MIN_DURATION_SECONDS: int = 1
    PROCESSING_TEMP_DIR: str = "/tmp/audio-processing"
    OUTPUT_DIR: str = "/data/outputs"

    # Quality thresholds
    QUALITY_SNR_WARNING_THRESHOLD: float = 10.0  # dB
    QUALITY_SILENCE_WARNING_THRESHOLD: float = 0.8  # 80%
    QUALITY_CLIPPING_WARNING_THRESHOLD: float = 0.05  # 5%

    # Callbacks
    CALLBACK_TIMEOUT_SECONDS: int = 30
    CALLBACK_RETRY_COUNT: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

### 7.2 Environment File Template

```bash
# .env

# ===========================================
# SERVICE CONFIGURATION
# ===========================================
SERVICE_NAME=project-e
DEBUG=false

# ===========================================
# DEEPGRAM API
# ===========================================
DEEPGRAM_API_KEY=your_deepgram_api_key_here
DEEPGRAM_TIMEOUT_SECONDS=3600
DEEPGRAM_MODEL=nova-2

# ===========================================
# REDIS
# ===========================================
REDIS_URL=redis://redis:6379

# ===========================================
# PROCESSING
# ===========================================
MAX_FILE_SIZE_BYTES=2147483648
MAX_DURATION_SECONDS=14400
PROCESSING_TEMP_DIR=/tmp/audio-processing
OUTPUT_DIR=/data/outputs

# ===========================================
# QUALITY THRESHOLDS
# ===========================================
QUALITY_SNR_WARNING_THRESHOLD=10.0
QUALITY_SILENCE_WARNING_THRESHOLD=0.8
QUALITY_CLIPPING_WARNING_THRESHOLD=0.05
```

---

## 8. Error Handling

### 8.1 Error Codes

| Code | HTTP Status | Description | Recoverable |
|------|-------------|-------------|-------------|
| `INVALID_FILE_TYPE` | 400 | Unsupported file format | No |
| `FILE_TOO_LARGE` | 400 | File exceeds size limit | No |
| `FILE_TOO_SHORT` | 400 | File shorter than minimum | No |
| `FILE_CORRUPTED` | 400 | Cannot read/decode file | No |
| `DEEPGRAM_ERROR` | 502 | Deepgram API error | Yes |
| `DEEPGRAM_TIMEOUT` | 504 | Deepgram request timeout | Yes |
| `DEEPGRAM_QUOTA` | 429 | Deepgram quota exceeded | Yes |
| `FFMPEG_ERROR` | 500 | Audio conversion failed | Maybe |
| `QUALITY_TOO_LOW` | 422 | Audio quality below threshold | No |
| `PROCESSING_ERROR` | 500 | Unexpected processing error | Maybe |
| `STORAGE_ERROR` | 500 | Cannot write output files | Yes |

### 8.2 Retry Strategy

```python
from rq import Retry

# Retry configuration for different error types
RETRY_STRATEGIES = {
    "deepgram_timeout": Retry(max=3, interval=[60, 120, 300]),
    "deepgram_error": Retry(max=2, interval=[30, 60]),
    "storage_error": Retry(max=3, interval=[10, 30, 60]),
    "default": Retry(max=1, interval=[30]),
}
```

---

## 9. Testing Strategy

### 9.1 Test Categories

| Category | Coverage Target | Tools |
|----------|-----------------|-------|
| Unit Tests | 80%+ | pytest, pytest-asyncio |
| Integration Tests | Key flows | pytest, testcontainers |
| E2E Tests | Happy paths | pytest, real Deepgram (test key) |

### 9.2 Test Fixtures

```python
# tests/fixtures/audio.py

import pytest
from pathlib import Path

@pytest.fixture
def sample_audio_mp3(tmp_path) -> Path:
    """Generate a short test MP3 file."""
    # Use pydub to create silent audio
    from pydub import AudioSegment
    from pydub.generators import Sine

    # 10 seconds of 440Hz tone
    tone = Sine(440).to_audio_segment(duration=10000)
    path = tmp_path / "test.mp3"
    tone.export(path, format="mp3")
    return path

@pytest.fixture
def mock_deepgram_response() -> dict:
    """Mock Deepgram API response."""
    return {
        "metadata": {
            "request_id": "test-123",
            "duration": 10.0,
            "channels": 1,
        },
        "results": {
            "channels": [{
                "alternatives": [{
                    "transcript": "Hello world, this is a test.",
                    "confidence": 0.95,
                    "words": [
                        {"word": "Hello", "start": 0.0, "end": 0.5, "confidence": 0.98},
                        {"word": "world", "start": 0.5, "end": 1.0, "confidence": 0.96},
                    ],
                }],
            }],
            "utterances": [],
        },
    }
```

---

## 10. Monitoring & Observability

### 10.1 Metrics (Prometheus)

```python
# Key metrics to export

audio_jobs_total = Counter(
    "audio_jobs_total",
    "Total audio processing jobs",
    ["status"]  # queued, completed, failed
)

audio_processing_duration_seconds = Histogram(
    "audio_processing_duration_seconds",
    "Audio processing duration",
    ["stage"],
    buckets=[10, 30, 60, 120, 300, 600, 1200, 3600]
)

audio_file_duration_seconds = Histogram(
    "audio_file_duration_seconds",
    "Input audio file duration",
    buckets=[60, 300, 600, 1800, 3600, 7200, 14400]
)

deepgram_api_calls_total = Counter(
    "deepgram_api_calls_total",
    "Deepgram API calls",
    ["status"]  # success, error, timeout
)

deepgram_cost_usd_total = Counter(
    "deepgram_cost_usd_total",
    "Cumulative Deepgram API cost in USD"
)

audio_quality_score = Histogram(
    "audio_quality_score",
    "Audio quality scores",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)
```

### 10.2 Logging

```python
# Structured logging configuration
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)

# Usage
logger = structlog.get_logger()

logger.info(
    "audio_processing_started",
    job_id=job.job_id,
    filename=job.source_file.filename,
    duration_seconds=audio_props.duration_ms / 1000,
)
```

---

## 11. Deployment

### 11.1 Dockerfile

```dockerfile
# Dockerfile

FROM python:3.11-slim

# Install FFmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Install dependencies
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction

# Copy application
COPY src/ ./src/

# Set ownership
RUN chown -R appuser:appuser /app

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "src.audio_preprocessing.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 11.2 Docker Compose Service

```yaml
# docker-compose.yml (Project E service)

services:
  project-e:
    build:
      context: ./project-e
      dockerfile: Dockerfile
    container_name: rag-project-e
    restart: unless-stopped
    expose:
      - "8000"
    environment:
      DEEPGRAM_API_KEY: ${DEEPGRAM_API_KEY}
      REDIS_URL: redis://redis:6379
      OUTPUT_DIR: /data/outputs
      PROCESSING_TEMP_DIR: /tmp/audio-processing
    volumes:
      - ${RAG_DATA_PATH}/uploads:/data/uploads:ro
      - ${RAG_DATA_PATH}/outputs/project-e:/data/outputs
      - project-e-temp:/tmp/audio-processing
    networks:
      - rag-network
    depends_on:
      redis:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: "4"
        reservations:
          memory: 2G
          cpus: "2"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  project-e-temp:
```

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | December 2024 | — | Initial technical specification |

---

*— End of Document —*
