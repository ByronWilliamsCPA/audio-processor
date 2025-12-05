---
title: "Audio Processor - Technical Specification"
schema_type: planning
status: published
owner: core-maintainer
purpose: "Document the technical architecture and implementation details."
tags:
  - planning
  - architecture
component: Development-Tools
source: "/plan command generation"
---

> **Status**: Approved | **Version**: 1.0 | **Updated**: 2025-12-04

## TL;DR

FastAPI-based async audio processing service using Deepgram Nova-2 API, Redis Queue for job management, FFmpeg for media handling, and Docling DOM for pipeline-compatible output. Python 3.12 with UV, Ruff, BasedPyright, and pytest.

## 1. Technology Stack

### Core

- **Language**: Python 3.12
- **Package Manager**: UV
- **Framework**: FastAPI 0.109+ (async API server)
- **CLI**: Click (command-line interface)

### Code Quality

- **Linter**: Ruff (PyStrict-aligned rules, 88-char line length)
- **Type Checker**: BasedPyright (strict mode)
- **Formatter**: Ruff format
- **Testing**: pytest 8.x with pytest-asyncio

### External Services

- **ASR Engine**: Deepgram SDK 3.x (Nova-2 model) - See [ADR-001](./adr/adr-001-initial-architecture.md)
- **Queue**: Redis 7.x + RQ 1.x (job management)
- **Media Processing**: FFmpeg 6.x (audio extraction, conversion)
- **Audio Analysis**: librosa 0.10+ (quality assessment)

### Infrastructure

- **CI/CD**: GitHub Actions (linting, testing, security scans)
- **Container**: Docker (multi-stage build, non-root user)
- **Deployment**: Docker Compose (service orchestration)

## 2. Architecture

### Pattern

**Async Queue-Based Microservice** - FastAPI frontend receives requests, RQ workers process jobs asynchronously, Redis manages state.

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      FASTAPI APPLICATION                    │
├────────────────┬────────────────┬──────────────────────────┤
│  POST /process │  GET /status   │  GET /results            │
│  (ingest)      │  (tracking)    │  (artifacts)             │
└───────┬────────┴────────┬───────┴────────┬─────────────────┘
        │                 │                │
        ▼                 ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│                     REDIS (State + Queue)                   │
│  • Job Queue (RQ)    • Status Store    • Progress Tracking  │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                      RQ WORKER PROCESS                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              AudioProcessor Orchestrator             │   │
│  │  ┌────────┐  ┌──────────┐  ┌────────────┐           │   │
│  │  │Validate│─►│Condition │─►│Quality     │           │   │
│  │  │File    │  │(FFmpeg)  │  │Assessment  │           │   │
│  │  └────────┘  └──────────┘  └──────┬─────┘           │   │
│  │                                    │                 │   │
│  │                                    ▼                 │   │
│  │  ┌────────┐  ┌──────────┐  ┌────────────┐           │   │
│  │  │DOM     │◄─│Process   │◄─│Deepgram    │           │   │
│  │  │Builder │  │Response  │  │API Call    │           │   │
│  │  └────────┘  └──────────┘  └────────────┘           │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Purpose | Key Functions |
|-----------|---------|---------------|
| **FastAPI App** | HTTP API server | Request validation, job submission, status queries |
| **AudioProcessor** | Processing orchestrator | Pipeline coordination, progress tracking, error handling |
| **DeepgramClient** | ASR API integration | Transcription, diarization, summarization via API |
| **AudioConverter** | Media manipulation | FFmpeg wrapper for extraction, conversion, splitting |
| **QualityAssessor** | Audio analysis | SNR calculation, silence detection, quality scoring |
| **DOMBuilder** | Output formatting | Map speakers/utterances to Docling SectionItems/TextItems |
| **RQ Worker** | Background processing | Async job execution, retry logic, status updates |

## 3. Data Model

### Core Entities

```python
# AudioFile (Input)
class AudioFile:
    filename: str
    file_hash: str          # SHA-256
    size_bytes: int
    mime_type: str
    format: AudioFormat     # Enum: mp3, wav, m4a, flac, ogg, etc.

# AudioProperties (Metadata)
class AudioProperties:
    duration_ms: int
    sample_rate: int
    channels: int
    bit_depth: int | None
    bitrate_kbps: int | None

# AudioQuality (Assessment)
class AudioQuality:
    snr_db: float                # Signal-to-noise ratio
    silence_ratio: float         # 0.0-1.0
    clipping_ratio: float        # 0.0-1.0
    quality_score: float         # 0.0-1.0 (composite)
    warnings: list[str]

# Speaker (Diarization Result)
class Speaker:
    id: str                      # speaker_0, speaker_1, ...
    label: str                   # Speaker 1, Speaker 2, ...
    duration_ms: int
    utterance_count: int
    word_count: int
    confidence_mean: float

# Utterance (Transcription Segment)
class Utterance:
    id: str
    speaker_id: str
    text: str
    start_ms: int
    end_ms: int
    confidence: float
    words: list[Word]

# Job (Processing State)
class Job:
    job_id: str
    status: JobStatus            # Enum: queued, processing, completed, failed
    progress: JobProgress | None
    source_file: AudioFile
    created_at: datetime
    updated_at: datetime
    error: JobError | None
```

### Relationships

- Job → 1 AudioFile (source)
- AudioFile → 1 AudioProperties (metadata)
- AudioFile → 1 AudioQuality (assessment)
- Job → N Speakers (diarization results)
- Speaker → N Utterances (speech segments)
- Utterance → N Words (word-level transcription)

