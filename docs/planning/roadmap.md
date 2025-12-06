---
title: "Audio Processor - Development Roadmap"
schema_type: planning
status: published
owner: core-maintainer
purpose: "Document the phased implementation plan and milestones."
tags:
  - planning
  - roadmap
component: Strategy
source: "/plan command generation"
---

<!-- markdownlint-disable MD024 - Duplicate headings are intentional for phase structure -->

> **Status**: Active | **Updated**: 2025-12-04

## TL;DR

Build Deepgram-powered audio transcription pipeline in 4 phases over 4 weeks: Phase 0 (foundation), Phase 1 (core processing), Phase 2 (integration & enhancement), Phase 3 (polish & deploy). Target: production-ready MVP with < 3% WER, < $0.50/hour cost.

## Timeline Overview

```text
Phase 0: Foundation    ████████░░░░░░░░░░░░░░ (Week 1)    - Dev environment, CI/CD
Phase 1: Core MVP      ░░░░░░░░████████████░░░░ (Week 2-3) - Deepgram, processing
Phase 2: Integration   ░░░░░░░░░░░░░░░░████████ (Week 3-4) - Docling DOM, pipeline
Phase 3: Polish        ░░░░░░░░░░░░░░░░░░░░████ (Week 4)   - Testing, docs, deploy
```

## Milestones

| Milestone | Target | Status | Dependencies |
| ----------- | -------- | -------- | -------------- |
| M0: Dev Environment Ready | Week 1 End | ⏸️ Planned | None |
| M1: Deepgram Integration Working | Week 2 Mid | ⏸️ Planned | M0 |
| M2: Basic Processing Pipeline | Week 2 End | ⏸️ Planned | M1 |
| M3: Docling DOM Output | Week 3 Mid | ⏸️ Planned | M2 |
| M4: Quality Assessment | Week 3 End | ⏸️ Planned | M3 |
| M5: MVP Complete | Week 4 Mid | ⏸️ Planned | M4 |
| M6: Production Ready | Week 4 End | ⏸️ Planned | M5 |

---

## Phase 0: Foundation (Week 1)

### Objective

Establish development environment, project structure, and CI/CD pipeline for efficient development.

### Deliverables

- [ ] UV package manager configured with all dependencies
- [ ] Pre-commit hooks (Ruff, BasedPyright, security checks)
- [ ] GitHub Actions CI/CD (linting, type checking, testing)
- [ ] Docker development environment with Redis
- [ ] Project structure following cookiecutter template standards

### Success Criteria

- ✅ Clone → `uv sync --all-extras` → run locally in < 5 minutes
- ✅ CI pipeline passes on main branch
- ✅ Pre-commit hooks prevent commits with linting errors
- ✅ Docker Compose brings up development stack successfully

### Tasks

| Task | Est. Hours | Status |
| ------ | ------------ | -------- |
| Configure UV with pyproject.toml dependencies | 2 | ⏸️ |
| Add Deepgram SDK, FastAPI, Redis, librosa, FFmpeg deps | 2 | ⏸️ |
| Set up pre-commit hooks (Ruff, BasedPyright, Bandit) | 2 | ⏸️ |
| Create GitHub Actions CI workflow | 3 | ⏸️ |
| Configure Docker Compose (app + Redis + worker) | 3 | ⏸️ |
| Write development setup guide | 2 | ⏸️ |
| **Phase Total** | **14** | ⏸️ |

---

## Phase 1: Core MVP (Weeks 2-3)

### Objective

Implement core audio processing pipeline with Deepgram transcription, speaker diarization, and job management.

### Deliverables

- [ ] FastAPI endpoints (POST /process, GET /status, GET /results)
- [ ] Deepgram API integration (Nova-2, diarization, summarization)
- [ ] Redis Queue job management with retry logic
- [ ] FFmpeg wrapper for audio extraction and conversion
- [ ] Audio quality assessment (SNR, silence, clipping)
- [ ] Basic error handling and logging

### Success Criteria

