---
schema_type: planning
title: "Phase 1: Core MVP - Detailed Plan"
status: published
owner: core-maintainer
purpose: "Detailed sprint breakdown for Phase 1 Core MVP with 3-4 hour increments."
tags:
  - planning
  - phase_plan
component: Development-Tools
source: "Derived from roadmap.md Phase 1"
---
<!--
SPDX-FileCopyrightText: 2025 Byron Williams <byron@williamshome.family>
SPDX-License-Identifier: CC-BY-4.0
-->

# Phase 1: Core MVP - Detailed Plan

> **Branch**: `feat/phase-1-core-mvp`
> **Duration**: Weeks 2-3 (~88 hours across 22 sprints)
> **Status**: Ready to Start

## Phase Overview

Implement core audio processing pipeline with Deepgram transcription, comprehensive audio preprocessing (signal conditioning, VAD), speaker diarization, quality assessment, and job management.

## Milestones

| Milestone | Sprint(s) | Deliverable |
| --------- | --------- | ----------- |
| M1.1: Audio Preprocessing Pipeline | Sprints 1-6 | Signal conditioning, VAD, quality assessment complete |
| M1.2: Deepgram Integration | Sprints 7-11 | Transcription with diarization working |
| M1.3: Job Management | Sprints 12-16 | Redis Queue with retry logic operational |
| M1.4: Quality & Testing | Sprints 17-22 | Tests passing, error handling robust |

## Sprint Breakdown

### Sprint 1: Audio Signal Conditioning Foundation (4 hours)

**Goal**: Implement core signal processing functions (resampling, mono conversion, RMS normalization).

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Create AudioConditioner service class | 1.0 | Core class with polyphase resampling (librosa) |
| Implement stereo-to-mono conversion | 1.0 | Energy-based channel selection with pydub |
| Implement RMS normalization to -20dBFS | 1.5 | Target level with headroom protection |
| Write unit tests for signal processing | 0.5 | Test resampling accuracy, normalization levels |

**Acceptance Criteria**:

- [ ] Audio resampled to 16kHz using polyphase filters
- [ ] Stereo converted to mono with energy-based channel selection
- [ ] RMS normalization achieves -20dBFS ±1dB
- [ ] Tests pass for various input formats and sample rates

**Deliverable**: AudioConditioner class with signal preprocessing

---

### Sprint 2: Silero VAD Integration (4 hours)

**Goal**: Integrate Silero VAD model for silence removal.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Create VADProcessor service class | 1.0 | Load Silero VAD model (v4.0) |
| Implement speech segment detection | 1.5 | Apply VAD to audio, detect speech boundaries |
| Implement VAD timeline reconstruction | 1.0 | Map VAD segments to original timestamps |
| Write unit tests with synthetic audio | 0.5 | Test silence detection, segment merging |

**Acceptance Criteria**:

- [ ] Silero VAD model loads successfully
- [ ] Speech segments detected with >90% accuracy
- [ ] Timeline reconstruction preserves timestamp accuracy
- [ ] Tests pass for audio with varying silence patterns

**Deliverable**: VADProcessor with silence removal capability

---

### Sprint 3: Audio Quality Assessment (4 hours)

**Goal**: Implement comprehensive audio quality metrics.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Create QualityAssessor service class | 1.0 | Core class with librosa for analysis |
| Implement SNR calculation | 1.0 | Signal-to-noise ratio in dB |
| Implement silence and clipping detection | 1.5 | Detect silence ratio, clipping ratio |
| Calculate composite quality score | 0.5 | Weighted score (0.0-1.0) with warnings |

**Acceptance Criteria**:

- [ ] SNR calculated accurately (±2dB validation)
- [ ] Silence ratio detected (0.0-1.0 scale)
- [ ] Clipping ratio detected (samples > 0.99)
- [ ] Quality score reflects audio usability

**Deliverable**: QualityAssessor with SNR, silence, clipping metrics

---

### Sprint 4: Preprocessing Pipeline Integration (3 hours)

**Goal**: Integrate AudioConditioner, VADProcessor, and QualityAssessor.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Create AudioPreprocessor orchestrator | 1.0 | Coordinate conditioning → VAD → quality |
| Implement preprocessing pipeline flow | 1.0 | Chain components, handle errors |
| Add preprocessing metrics output | 0.5 | VAD removed %, processing time, quality score |
| Write integration tests | 0.5 | Test full preprocessing pipeline |

**Acceptance Criteria**:

- [ ] Pipeline executes: condition → VAD → quality assessment
- [ ] Metrics include VAD removed %, processing time
- [ ] Processing completes in < 10% of audio duration
- [ ] Integration tests pass for varied audio samples

