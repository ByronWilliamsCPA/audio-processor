---
schema_type: planning
title: "Phase 2: Integration - Detailed Plan"
status: published
owner: core-maintainer
purpose: "Detailed sprint breakdown for Phase 2 Integration with 3-4 hour increments."
tags:
  - planning
component: Development-Tools
source: "Derived from roadmap.md Phase 2"
---
<!--
SPDX-FileCopyrightText: 2025 Byron Williams <byron@williamshome.family>
SPDX-License-Identifier: CC-BY-4.0
-->


> **Branch**: `feat/phase-2-integration`
> **Duration**: Weeks 3-4 (~37 hours across 10 sprints)
> **Status**: Ready to Start

## Phase Overview

Implement Docling DOM output format for pipeline integration, add result retrieval endpoints, artifact generation, and validate integration with downstream systems.

## Milestones

| Milestone | Sprint(s) | Deliverable |
| --------- | --------- | ----------- |
| M2.1: Docling DOM Mapping | Sprints 1-4 | Speaker/Utterance → SectionItem/TextItem mapping complete |
| M2.2: Results API | Sprints 5-6 | GET /results endpoint returning metadata, speakers, summary, and artifact links |
| M2.3: Artifact Generation | Sprints 7-8 | Multiple output formats (JSON, TXT, SRT) |
| M2.4: Integration Testing | Sprints 9-10 | Downstream pipeline validation, E2E tests |

## Sprint Breakdown

### Sprint 1: Docling DOM Foundation (4 hours)

**Goal**: Create DOMBuilder service and understand Docling schema requirements.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Research Docling DOM schema | 1.0 | Study SectionItem, TextItem, meta structure |
| Create DOMBuilder service class | 1.5 | Core class for DOM generation |
| Define DOM data models | 1.0 | Pydantic models for Docling DOM elements |
| Write unit tests for models | 0.5 | Test model validation, serialization |

**Acceptance Criteria**:

- [ ] Docling DOM schema understood and documented
- [ ] DOMBuilder class initialized
- [ ] Pydantic models defined for SectionItem, TextItem
- [ ] Model tests validate schema compliance

**Deliverable**: DOMBuilder foundation with data models

---

### Sprint 2: Speaker to SectionItem Mapping (4 hours)

**Goal**: Map Speaker model to Docling SectionItem with metadata.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Implement speaker → SectionItem mapper | 2.0 | Convert Speaker to SectionItem format |
| Add speaker metadata | 1.0 | Include speaker_id, duration, word_count |
| Add section hierarchy | 0.5 | Group utterances under speaker sections |
| Write unit tests for mapping | 0.5 | Test speaker mapping logic |

**Acceptance Criteria**:

- [ ] Speaker mapped to SectionItem with label
- [ ] Metadata includes speaker_id, duration, stats
- [ ] Utterances grouped under speaker sections
- [ ] Tests validate mapping accuracy

**Deliverable**: Speaker to SectionItem mapping

---

### Sprint 3: Utterance to TextItem Mapping (4 hours)

**Goal**: Map Utterance model to Docling TextItem with timestamps.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Implement utterance → TextItem mapper | 2.0 | Convert Utterance to TextItem format |
| Add timestamp metadata | 1.0 | Include start_ms, end_ms in meta field |
| Add confidence scores | 0.5 | Include confidence in metadata |
| Write unit tests for mapping | 0.5 | Test utterance mapping logic |

**Acceptance Criteria**:

- [ ] Utterance mapped to TextItem with text
- [ ] Metadata includes start_ms, end_ms, confidence
- [ ] TextItems preserve utterance order
- [ ] Tests validate mapping and metadata

**Deliverable**: Utterance to TextItem mapping

---

### Sprint 4: Playback URL Generation (4 hours)

**Goal**: Generate Media Fragment URIs for playback URLs.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Research Media Fragment URI syntax | 1.0 | Understand #t=start,end format |
| Implement URL generator | 1.5 | Generate playback URLs with timestamps |
| Add URLs to TextItem metadata | 1.0 | Include playback_url in meta |
| Write unit tests for URL generation | 0.5 | Test URL format, timestamp accuracy |

**Acceptance Criteria**:

- [ ] Playback URLs use Media Fragment syntax (#t=start,end)
- [ ] URLs generated for each utterance
- [ ] Timestamps match utterance start/end
- [ ] Tests validate URL format and accuracy

**Deliverable**: Playback URL generation

---

### Sprint 5: Docling DOM Validation (3 hours)

**Goal**: Validate generated DOM against Docling schema.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Implement schema validator | 1.5 | Validate DOM output against Docling schema |
| Add validation to DOMBuilder | 0.5 | Validate before returning DOM |
| Create test suite with sample data | 0.5 | Test with varied transcription results |
| Document validation failures | 0.5 | Log validation errors with details |

**Acceptance Criteria**:

- [ ] DOM output validates against Docling schema
- [ ] Validation errors logged with context
- [ ] Tests pass for varied transcription data
- [ ] Invalid DOM raises ValidationError

**Deliverable**: DOM validation against Docling schema

---

### Sprint 6: Results Endpoint Implementation (4 hours)

**Goal**: Implement GET /api/v1/results endpoint with comprehensive output.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Create /results endpoint | 1.5 | Return complete job results |
| Build comprehensive response model | 1.5 | Include metadata, speakers, summary, links |
| Add result caching in Redis | 0.5 | Cache results for 24 hours |
| Write endpoint tests | 0.5 | Test result retrieval, caching |

**Acceptance Criteria**:

- [ ] Endpoint returns job_id, status, processing stats
- [ ] Response includes transcription metadata, speakers
- [ ] Links provided to downloadable artifacts
- [ ] Results cached in Redis for 24 hours

**Deliverable**: GET /results endpoint

---

### Sprint 7: Plain Text Transcript Generation (3 hours)

**Goal**: Generate plain text transcript from transcription results.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Create TextTranscriptGenerator | 1.5 | Convert utterances to plain text |
| Add speaker labels | 0.5 | Prefix utterances with speaker label |
| Add timestamps (optional) | 0.5 | Include timestamps if requested |
| Write generator tests | 0.5 | Test transcript formatting |

**Acceptance Criteria**:

- [ ] Transcript includes speaker labels
- [ ] Utterances formatted as "Speaker 1: [text]"
- [ ] Timestamps optional ([HH:MM:SS] format)
- [ ] Tests validate formatting

**Deliverable**: Plain text transcript generator

---

### Sprint 8: SRT Subtitle Generation (4 hours)

**Goal**: Generate SRT subtitle file from transcription results.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Create SRTGenerator | 2.0 | Convert utterances to SRT format |
| Implement SRT timestamp format | 1.0 | Convert ms to HH:MM:SS,mmm format |
| Add subtitle indexing | 0.5 | Number subtitles sequentially |
| Write SRT generator tests | 0.5 | Test SRT format, timestamps |

**Acceptance Criteria**:

- [ ] SRT format valid (index, timestamps, text, blank line)
- [ ] Timestamps in HH:MM:SS,mmm format
- [ ] Subtitles numbered sequentially
- [ ] Tests validate SRT parsing compatibility

**Deliverable**: SRT subtitle generator

---

### Sprint 9: Artifacts Download Endpoint (4 hours)

**Goal**: Implement GET /api/v1/artifacts endpoint for multiple formats.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Create /artifacts endpoint | 1.5 | Serve downloadable artifacts |
| Add format routing | 1.0 | Route by artifact name (docling_dom.json, etc.) |
| Set proper Content-Type headers | 0.5 | application/json, text/plain, text/srt |
| Write download tests | 1.0 | Test all artifact formats |

**Acceptance Criteria**:

- [ ] GET /artifacts/{job_id}/docling_dom.json returns JSON
- [ ] GET /artifacts/{job_id}/transcript.txt returns plain text
- [ ] GET /artifacts/{job_id}/transcript.srt returns SRT
- [ ] Proper Content-Type headers set

**Deliverable**: Artifacts download endpoint

---

### Sprint 10: Integration Testing & Validation (4 hours)

**Goal**: Validate integration with downstream pipeline and create E2E tests.

**Tasks**:

| Task | Hours | Description |
| ---- | ----- | ----------- |
| Create downstream integration tests | 1.5 | Test DOM processing in downstream pipeline |
| Test artifact compatibility | 1.0 | Validate TXT, SRT in external tools |
| Document integration points | 1.0 | API contracts, data formats |
| Write E2E test suite | 0.5 | Full workflow: submit → process → download |

**Acceptance Criteria**:

- [ ] Downstream pipeline processes audio DOM successfully
- [ ] TXT and SRT artifacts work in external tools
- [ ] Integration points documented
- [ ] E2E tests pass for full workflows

**Deliverable**: Integration validation and E2E tests

---

## Phase Completion Checklist

- [ ] All 10 sprints completed
- [ ] All milestone deliverables ready
- [ ] Docling DOM mapping complete (M2.1)
- [ ] GET /results endpoint operational (M2.2)
- [ ] Multiple artifact formats generated (M2.3)
- [ ] Downstream integration validated (M2.4)
- [ ] DOM output validates against schema
- [ ] All artifact formats tested externally
- [ ] E2E tests passing
- [ ] PR created and merged

## Related Documents

- [Main PROJECT-PLAN](../PROJECT-PLAN.md)
- [Roadmap Phase 2](../roadmap.md#phase-2-integration--enhancement-week-3-4)
- [Tech Spec - Data Model](../tech-spec.md#3-data-model)
- [Tech Spec - API Specification](../tech-spec.md#4-api-specification)
- [ADR-001: Initial Architecture](../adr/adr-001-initial-architecture.md)
- [Previous: Phase 1 Core MVP](./phase-1-core-mvp.md)
- [Next: Phase 3 Polish](./phase-3-polish.md)