- ✅ Process 1-hour MP3 file end-to-end successfully
- ✅ Transcription achieves < 3% WER on test audio
- ✅ Speaker diarization correctly identifies speakers
- ✅ Jobs survive API failures with retry logic
- ✅ Processing completes in < 0.2x real-time

### User Stories

#### US-001: Submit Audio for Processing

**As a** user
**I want** to submit an audio file via API
**So that** it gets transcribed and processed asynchronously

**Acceptance Criteria**:

- [ ] POST /api/v1/process accepts MP3, WAV, M4A, FLAC files
- [ ] Endpoint validates file type, size, duration
- [ ] Returns 202 Accepted with job_id and status_url
- [ ] Job is queued in Redis for background processing

**Tasks**:

| Task | Est. Hours | Status |
| ------ | ------------ | -------- |
| Create FastAPI app with /process endpoint | 4 | ⏸️ |
| Implement file upload validation | 2 | ⏸️ |
| Integrate Redis Queue job submission | 3 | ⏸️ |
| Write unit tests for endpoint | 2 | ⏸️ |

#### US-002: Transcribe Audio with Deepgram

**As a** background worker
**I want** to send audio to Deepgram Nova-2 API
**So that** I get accurate transcription with speaker diarization

**Acceptance Criteria**:

- [ ] Deepgram client configured with API key and timeouts
- [ ] API call includes Nova-2, diarization, smart_format, summarization
- [ ] Response parsed into Speaker, Utterance, Word models
- [ ] API failures trigger retry with exponential backoff

**Tasks**:

| Task | Est. Hours | Status |
| ------ | ------------ | -------- |
| Create DeepgramClient service class | 4 | ⏸️ |
| Implement API call with proper options | 3 | ⏸️ |
| Parse Deepgram JSON response into models | 4 | ⏸️ |
| Add retry logic for transient errors | 2 | ⏸️ |
| Write integration tests with real API | 3 | ⏸️ |

#### US-003: Extract Audio from Video

**As a** processing pipeline
**I want** to extract audio from video files
**So that** users can submit MP4/MOV/AVI files directly

**Acceptance Criteria**:

- [ ] FFmpeg detects video files and extracts audio track
- [ ] Audio converted to 16kHz mono MP3 for Deepgram
- [ ] Long files (>4 hours) automatically split with overlap
- [ ] Extracted files cleaned up after processing

**Tasks**:

| Task | Est. Hours | Status |
| ------ | ------------ | -------- |
| Create AudioConverter wrapper for FFmpeg | 4 | ⏸️ |
| Implement audio extraction from video | 3 | ⏸️ |
| Add format conversion (optimal for Deepgram) | 2 | ⏸️ |
| Implement long file splitting logic | 4 | ⏸️ |
| Write tests with sample video files | 2 | ⏸️ |

#### US-004: Assess Audio Quality

**As a** processing pipeline
**I want** to analyze audio quality before transcription
**So that** users are warned about potential low-quality results

**Acceptance Criteria**:

- [ ] Calculate SNR (signal-to-noise ratio) in dB
- [ ] Detect silence ratio (percentage of silent audio)
- [ ] Detect clipping ratio (percentage of clipped samples)
- [ ] Generate composite quality score (0.0-1.0)
- [ ] Attach warnings to job results if quality is low

**Tasks**:

| Task | Est. Hours | Status |
| ------ | ------------ | -------- |
| Create QualityAssessor service using librosa | 5 | ⏸️ |
| Implement SNR calculation | 2 | ⏸️ |
| Implement silence and clipping detection | 3 | ⏸️ |
| Calculate composite quality score | 2 | ⏸️ |
| Write tests with synthetic audio samples | 2 | ⏸️ |

#### US-005: Track Job Status

**As a** user
**I want** to check processing status via API
**So that** I know when results are ready

**Acceptance Criteria**:

- [ ] GET /api/v1/status/{job_id} returns current status
- [ ] Response includes progress (stage, percent complete)
- [ ] Status updates in real-time as job progresses
- [ ] Completed jobs return processing time and cost