## 4. API Specification

### Endpoints

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| POST | /api/v1/process | Submit audio/video for processing | No |
| GET | /api/v1/status/{job_id} | Get job status and progress | No |
| GET | /api/v1/results/{job_id} | Get completed results | No |
| GET | /api/v1/artifacts/{job_id}/{name} | Download specific artifact | No |
| POST | /api/v1/cancel/{job_id} | Cancel queued/processing job | No |
| GET | /health | Health check | No |

### Request/Response Format

**POST /api/v1/process** (multipart/form-data):

```json
{
  "file": "<binary>",
  "job_id": "audio_abc123",
  "priority": "normal",
  "options": {
    "language": "en",
    "diarize": true,
    "summarize": true,
    "detect_language": true
  }
}
```

**Response** (202 Accepted):

```json
{
  "job_id": "audio_abc123",
  "status": "queued",
  "created_at": "2025-12-04T10:30:00Z",
  "status_url": "/api/v1/status/audio_abc123"
}
```

**GET /api/v1/results/{job_id}** (200 OK):

```json
{
  "job_id": "audio_abc123",
  "status": "completed",
  "processing": {
    "duration_seconds": 390,
    "deepgram_cost_usd": 0.348
  },
  "transcription": {
    "language": "en",
    "word_count": 8500,
    "speaker_count": 3
  },
  "outputs": {
    "docling_dom_url": "/api/v1/artifacts/audio_abc123/docling_dom.json",
    "transcript_txt_url": "/api/v1/artifacts/audio_abc123/transcript.txt"
  }
}
```

## 5. CLI Specification

### Commands

| Command | Purpose | Example |
|---------|---------|---------|
| `audio-processor process` | Process audio file locally | `audio-processor process meeting.mp3` |
| `audio-processor status` | Check job status | `audio-processor status audio_abc123` |
| `audio-processor config` | Show/set configuration | `audio-processor config --show` |

### Arguments

- `--output-dir`: Output directory for results (default: `./outputs`)
- `--quality-threshold`: Minimum quality score (default: 0.5)
- `--skip-quality-check`: Skip audio quality assessment
- `--format`: Output format (json, txt, srt)

## 6. Security

### Authentication

**None (MVP)** - Internal service accessed via Docker network. Future: API key authentication for external access.

### Authorization

**None (MVP)** - Single-tenant deployment. Future: RBAC for multi-tenant scenarios.

### Data Protection

- **At Rest**: Files stored temporarily in `/tmp/audio-processing` (ephemeral, cleaned after processing)
- **In Transit**: TLS for Deepgram API calls (enforced by SDK)
- **Sensitive Data**: API keys stored in environment variables, never logged

### Input Validation

- File type verification (magic bytes, not extension)
- File size limit enforcement (2GB max)
- Duration validation (>1 second minimum)
- Content hash verification for integrity

## 7. Error Handling

### Strategy

**Fail-fast with retry** - Validate early, fail explicitly, retry transient errors, log all failures.

### Error Codes

| Code | Meaning | User Action |
|------|---------|-------------|
| `INVALID_FILE_TYPE` | Unsupported format | Use MP3, WAV, M4A, FLAC, OGG, MP4, MOV |
| `FILE_TOO_LARGE` | Exceeds 2GB limit | Split file or compress |
| `FILE_TOO_SHORT` | < 1 second duration | Provide longer audio |
| `DEEPGRAM_ERROR` | API failure | Retry (automatic) or check API status |
| `DEEPGRAM_TIMEOUT` | Request timeout | Retry with smaller file |
| `QUALITY_TOO_LOW` | Audio quality warning | Review quality report, proceed if acceptable |

### Logging

- **Format**: Structured JSON (structlog)
- **Levels**: DEBUG (development), INFO (production), WARNING, ERROR
- **Sensitive**: Never log API keys, file contents, or user data
- **Correlation**: Include `job_id` in all log entries for traceability

## 8. Performance Requirements

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Processing Speed** | < 0.2x real-time | End-to-end timing for 1-hour test file |
| **API Response Time** | < 200ms (submit), < 50ms (status) | 95th percentile |
| **Throughput** | 10 concurrent jobs | Load testing with varied file sizes |
| **Memory** | < 2GB per worker | Container resource monitoring |
| **Cost** | < $0.50 per hour audio | Deepgram billing + compute costs |

## 9. Testing Strategy

### Coverage Target

- **Minimum**: 80% overall
- **Critical paths**: 100% (Deepgram integration, DOM mapping, quality assessment)

### Test Types

- **Unit**: Component isolation, mock external dependencies
  - DeepgramClient (mock API responses)
  - DOMBuilder (test mapping logic)
  - QualityAssessor (test SNR calculations)
  - AudioConverter (mock FFmpeg calls)

- **Integration**: Real external services
  - Deepgram API with test audio files
  - Redis queue job lifecycle
  - FFmpeg audio extraction from test videos

- **E2E**: Full user workflows
  - Submit audio → process → retrieve results
  - Handle long files (>4 hours, auto-split)
  - Quality warnings on poor audio

## Related Documents

- [Project Vision](./project-vision.md): Overall goals and constraints
- [ADR-001](./adr/adr-001-initial-architecture.md): Deepgram architecture decision
- [Development Roadmap](./roadmap.md): Implementation phases and timeline
