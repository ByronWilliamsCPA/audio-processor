---
schema_type: planning
title: "Audio Processor - Project Plan"
status: published
owner: core-maintainer
purpose: "Provide unified development plan with git branch strategy."
tags:
  - planning
component: Strategy
source: "Synthesized from planning documents"
---
<!--
SPDX-FileCopyrightText: 2025 Byron Williams <byron@williamshome.family>
SPDX-License-Identifier: CC-BY-4.0
-->

> **Generated**: 2025-12-04
> **Status**: Ready for Development
> **Timeline**: 4 weeks across 4 phases

## Executive Summary

Audio Processor is a Deepgram-powered audio transcription pipeline that converts audio/video files into structured, RAG-ready content. It provides high-accuracy speech-to-text (6-9% WER), native speaker diarization, and automatic summarization, outputting unified Docling DOM format for seamless integration with the existing image_detection RAG pipeline.

**Key Value**: Transform spoken content into searchable, attributable text chunks that integrate seamlessly with existing document processing pipelines, enabling unified semantic search across all content types.

**Target**: Production-ready MVP in 4 weeks with < 10% WER, < $0.50/hour cost, < 1 minute processing time per hour of audio.

## Project Scope

### In Scope (MVP)

- ✅ **Audio/Video Ingestion**: All major formats (MP3, WAV, M4A, FLAC, MP4, MOV) with FFmpeg extraction
- ✅ **Audio Preprocessing**: 16kHz resampling, RMS normalization, VAD silence removal (librosa, pydub, Silero)
- ✅ **Deepgram Processing**: Nova-2 transcription + native diarization + v2 summarization (single API call)
- ✅ **Quality Assessment**: SNR, silence ratio, clipping detection with user warnings
- ✅ **Docling DOM Output**: Speaker-centric structure (SectionItems + TextItems) for pipeline compatibility
- ✅ **Job Management**: Async processing via Redis Queue with status tracking and retry logic
- ✅ **Playback URLs**: Media Fragment URIs for timestamp-based playback links

### Out of Scope

- ❌ **Real-time Streaming**: Batch processing only
- ❌ **Speaker Identification**: Anonymous labels only (no name matching)
- ❌ **Audio Enhancement**: No noise reduction or cleanup
- ❌ **Translation**: Single-language output only
- 🔄 **Local Whisper**: Deferred to Phase 2 for air-gapped/sensitive content

## Git Branch Strategy

This project follows semantic release with phase-based feature branches:

| Phase | Branch | Type | Commits | Version Impact |
| ----- | ------ | ---- | ------- | -------------- |
| **Phase 0** | `feat/phase-0-foundation` | feat | Foundation setup commits | Minor (0.1.0) |
| **Phase 1** | `feat/phase-1-core-mvp` | feat | Core processing commits | Minor (0.2.0) |
| **Phase 2** | `feat/phase-2-integration` | feat | Integration commits | Minor (0.3.0) |
| **Phase 3** | `feat/phase-3-polish` | feat | Polish & deploy commits | Minor (0.4.0) |

**Branch Workflow**:

```bash
# Start a phase
git checkout main && git pull
git checkout -b feat/phase-{N}-{name}

# Work on phase with conventional commits
git commit -m "feat: implement {feature}"
git commit -m "test: add tests for {component}"
git commit -m "docs: document {feature}"

# Complete phase - create PR
git push -u origin feat/phase-{N}-{name}
gh pr create --title "feat: Phase {N} - {Name}" --body "..."

# After PR merge, start next phase
git checkout main && git pull
git checkout -b feat/phase-{N+1}-{name}
```

## Phased Development Plan

### Phase 0: Foundation (Week 1)

**Branch**: `feat/phase-0-foundation`
**Duration**: 1 week (~14 hours across 4 sprints)
**Dependencies**: None

**📋 [Detailed Phase Plan](./phases/phase-0-foundation.md)** - Sprint-by-sprint breakdown

**Objective**: Establish development environment, project structure, and CI/CD pipeline.

**Deliverables**:

- [ ] UV package manager configured with all dependencies (Deepgram, FastAPI, Redis, librosa, pydub, silero-vad, ffmpeg-python, soundfile)
- [ ] Pre-commit hooks installed (Ruff, BasedPyright, Bandit, markdownlint)
- [ ] GitHub Actions CI/CD workflows verified
- [ ] Docker Compose development environment (app + Redis + worker)
- [ ] Project structure validated

**Success Criteria**:

- ✅ `uv sync --all-extras` completes in < 5 minutes
- ✅ CI pipeline passes on main branch
- ✅ Pre-commit hooks prevent linting/type errors
- ✅ `docker-compose up` brings up development stack

**Tasks**:

| Task | Est. Hours |
| ---- | ---------- |
| Configure UV with pyproject.toml dependencies | 2 |
| Add Deepgram SDK, FastAPI, Redis, librosa, FFmpeg deps | 2 |
| Set up pre-commit hooks (Ruff, BasedPyright, Bandit) | 2 |
| Verify GitHub Actions CI workflows | 3 |
| Configure Docker Compose (app + Redis + worker) | 3 |
| Write development setup guide | 2 |

**Start Phase**:

```bash
git checkout -b feat/phase-0-foundation
```

---

### Phase 1: Core MVP (Weeks 2-3)

**Branch**: `feat/phase-1-core-mvp`
**Duration**: 2 weeks (~88 hours across 22 sprints)
**Dependencies**: Phase 0 complete

**📋 [Detailed Phase Plan](./phases/phase-1-core-mvp.md)** - Sprint-by-sprint breakdown

**Objective**: Implement core audio processing pipeline with Deepgram transcription, preprocessing, and job management.

**Deliverables**:

- [ ] FastAPI endpoints (POST /process, GET /status, GET /results)
- [ ] Audio preprocessing pipeline (AudioConditioner, VADProcessor, QualityAssessor)
- [ ] Deepgram API integration (Nova-2, diarization, summarization)
- [ ] Redis Queue job management with retry logic
- [ ] FFmpeg wrapper for audio extraction and conversion
- [ ] Basic error handling and structured logging

**Success Criteria**:

- ✅ Process 1-hour MP3 file end-to-end successfully
- ✅ Preprocessing improves WER by 10-20% (validated on test set)
- ✅ Speaker diarization correctly identifies speakers
- ✅ Jobs survive API failures with retry logic
- ✅ Processing completes in < 1 minute per hour of audio

**User Stories** (9 total):

1. US-001: Submit Audio for Processing (11 hours)
2. US-002: Transcribe Audio with Deepgram (16 hours)
3. US-003: Extract Audio from Video (15 hours)
4. US-004: Assess Audio Quality (14 hours)
5. US-005: Track Job Status (10 hours)
6. US-009: Audio Signal Conditioning Pipeline (22 hours) ⭐ NEW

**Phase Total**: ~88 hours

---

### Phase 2: Integration & Enhancement (Week 3-4)

**Branch**: `feat/phase-2-integration`
**Duration**: 1-2 weeks (~37 hours across 10 sprints)
**Dependencies**: Phase 1 complete

**📋 [Detailed Phase Plan](./phases/phase-2-integration.md)** - Sprint-by-sprint breakdown

**Objective**: Implement Docling DOM output format and result retrieval endpoints.

**Deliverables**:

- [ ] Docling DOM mapping (Speakers → SectionItems, Utterances → TextItems)
- [ ] GET /api/v1/results endpoint with full job results
- [ ] Artifact download endpoints (Docling DOM, transcript, SRT)
- [ ] Playback URL generation (Media Fragment URIs)
- [ ] Integration tests with downstream pipeline

**Success Criteria**:

- ✅ Docling DOM output validates against schema
- ✅ Downstream pipeline processes audio DOM without changes
- ✅ Results include playback URLs with timestamp fragments
- ✅ All artifact formats (JSON, TXT, SRT) generated correctly

**User Stories** (3 total):

7. US-006: Generate Docling DOM Output (17 hours)
8. US-007: Retrieve Processing Results (9 hours)
9. US-008: Download Artifacts (11 hours)

**Phase Total**: ~37 hours

---

### Phase 3: Polish & Deploy (Week 4)

**Branch**: `feat/phase-3-polish`
**Duration**: 1 week (~30 hours across 8 sprints)
**Dependencies**: Phase 2 complete

**📋 [Detailed Phase Plan](./phases/phase-3-polish.md)** - Sprint-by-sprint breakdown

**Objective**: Achieve production readiness through testing, documentation, and deployment validation.

**Deliverables**:

- [ ] Test coverage ≥ 80% overall, 100% critical paths
- [ ] User documentation (README, API reference)
- [ ] Docker production image optimized
- [ ] Performance validation (< 1 min/hour processing)
- [ ] Security review (Bandit, Safety, dependency audit)
- [ ] Deployment guide for Docker Compose

**Success Criteria**:

- ✅ All tests passing with 80%+ coverage
- ✅ No critical/high security vulnerabilities
- ✅ README covers installation, configuration, usage
- ✅ Performance meets targets on 1-hour test files
- ✅ Docker image < 500MB, starts in < 10s

**Phase Total**: ~30 hours

---

## System Architecture

### Architecture Pattern

**Async Queue-Based Microservice** - FastAPI frontend receives requests, RQ workers process jobs asynchronously, Redis manages state.

### Component Diagram