**Tasks**:

| Task | Est. Hours | Status |
| ------ | ------------ | -------- |
| Implement /status endpoint | 3 | ⏸️ |
| Add progress tracking in worker | 3 | ⏸️ |
| Store status updates in Redis | 2 | ⏸️ |
| Write tests for status tracking | 2 | ⏸️ |

#### US-009: Audio Signal Conditioning Pipeline

**As a** processing pipeline
**I want** to standardize all audio to optimal ASR parameters
**So that** transcription accuracy is maximized and API costs are minimized

**Acceptance Criteria**:

- [ ] Resample all audio to 16kHz using polyphase filters
- [ ] Convert stereo to mono with energy-based channel selection
- [ ] Apply RMS normalization to -20dBFS target
- [ ] Implement Silero VAD to remove silence segments
- [ ] Processing completes in < 10% of audio duration

**Tasks**:

| Task | Est. Hours | Status |
| ------ | ------------ | -------- |
| Create AudioConditioner service (resampling, mono mix, RMS) | 6 | ⏸️ |
| Integrate Silero VAD model for silence removal | 4 | ⏸️ |
| Implement VAD timeline reconstruction | 3 | ⏸️ |
| Add preprocessing metrics (VAD removed %, processing time) | 2 | ⏸️ |
| Write unit tests for signal processing | 4 | ⏸️ |
| Validate WER improvement with preprocessed audio | 3 | ⏸️ |

### Dependencies

- Requires: Phase 0 complete
- Blocks: Phase 2

---

## Phase 2: Integration & Enhancement (Week 3-4)

### Objective

Implement Docling DOM output format for pipeline integration and add result retrieval endpoints.

### Deliverables

- [ ] Docling DOM mapping (Speakers → SectionItems, Utterances → TextItems)
- [ ] GET /api/v1/results endpoint with full job results
- [ ] Artifact download endpoints (Docling DOM, transcript, SRT)
- [ ] Playback URL generation (Media Fragment URIs)
- [ ] Integration tests with downstream pipeline

### Success Criteria

- ✅ Docling DOM output validates against schema
- ✅ Downstream pipeline processes audio DOM without changes
- ✅ Results include playback URLs with timestamp fragments
- ✅ All artifact formats (JSON, TXT, SRT) generated correctly

### User Stories

#### US-006: Generate Docling DOM Output

**As a** processing pipeline
**I want** to convert transcription to Docling DOM format
**So that** downstream pipeline can process audio like documents

**Acceptance Criteria**:

- [ ] Speakers mapped to SectionItems with speaker metadata
- [ ] Utterances mapped to TextItems with timestamps in meta
- [ ] Summary section included if available
- [ ] Playback URLs generated with Media Fragment syntax
- [ ] Output validates as valid Docling DOM

**Tasks**:

| Task | Est. Hours | Status |
| ------ | ------------ | -------- |
| Create DOMBuilder service class | 4 | ⏸️ |
| Implement speaker → SectionItem mapping | 3 | ⏸️ |
| Implement utterance → TextItem mapping | 3 | ⏸️ |
| Add timestamp metadata and playback URLs | 2 | ⏸️ |
| Validate output against Docling schema | 2 | ⏸️ |
| Write unit tests for DOM mapping | 3 | ⏸️ |

#### US-007: Retrieve Processing Results

**As a** user
**I want** to fetch complete job results via API
**So that** I can access transcription, speakers, and metadata

**Acceptance Criteria**:

- [ ] GET /api/v1/results/{job_id} returns complete results
- [ ] Response includes transcription metadata, speakers, summary
- [ ] Links provided to downloadable artifacts
- [ ] Results cached for 24 hours after completion

**Tasks**:

| Task | Est. Hours | Status |
| ------ | ------------ | -------- |
| Implement /results endpoint | 3 | ⏸️ |
| Build comprehensive result response model | 2 | ⏸️ |
| Add result caching in Redis | 2 | ⏸️ |
| Write integration tests | 2 | ⏸️ |