**Deliverable**: Complete audio preprocessing pipeline

---

### Sprint 5: FFmpeg Audio Extraction (4 hours)

**Goal**: Implement FFmpeg wrapper for audio extraction and conversion.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Create AudioConverter service class | 1.5 | ffmpeg-python wrapper for extraction |
| Implement audio extraction from video | 1.5 | Detect video, extract audio track |
| Add format conversion for Deepgram | 0.5 | Convert to 16kHz mono MP3 |
| Write tests with sample video files | 0.5 | Test MP4, MOV, AVI extraction |

**Acceptance Criteria**:

- [ ] FFmpeg detects video files automatically
- [ ] Audio extracted from MP4, MOV, AVI
- [ ] Output converted to 16kHz mono MP3
- [ ] Tests pass for common video formats

**Deliverable**: AudioConverter for video-to-audio extraction

---

### Sprint 6: Long File Splitting Logic (4 hours)

**Goal**: Implement automatic splitting for long files (>4 hours).

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Implement duration detection | 1.0 | Use ffprobe to detect audio duration |
| Implement file splitting with overlap | 2.0 | Split at 4-hour boundaries with 30s overlap |
| Add segment metadata tracking | 0.5 | Track segment timestamps, sequence |
| Write tests for long file handling | 0.5 | Test splitting, overlap, reassembly |

**Acceptance Criteria**:

- [ ] Files >4 hours automatically split
- [ ] Segments include 30s overlap for context
- [ ] Segment metadata tracks original timestamps
- [ ] Tests validate splitting and reassembly

**Deliverable**: Long file splitting with overlap

---

### Sprint 7: Deepgram Client Foundation (4 hours)

**Goal**: Create Deepgram API client with configuration.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Create DeepgramClient service class | 1.5 | Initialize SDK, configure API key |
| Configure Nova-2 model options | 1.0 | Model, diarization, smart_format, summarization |
| Implement API timeout and retries | 1.0 | 120s timeout, exponential backoff (3 retries) |
| Write unit tests with mocked responses | 0.5 | Test client initialization, config |

**Acceptance Criteria**:

- [ ] Deepgram SDK initializes with API key
- [ ] Nova-2 model configured correctly
- [ ] Timeout set to 120s with 3 retries
- [ ] Tests pass with mocked API responses

**Deliverable**: Configured DeepgramClient

---

### Sprint 8: Deepgram API Call Implementation (4 hours)

**Goal**: Implement transcription API call with diarization.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Implement transcribe_audio method | 2.0 | Call Deepgram API with preprocessed audio |
| Add diarization options | 0.5 | Enable speaker diarization, smart_format |
| Add summarization options | 0.5 | Enable summarization if requested |
| Handle API response and errors | 1.0 | Parse response, handle API failures |

**Acceptance Criteria**:

- [ ] API call includes Nova-2, diarization, smart_format
- [ ] Summarization enabled via optional flag
- [ ] API errors captured and logged
- [ ] Response JSON returned successfully

**Deliverable**: Working Deepgram transcription call

---

### Sprint 9: Deepgram Response Parsing (4 hours)

**Goal**: Parse Deepgram JSON into Speaker, Utterance, Word models.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Create response parsing module | 1.5 | Extract speakers, utterances, words from JSON |
| Map to Speaker model | 1.0 | Parse speaker_id, duration, word_count |
| Map to Utterance and Word models | 1.0 | Parse text, timestamps, confidence |
| Write unit tests for parsing | 0.5 | Test with sample Deepgram responses |

**Acceptance Criteria**:

- [ ] Speaker model includes id, label, duration, stats
- [ ] Utterance model includes text, timestamps, speaker_id
- [ ] Word model includes text, timestamps, confidence
- [ ] Tests pass for varied Deepgram responses

**Deliverable**: Deepgram response parser

---

### Sprint 10: Deepgram Retry Logic (3 hours)

**Goal**: Implement exponential backoff for transient errors.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Implement retry decorator | 1.0 | Exponential backoff (1s, 2s, 4s) |
| Classify retryable vs. fatal errors | 1.0 | 5xx → retry, 4xx → fail immediately |
| Add retry logging | 0.5 | Log retry attempts, final failure |
| Write integration tests | 0.5 | Test retry behavior with mocked failures |

**Acceptance Criteria**:

- [ ] 5xx errors trigger retry with backoff
- [ ] 4xx errors fail immediately
- [ ] Maximum 3 retries before final failure
- [ ] Tests validate retry behavior

**Deliverable**: Robust retry logic for Deepgram API

---

### Sprint 11: Deepgram Integration Testing (3 hours)