```text
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
│  │                                                      │   │
│  │  Validate → Condition → VAD → Quality → Deepgram    │   │
│  │      ↓                                        ↓      │   │
│  │  AudioConverter          →          DOMBuilder       │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Responsibility | Phase |
| --------- | -------------- | ----- |
| **AudioConditioner** | 16kHz resampling, mono mixing, RMS normalization | Phase 1 |
| **VADProcessor** | Silero VAD silence removal, timeline reconstruction | Phase 1 |
| **QualityAssessor** | SNR, silence/clipping detection, quality scoring | Phase 1 |
| **DeepgramClient** | Nova-2 transcription, diarization, summarization | Phase 1 |
| **AudioConverter** | FFmpeg audio extraction, format conversion | Phase 1 |
| **DOMBuilder** | Docling DOM mapping (speakers → sections, utterances → text items) | Phase 2 |
| **FastAPI App** | HTTP API server, job submission, status queries | Phase 1-2 |
| **RQ Worker** | Background processing, retry logic, status updates | Phase 1 |

## Technology Stack

### Core

- **Language**: Python 3.12
- **Package Manager**: UV
- **Framework**: FastAPI 0.109+ (async API server)
- **CLI**: Click

### Audio Processing Stack

- **Signal Processing**:
  - librosa 0.10+ (polyphase resampling, SNR calculation)
  - pydub 0.25+ (RMS normalization, format conversion)
  - ffmpeg-python 0.2+ (codec conversion, extraction)
  - soundfile 0.12+ (audio I/O)
- **Voice Activity Detection**: silero-vad 4.0+ (CPU-efficient)
- **ASR Engine**: Deepgram SDK 3.x (Nova-2 model)
- **Queue**: Redis 7.x + RQ 1.x

### Code Quality

- **Linter**: Ruff (PyStrict-aligned)
- **Type Checker**: BasedPyright (strict mode)
- **Testing**: pytest 8.x with pytest-asyncio
- **Security**: Bandit, Safety

## Architecture Decisions

### ADR-001: Deepgram Nova-2 as Primary ASR Engine

**Status**: Accepted
**Date**: 2025-12-04

**Decision**: Use Deepgram Nova-2 API as the exclusive ASR engine with native diarization and summarization.

**Rationale**:

1. **Integrated diarization**: Single API call (vs. two-step Whisper+Pyannote)
2. **Very fast processing**: ~30 seconds per hour of audio
3. **Cost-effective**: $0.35/hour including all features
4. **No GPU required**: Frees resources for other pipeline tasks
5. **Smart formatting**: Automatic entity normalization

**Trade-off**: Accept 6-9% WER (vs. Whisper's 4-5%) for native diarization benefit.

**Data Privacy**: For sensitive content (PII/PHI, legal, HIPAA/GDPR), defer to Phase 2 local Whisper implementation.

[Full ADR](./adr/adr-001-initial-architecture.md)

### ADR-002: Audio Signal Conditioning and Preprocessing Pipeline

**Status**: Accepted
**Date**: 2025-12-04

**Decision**: Implement mandatory audio preprocessing pipeline standardizing all input to 16kHz mono 16-bit PCM with VAD and RMS normalization.

**Preprocessing Steps**:

1. Format detection & validation
2. Codec conversion to WAV PCM
3. Resampling to 16kHz (polyphase filters)
4. Stereo → mono (energy-based selection)
5. RMS normalization to -20dBFS
6. Voice Activity Detection (Silero VAD removes 10-30% silence)
7. Quality assessment (SNR, clipping, silence metrics)

**Expected Benefits**:

- 10-20% WER improvement
- 10-30% cost reduction through VAD
- Hallucination prevention
- Consistent confidence scores

**Overhead**: 30-60 seconds per hour of audio (0.8-2%)

[Full ADR](./adr/adr-002-audio-preprocessing-pipeline.md)

### ADR-003: Docling DOM as Unified Output Format

**Status**: Accepted (documented in draft_ADR.md)

**Decision**: Output transcriptions as Docling Document Object Model for pipeline integration.

**Mapping**:

- Full transcript → DoclingDocument
- Speaker turn → SectionItem (with speaker metadata)
- Utterance → TextItem (with timestamps in metadata)
- Summary → SectionItem (special, marked as summary)

**Benefit**: Enables unified downstream processing - same chunking/embedding logic for audio and document content.

## Success Metrics

| Metric | Target | Measurement |
| ------ | ------ | ----------- |
| **Transcription WER** | < 10% (target 6-9%) | Test set evaluation |
| **Processing Speed** | < 0.02x real-time | 1-hour file in < 1 minute |
| **Preprocessing Overhead** | < 2% | < 1 minute per hour audio |
| **Cost** | < $0.50/hour | Deepgram billing + compute |
| **Diarization Error** | < 10% | Speaker confusion rate |
| **Pipeline Integration** | 100% | Zero downstream code changes |
| **Test Coverage** | ≥ 80% | pytest with coverage |

## Risk Management

| Risk | Probability | Impact | Mitigation | Phase |
| ---- | ----------- | ------ | ---------- | ----- |
| Deepgram WER below target | Low | High | Validate early with test set; add Whisper fallback if needed | Phase 1 |
| Costs exceed $0.50/hour | Low | Medium | Implement cost tracking, VAD optimization | Phase 1 |
| FFmpeg extraction fails | Medium | Medium | Test common formats; document unsupported | Phase 1 |
| Quality assessment overhead | Medium | Low | Cache results; make optional via flag | Phase 1 |
| Docling DOM integration issues | Low | High | Validate against downstream pipeline early | Phase 2 |
| Redis queue failures | Low | Medium | Queue persistence; job recovery | Phase 1 |

## Development Timeline

```text
Week 1: Phase 0 - Foundation
  ├── Configure dependencies (UV, Docker)
  ├── Set up CI/CD and pre-commit hooks
  └── Verify development environment