#### US-008: Download Artifacts

**As a** user
**I want** to download specific output formats
**So that** I can use results in different systems

**Acceptance Criteria**:

- [ ] GET /api/v1/artifacts/{job_id}/docling_dom.json
- [ ] GET /api/v1/artifacts/{job_id}/transcript.txt (plain text)
- [ ] GET /api/v1/artifacts/{job_id}/transcript.srt (subtitles)
- [ ] Proper Content-Type headers for each format

**Tasks**:

| Task | Est. Hours | Status |
| ------ | ------------ | -------- |
| Implement /artifacts endpoint | 3 | ⏸️ |
| Generate plain text transcript | 2 | ⏸️ |
| Generate SRT subtitle format | 3 | ⏸️ |
| Add Content-Type headers | 1 | ⏸️ |
| Write download tests | 2 | ⏸️ |

### Dependencies

- Requires: Phase 1 complete
- Blocks: Phase 3

---

## Phase 3: Polish & Deploy (Week 4)

### Objective

Achieve production readiness through testing, documentation, and deployment configuration.

### Deliverables

- [ ] Test coverage ≥ 80% overall, 100% critical paths
- [ ] User documentation (README, API reference)
- [ ] Docker production image optimized
- [ ] Performance validation (< 0.2x real-time processing)
- [ ] Security review (Bandit, Safety, dependency audit)
- [ ] Deployment guide for Docker Compose

### Success Criteria

- ✅ All tests passing with 80%+ coverage
- ✅ No critical/high security vulnerabilities
- ✅ README covers installation, configuration, usage
- ✅ Performance meets targets on 1-hour test files
- ✅ Docker image < 500MB, starts in < 10s

### Tasks

| Task | Est. Hours | Status |
| ------ | ------------ | -------- |
| Increase test coverage to 80% | 6 | ⏸️ |
| Write E2E tests for complete workflows | 4 | ⏸️ |
| Write comprehensive README | 4 | ⏸️ |
| Create API reference documentation | 3 | ⏸️ |
| Optimize Docker image (multi-stage build) | 2 | ⏸️ |
| Performance testing with varied audio | 3 | ⏸️ |
| Run Bandit and Safety security scans | 1 | ⏸️ |
| Fix security issues | 3 | ⏸️ |
| Write deployment guide | 2 | ⏸️ |
| Validate Deepgram cost tracking | 2 | ⏸️ |
| **Phase Total** | **30** | ⏸️ |

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
| ------ | ------------- | -------- | ------------ |
| Deepgram API accuracy below 3% WER target | Low | High | Test with diverse audio samples early; add Whisper fallback if needed |
| Deepgram costs exceed $0.50/hour | Low | Medium | Monitor billing closely; implement cost tracking and alerts |
| FFmpeg extraction fails on some video formats | Medium | Medium | Test with common formats (MP4, MOV, AVI); document unsupported formats |
| Quality assessment performance impact | Medium | Low | Cache quality results; make quality check optional via flag |
| Docling DOM integration issues | Low | High | Validate against downstream pipeline early in Phase 2 |
| Redis queue failures lose jobs | Low | Medium | Implement queue persistence; add job recovery mechanism |

## Definition of Done

A feature is complete when:

- [ ] Code reviewed and approved (self-review against standards)
- [ ] Tests written and passing (unit + integration where applicable)
- [ ] Documentation updated (docstrings, README if user-facing)
- [ ] No linting errors (Ruff passes)
- [ ] No type errors (BasedPyright strict mode passes)
- [ ] No security issues (Bandit and Safety pass)
- [ ] Merged to main branch with signed commit

## Related Documents

- [Project Vision](./project-vision.md): Overall goals and success metrics
- [Technical Spec](./tech-spec.md): Detailed architecture and API design
- [ADR-001](./adr/adr-001-initial-architecture.md): Key architectural decisions