**Goal**: Test Deepgram integration with real API.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Create integration test suite | 1.0 | Test with real Deepgram API |
| Test with sample audio files | 1.0 | Varied durations, speakers, quality |
| Validate WER < 3% on test audio | 0.5 | Measure accuracy against ground truth |
| Document API usage and costs | 0.5 | Track billing, document cost per minute |

**Acceptance Criteria**:

- [ ] Integration tests pass with real API
- [ ] WER < 3% on clean test audio
- [ ] Speaker diarization correctly identifies speakers
- [ ] Cost tracking shows < $0.50/hour

**Deliverable**: Validated Deepgram integration

---

### Sprint 12: FastAPI Application Setup (4 hours)

**Goal**: Create FastAPI application with basic endpoints.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Create FastAPI app with ASGI server | 1.5 | Basic app, uvicorn configuration |
| Implement /health endpoint | 0.5 | Health check for monitoring |
| Create request/response models | 1.0 | Pydantic models for API contracts |
| Write API documentation | 1.0 | OpenAPI docs, endpoint descriptions |

**Acceptance Criteria**:

- [ ] FastAPI app starts on port 8000
- [ ] /health endpoint returns 200 OK
- [ ] Pydantic models validate requests/responses
- [ ] OpenAPI docs accessible at /docs

**Deliverable**: FastAPI application foundation

---

### Sprint 13: File Upload Endpoint (4 hours)

**Goal**: Implement POST /api/v1/process endpoint.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Create /process endpoint | 1.5 | Accept multipart file uploads |
| Implement file validation | 1.5 | Type, size, duration checks |
| Add job_id generation | 0.5 | UUID-based job IDs |
| Write endpoint tests | 0.5 | Test upload, validation, job creation |

**Acceptance Criteria**:

- [ ] Endpoint accepts MP3, WAV, M4A, FLAC, OGG, MP4, MOV
- [ ] File size limited to 2GB
- [ ] Duration validated (>1 second)
- [ ] Returns 202 Accepted with job_id

**Deliverable**: Working file upload endpoint

---

### Sprint 14: Redis Queue Integration (4 hours)

**Goal**: Integrate Redis Queue for job management.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Configure Redis connection | 1.0 | Connect to Redis, configure RQ |
| Create RQ worker process | 1.5 | Worker consumes jobs from queue |
| Implement job submission | 1.0 | Queue jobs from /process endpoint |
| Write queue integration tests | 0.5 | Test job submission, consumption |

**Acceptance Criteria**:

- [ ] Redis connection established
- [ ] RQ worker consumes jobs successfully
- [ ] Jobs queued from /process endpoint
- [ ] Tests validate queue behavior

**Deliverable**: Redis Queue job management

---

### Sprint 15: Job Status Tracking (3 hours)

**Goal**: Implement GET /api/v1/status endpoint.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Create /status endpoint | 1.0 | Return job status and progress |
| Implement progress tracking | 1.0 | Track stage, percent complete |
| Store status updates in Redis | 0.5 | Update status as job progresses |
| Write status endpoint tests | 0.5 | Test status retrieval, updates |

**Acceptance Criteria**:

- [ ] Endpoint returns job status (queued, processing, completed, failed)
- [ ] Progress includes stage and percent complete
- [ ] Status updates in real-time
- [ ] Tests validate status tracking

**Deliverable**: Job status tracking endpoint

---

### Sprint 16: AudioProcessor Orchestrator (4 hours)

**Goal**: Create orchestrator to coordinate preprocessing, Deepgram, and result storage.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Create AudioProcessor orchestrator | 1.5 | Coordinate all processing steps |
| Implement processing pipeline | 1.5 | Preprocess → Deepgram → store results |
| Add progress callbacks | 0.5 | Update job status at each stage |
| Write orchestration tests | 0.5 | Test full processing flow |

**Acceptance Criteria**:

- [ ] Orchestrator coordinates: validate → preprocess → quality → Deepgram
- [ ] Progress updated at each stage
- [ ] Results stored in Redis
- [ ] Tests validate full pipeline

**Deliverable**: AudioProcessor orchestrator

---

### Sprint 17: Error Handling & Logging (4 hours)

**Goal**: Implement comprehensive error handling and structured logging.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Create custom exception hierarchy | 1.0 | ValidationError, APIError, ProcessingError |
| Implement structured logging | 1.5 | JSON logs with job_id correlation |
| Add error recovery logic | 1.0 | Retry transient errors, fail gracefully |
| Write error handling tests | 0.5 | Test error scenarios, recovery |

**Acceptance Criteria**:

- [ ] Custom exceptions for all error types
- [ ] Logs structured as JSON with job_id
- [ ] Transient errors trigger retry
- [ ] Fatal errors logged and reported

**Deliverable**: Robust error handling and logging