Week 2-3: Phase 1 - Core MVP
  ├── Implement preprocessing pipeline (AudioConditioner, VAD)
  ├── Integrate Deepgram API (transcription + diarization)
  ├── Build job management (FastAPI + Redis Queue)
  └── Add quality assessment and error handling

Week 3-4: Phase 2 - Integration
  ├── Implement Docling DOM mapping
  ├── Build result retrieval endpoints
  ├── Generate artifacts (DOM, TXT, SRT)
  └── Validate pipeline integration

Week 4: Phase 3 - Polish
  ├── Increase test coverage to 80%+
  ├── Write comprehensive documentation
  ├── Performance and security validation
  └── Production deployment guide
```

## Dependencies & Requirements

### External Services (Critical)

- **Deepgram API**: Nova-2 transcription, diarization, summarization (requires API key)
- **Redis**: Job queue and status storage
- **FFmpeg**: Audio extraction from video, format conversion

### Python Dependencies

```bash
# Core framework
fastapi>=0.109
uvicorn
redis[hiredis]>=5.0
rq>=1.15

# Audio processing
librosa>=0.10
pydub>=0.25
ffmpeg-python>=0.2
soundfile>=0.12
silero-vad>=4.0

# ASR
deepgram-sdk>=3.0

# Data models
pydantic>=2.0
docling-core

# Development
ruff
basedpyright
pytest>=8.0
pytest-asyncio
pytest-cov
```

### System Requirements

- **Python**: 3.12+
- **FFmpeg**: 6.x (system package)
- **Redis**: 7.x (Docker or system service)
- **Memory**: 2GB minimum per worker
- **Storage**: 10MB/min for temporary WAV files

## Security Considerations

### Data Privacy (from ADR-001)

**Use Deepgram** for:

- General business meetings
- Podcasts, public content
- Non-sensitive communications

**Use local Whisper** (Phase 2) for:

- PII/PHI content
- Legal/confidential (attorney-client, NDAs)
- Compliance requirements (HIPAA, GDPR, FedRAMP)
- Sensitive HR discussions

### Input Validation

- File type verification (magic bytes, not extension)
- File size limits (2GB max)
- Duration validation (> 1 second minimum)
- Content hash for integrity

### Secrets Management

- API keys in environment variables
- Never log sensitive data
- TLS for all Deepgram API calls

## Next Steps

### 1. Review This Plan

Validate that the synthesis accurately represents all planning documents.

### 2. Start Phase 0

```bash
# Create Phase 0 branch
git checkout main
git checkout -b feat/phase-0-foundation

# Begin with dependency configuration
# Follow tasks in roadmap.md Phase 0
```

### 3. Track Progress

Use TodoWrite to track phase deliverables and tasks.

### 4. Complete Phases with PRs

```bash
# When phase complete
git push -u origin feat/phase-{N}-{name}

# Create PR
gh pr create \
  --title "feat: Phase {N} - {Name}" \
  --body "Implements Phase {N} deliverables per PROJECT-PLAN.md"

# After merge, start next phase
```

## Document References

- **[Project Vision & Scope](./project-vision.md)**: Problem, solution, scope, metrics
- **[Technical Specification](./tech-spec.md)**: Architecture, APIs, data models
- **[Development Roadmap](./roadmap.md)**: Detailed phases, user stories, tasks
- **[ADR-001: Deepgram Architecture](./adr/adr-001-initial-architecture.md)**: ASR engine decision
- **[ADR-002: Preprocessing Pipeline](./adr/adr-002-audio-preprocessing-pipeline.md)**: Signal conditioning
- **[Template Feedback](../template_feedback.md)**: Cookiecutter issues for upstream fixes

---

**This project plan is ready for development. Start with Phase 0 (Foundation) when ready to begin implementation.**