---

### Sprint 18: Unit Test Coverage (4 hours)

**Goal**: Achieve 80% unit test coverage for core components.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Write tests for AudioConditioner | 1.0 | Test resampling, normalization, mono conversion |
| Write tests for QualityAssessor | 1.0 | Test SNR, silence, clipping calculations |
| Write tests for DeepgramClient | 1.0 | Mock API, test parsing, retries |
| Write tests for AudioConverter | 1.0 | Mock FFmpeg, test extraction, splitting |

**Acceptance Criteria**:

- [ ] AudioConditioner tests cover all signal processing
- [ ] QualityAssessor tests validate metrics
- [ ] DeepgramClient tests cover API and parsing
- [ ] AudioConverter tests validate FFmpeg calls

**Deliverable**: 80% unit test coverage

---

### Sprint 19: Integration Test Suite (4 hours)

**Goal**: Create integration tests for full workflows.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Create end-to-end test suite | 1.5 | Test submit → process → retrieve |
| Test with varied audio samples | 1.5 | Different durations, quality, speakers |
| Test error scenarios | 0.5 | Invalid files, API failures |
| Document test coverage | 0.5 | Coverage report, gaps analysis |

**Acceptance Criteria**:

- [ ] E2E tests cover full workflows
- [ ] Tests validate with varied audio
- [ ] Error scenarios tested
- [ ] Coverage documented

**Deliverable**: Comprehensive integration tests

---

### Sprint 20: Performance Validation (3 hours)

**Goal**: Validate processing speed meets < 0.2x real-time target.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Create performance test suite | 1.0 | Time end-to-end processing |
| Test with 1-hour audio file | 1.0 | Measure total processing time |
| Optimize bottlenecks | 0.5 | Profile and optimize slow components |
| Document performance results | 0.5 | Timing breakdown by stage |

**Acceptance Criteria**:

- [ ] 1-hour audio processes in < 12 minutes
- [ ] Performance tests pass consistently
- [ ] Bottlenecks identified and documented
- [ ] Results meet target < 0.2x real-time

**Deliverable**: Performance validation report

---

### Sprint 21: Cost Tracking & Metrics (3 hours)

**Goal**: Implement Deepgram cost tracking and processing metrics.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Calculate Deepgram cost per job | 1.0 | Track API usage, calculate cost |
| Add metrics to job results | 1.0 | Include duration, cost, quality score |
| Create cost reporting | 0.5 | Log cost per job, aggregate stats |
| Write cost tracking tests | 0.5 | Validate cost calculations |

**Acceptance Criteria**:

- [ ] Cost calculated per job (Nova-2 rates)
- [ ] Metrics include duration, cost, quality
- [ ] Cost tracking logged
- [ ] Tests validate cost accuracy

**Deliverable**: Cost tracking and metrics

---

### Sprint 22: Phase 1 Documentation (4 hours)

**Goal**: Document Phase 1 implementation and usage.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Write API usage guide | 1.5 | Document endpoints, request/response |
| Document preprocessing pipeline | 1.0 | Explain signal conditioning, VAD, quality |
| Create troubleshooting guide | 1.0 | Common issues, solutions |
| Update README with Phase 1 features | 0.5 | Installation, configuration, usage |

**Acceptance Criteria**:

- [ ] API guide covers all endpoints
- [ ] Preprocessing pipeline documented
- [ ] Troubleshooting covers common issues
- [ ] README updated with features

**Deliverable**: Complete Phase 1 documentation

---

## Phase Completion Checklist

- [ ] All 22 sprints completed
- [ ] All milestone deliverables ready
- [ ] Audio preprocessing pipeline operational (M1.1)
- [ ] Deepgram integration working (M1.2)
- [ ] Job management with Redis Queue functional (M1.3)
- [ ] Test coverage ≥ 80% (M1.4)
- [ ] Performance meets < 0.2x real-time target
- [ ] Cost tracking shows < $0.50/hour
- [ ] PR created and merged

## Related Documents

- [Main PROJECT-PLAN](../PROJECT-PLAN.md)
- [Roadmap Phase 1](../roadmap.md#phase-1-core-mvp-weeks-2-3)
- [Tech Spec - Architecture](../tech-spec.md#2-architecture)
- [Tech Spec - Audio Processing Stack](../tech-spec.md#audio-processing-stack)
- [ADR-001: Initial Architecture](../adr/adr-001-initial-architecture.md)
- [ADR-002: Audio Preprocessing Pipeline](../adr/adr-002-audio-preprocessing-pipeline.md)
- [Previous: Phase 0 Foundation](./phase-0-foundation.md)
- [Next: Phase 2 Integration](./phase-2-integration.md)
