---
title: "Project E - Audio Preprocessing Engine - Vision & Scope Document"
schema_type: common
status: draft
owner: core-maintainer
purpose: "Draft vision and scope document for Project E audio preprocessing engine."
tags:
  - research
---

## Audio Preprocessing Engine

### Vision & Scope Document

**Version 1.0** | December 2024
*RAG Pipeline Project Suite*
*Document 1 of 4*

---

## Document Information

| Field | Value |
|-------|-------|
| Project Name | audio-preprocessing-engine (Project E) |
| Document Type | Vision & Scope (Document 1 of 4) |
| Version | 1.0 |
| Status | Draft |
| Last Updated | December 2024 |
| Repository | github.com/williaby/audio-preprocessing-engine |
| Related Projects | Project A (Image), Project B (OCR), Project C (Fusion), Project D (Vector), Web UI |

### Document Suite

| Doc # | Document | Purpose |
|-------|----------|---------|
| 1 | Vision & Scope (this document) | Business context, goals, boundaries, success criteria |
| 2 | Architecture Decision Records | Key technical decisions with rationale |
| 3 | Technical Implementation Spec | Detailed API, schemas, implementation details |
| 4 | Development Roadmap | Phases, milestones, timeline, dependencies |

---

## 1. Executive Summary

### 1.1 Project Overview

Project E (audio-preprocessing-engine) is a dedicated audio processing pipeline that transforms audio and video files into structured, RAG-ready content. It handles transcription via Deepgram's Nova-2 model, speaker diarization, and automatic summarization, outputting results in a unified Docling Document Object Model (DOM) format that integrates seamlessly with the existing RAG pipeline.

### 1.2 Problem Statement

The existing RAG pipeline (Projects A through D) handles document and image processing but lacks support for audio content. Organizations increasingly need to ingest meeting recordings, podcasts, interviews, and video content into their knowledge bases. Without a dedicated audio pipeline, this content remains unsearchable and disconnected from document-based knowledge.

### 1.3 Solution Summary

Project E provides a Deepgram-centric audio processing service that:

- Accepts audio files (.mp3, .wav, .m4a, .flac, .ogg, .aac) and video files (.mp4, .mov, .avi, .mkv, .webm)
- Extracts audio from video files automatically
- Transcribes audio using Deepgram Nova-2 (2.5% WER, best-in-class accuracy)
- Identifies speakers via native Deepgram diarization
- Generates summaries using Deepgram's summarization v2
- Outputs structured data in Docling DOM format for downstream processing
- Integrates with the existing pipeline: Web UI → Project E → Project B → Project C → Project D

### 1.4 Key Differentiators

| Aspect | Project E Approach |
|--------|-------------------|
| ASR Engine | Deepgram Nova-2 API (not local Whisper) — faster, more accurate, simpler |
| Diarization | Native Deepgram (not separate Pyannote) — single API call handles all |
| Output Format | Docling DOM — same structure as document pipeline, enabling unified downstream processing |
| GPU Requirements | None — Deepgram is API-based; frees local GPU for other workloads |
| Summarization | Built-in Deepgram v2 — no separate LLM call needed |

---

## 2. Business Context

### 2.1 Strategic Alignment

Project E extends the RAG pipeline to support multimodal content ingestion, a critical capability for enterprise knowledge management. It aligns with the broader goal of building a comprehensive, self-hosted document intelligence platform.

### 2.2 Target Use Cases

#### 2.2.1 Meeting Recordings

Process recorded meetings (Zoom, Teams, Google Meet exports) into searchable, attributable transcripts. Speaker diarization ensures each statement is associated with the correct participant.

#### 2.2.2 Podcast & Interview Ingestion

Transform podcast episodes and interview recordings into RAG-ready chunks, preserving speaker context and enabling semantic search across audio archives.

#### 2.2.3 Training & Educational Content

Process lecture recordings, training videos, and webinars into structured content that can be searched, summarized, and cross-referenced with related documentation.

#### 2.2.4 Customer Call Analysis

Ingest support calls, sales conversations, and customer feedback recordings for downstream analysis, enabling search across voice-of-customer data.

### 2.3 Stakeholders

| Stakeholder | Role | Interest |
|-------------|------|----------|
| End Users | Content uploaders | Simple upload, accurate transcription, fast processing |
| RAG Consumers | Query audio content | Searchable, attributable chunks with playback links |
| Pipeline Developers | Maintain integration | Clean APIs, consistent output format, easy debugging |
| Platform Operators | Run infrastructure | Low resource usage, predictable costs, reliable operation |

---

## 3. Goals and Objectives

### 3.1 Primary Goals

#### G1: Accurate Transcription

Achieve industry-leading transcription accuracy using Deepgram Nova-2, targeting <3% Word Error Rate (WER) on clear speech and <8% WER on challenging audio (background noise, accents, overlapping speech).

#### G2: Reliable Speaker Attribution

Correctly identify and attribute speech segments to individual speakers via diarization, enabling proper citation in RAG responses (e.g., "According to Speaker 2 at 14:32...").

#### G3: Seamless Pipeline Integration

Output structured data that Project B and Project C can process identically to document content, requiring no special handling for audio-sourced chunks.

#### G4: Cost-Effective Processing

Maintain processing costs under $0.50 per hour of audio (including transcription, diarization, and summarization) while delivering real-time or faster processing speeds.

### 3.2 Success Metrics

| Metric | Target | Measurement | Notes |
|--------|--------|-------------|-------|
| Transcription WER | < 3% (clear), < 8% (noisy) | Sample testing | Deepgram benchmark |
| Diarization Error Rate | < 10% | Sample testing | Speaker confusion rate |
| Processing Speed | < 0.2x real-time | End-to-end timing | 1hr audio in <12 min |
| Cost per Hour | < $0.50 | Deepgram billing | Including all features |
| Pipeline Compatibility | 100% | Integration tests | B/C process without changes |
| Uptime | > 99.5% | Monitoring | Excluding Deepgram outages |

---

## 4. Scope Definition

### 4.1 In Scope

#### 4.1.1 Audio Processing

- Accept audio files: MP3, WAV, M4A, FLAC, OGG, AAC, WMA
- Accept video files with audio extraction: MP4, MOV, AVI, MKV, WEBM
- Handle files up to 4 hours in length (split longer files automatically)
- Support sample rates from 8kHz to 48kHz
- Process mono and stereo audio

#### 4.1.2 Transcription Features

- Speech-to-text via Deepgram Nova-2 model
- Smart formatting (punctuation, capitalization, numerals)
- Paragraph detection for semantic chunking alignment
- Word-level timestamps for precise citation
- Confidence scores per word/segment

#### 4.1.3 Speaker Processing

- Native Deepgram diarization (no separate system)
- Speaker labeling (Speaker 1, Speaker 2, etc.)
- Per-speaker statistics (duration, utterance count)
- Utterance grouping by speaker

#### 4.1.4 Content Enhancement

- Automatic summarization via Deepgram v2
- Language detection
- Audio quality assessment (SNR, silence ratio)

#### 4.1.5 Output Generation

- AudioDocument.json with full metadata
- Docling DOM representation for pipeline compatibility
- Playback URL references with timestamps

### 4.2 Out of Scope

- Real-time/streaming transcription (batch processing only)
- Speaker identification by name (only anonymous labels)
- Audio enhancement/cleanup (noise reduction, normalization)
- Translation to other languages
- Custom vocabulary training
- On-premise ASR (Whisper local deployment)
- Music transcription / lyrics extraction
- Sound effect detection / non-speech audio analysis

### 4.3 System Boundaries

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PROJECT E SYSTEM BOUNDARY                           │
└─────────────────────────────────────────────────────────────────────────────┘

   INPUTS (from Web UI)                    OUTPUTS (to Project B)
   ────────────────────                    ─────────────────────
   • Audio files                           • AudioDocument.json
   • Video files                           • Docling DOM structure
   • Job metadata                          • Processing metrics

   ┌───────────────────────────────────────────────────────────────────┐
   │                        PROJECT E                                   │
   │                                                                    │
   │   ┌────────────────┐                                              │
   │   │   Ingest &     │  • Format validation                         │
   │   │   Validate     │  • Duration extraction                       │
   │   │                │  • Content hash generation                   │
   │   └───────┬────────┘                                              │
   │           │                                                        │
   │           ▼                                                        │
   │   ┌────────────────┐                                              │
   │   │    Signal      │  • Audio extraction (from video)             │
   │   │  Conditioning  │  • Format conversion (to WAV/MP3)            │
   │   │                │  • Long file splitting (>4hr)                │
   │   └───────┬────────┘                                              │
   │           │                                                        │
   │           ▼                                                        │
   │   ┌────────────────┐                                              │
   │   │    Quality     │  • SNR calculation                           │
   │   │   Assessment   │  • Silence ratio detection                   │
   │   │                │  • Quality scoring                           │
   │   └───────┬────────┘                                              │
   │           │                                                        │
   │           ▼                                                        │
   │   ┌────────────────┐        ┌──────────────────────┐              │
   │   │   Deepgram     │───────►│    DEEPGRAM API      │              │
   │   │   API Client   │◄───────│    (External)        │              │
   │   │                │        │                      │              │
   │   │  • Transcribe  │        │  • Nova-2 model      │              │
   │   │  • Diarize     │        │  • Smart formatting  │              │
   │   │  • Summarize   │        │  • Speaker ID        │              │
   │   └───────┬────────┘        │  • Summarization v2  │              │
   │           │                 └──────────────────────┘              │
   │           ▼                                                        │
   │   ┌────────────────┐                                              │
   │   │   Response     │  • Parse JSON response                       │
   │   │   Processing   │  • Extract utterances/paragraphs             │
   │   │                │  • Build speaker profiles                    │
   │   └───────┬────────┘                                              │
   │           │                                                        │
   │           ▼                                                        │
   │   ┌────────────────┐                                              │
   │   │  Docling DOM   │  • Map speakers → SectionItem               │
   │   │  Construction  │  • Map utterances → TextItem                │
   │   │                │  • Attach timestamps as metadata             │
   │   └───────┬────────┘                                              │
   │           │                                                        │
   │           ▼                                                        │
   │   ┌────────────────┐                                              │
   │   │    Output      │  • AudioDocument.json                        │
   │   │   Generation   │  • Docling DOM (serialized)                  │
   │   │                │  • Metrics/telemetry                         │
   │   └────────────────┘                                              │
   │                                                                    │
   └───────────────────────────────────────────────────────────────────┘
```

---

## 5. Architecture Overview

### 5.1 Pipeline Position

Project E operates in parallel with Project A, both feeding into Project B. The Web UI routes files to the appropriate preprocessor based on content type.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RAG PIPELINE DATA FLOW                               │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────┐
                              │   WEB UI     │
                              │   (Upload)   │
                              └──────┬───────┘
                                     │
                    File Type Detection & Routing
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
              ▼                      ▼                      ▼
        ┌──────────┐          ┌──────────┐          ┌──────────┐
        │PROJECT A │          │PROJECT E │          │PROJECT B │
        │          │          │          │          │          │
        │  Image   │          │  Audio   │          │  Direct  │
        │  IQA +   │          │Deepgram +│          │ Docling  │
        │  Layout  │          │ Docling  │          │(born-dig)│
        │          │          │   DOM    │          │          │
        └────┬─────┘          └────┬─────┘          └────┬─────┘
             │                     │                     │
             │   DocumentMeta      │   AudioDocument     │   OCRDocument
             │   + Docling DOM     │   + Docling DOM     │   + Docling DOM
             │                     │                     │
             └──────────────┬──────┴─────────────────────┘
                            │
                            ▼
                      ┌──────────┐
                      │PROJECT B │
                      │          │
                      │ Unified  │  ◄── Processes all Docling DOMs identically
                      │ Docling  │
                      │Processing│
                      └────┬─────┘
                           │
                           ▼
                      ┌──────────┐
                      │PROJECT C │
                      │          │
                      │ Fusion + │
                      │ Chunking │
                      │          │
                      └────┬─────┘
                           │
                           │  FusedDocument.json
                           │  + rag_chunks[]
                           ▼
                      ┌──────────┐
                      │PROJECT D │
                      │          │
                      │ LanceDB  │
                      │ Indexing │
                      │          │
                      └──────────┘
```

### 5.2 Docling DOM Unification Strategy

The key architectural decision is using Docling's Document Object Model as the unifying structure for both document and audio content. This enables Projects B and C to process audio-sourced content identically to document-sourced content.

#### 5.2.1 Mapping Strategy

| Audio Concept | Docling Element | Metadata |
|---------------|-----------------|----------|
| Entire transcript | Document | source_type: 'audio', duration_ms, speakers[] |
| Speaker turn | SectionItem | speaker_id, speaker_label |
| Utterance/paragraph | TextItem | start_ms, end_ms, confidence, playback_url |
| Summary | SectionItem (special) | is_summary: true, summary_type: 'deepgram_v2' |

#### 5.2.2 Benefits of Unification

- Project B processes audio and document content with the same code paths
- Project C applies identical chunking strategies to all content types
- RAG chunks include provenance metadata regardless of source
- Future content types (video frames, etc.) can follow the same pattern

### 5.3 External Dependencies

| Dependency | Purpose | Failure Impact |
|------------|---------|----------------|
| Deepgram API | Transcription, diarization, summarization | Critical — no processing possible without it |
| Modal (optional) | Embedding generation | Medium — can queue for later if unavailable |
| Redis | Job queue, status tracking | High — jobs cannot be queued or tracked |
| FFmpeg | Audio extraction from video | Medium — video files fail, audio files work |

---

## 6. Deepgram Integration

### 6.1 API Configuration

Project E uses a single Deepgram API call per audio file, with all features enabled simultaneously:

```json
{
  "model": "nova-2",           // Best accuracy/speed balance (2.5% WER)
  "smart_format": true,         // Punctuation, capitalization, numerals
  "diarize": true,              // Native speaker identification
  "paragraphs": true,           // Semantic paragraph breaks
  "utterances": true,           // Speaker-grouped segments
  "summarize": "v2",            // Automatic summarization
  "detect_language": true,      // Auto language detection
  "punctuate": true,            // Sentence-level punctuation
  "profanity_filter": false     // Preserve original content
}
```

### 6.2 Cost Model

| Feature | Per Minute | Per Hour | Notes |
|---------|------------|----------|-------|
| Nova-2 Base | $0.0043 | $0.258 | Transcription only |
| + Diarization | included | included | No additional cost |
| + Smart Format | included | included | No additional cost |
| + Summarization v2 | $0.0015 | $0.090 | Optional add-on |
| **TOTAL (all features)** | **$0.0058** | **$0.348** | Well under $0.50 target |

### 6.3 Processing Speed

Deepgram processes audio significantly faster than real-time:

- Typical processing: 0.1x - 0.2x real-time (1 hour audio in 6-12 minutes)
- Network latency: ~2-5 seconds for API round-trip
- File upload: Depends on file size and connection speed
- Total end-to-end: ~12 seconds per minute of audio (including upload)

---

## 7. Output Schema

### 7.1 AudioDocument.json

The primary output of Project E, containing all transcription results and metadata:

```json
{
  "document_id": "audio_abc123",
  "source_file": {
    "filename": "meeting_2024-12-03.mp3",
    "file_hash": "sha256:...",
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
    "quality_score": 0.85
  },
  "deepgram_metadata": {
    "model": "nova-2",
    "request_id": "req_xyz789",
    "processing_time_ms": 45000,
    "cost_usd": 0.348
  },
  "transcription": {
    "language": "en",
    "language_confidence": 0.98,
    "word_count": 8500,
    "speaker_count": 3
  },
  "speakers": [
    { "id": "speaker_0", "label": "Speaker 1", "duration_ms": 1200000, "utterance_count": 45 },
    { "id": "speaker_1", "label": "Speaker 2", "duration_ms": 1500000, "utterance_count": 52 },
    { "id": "speaker_2", "label": "Speaker 3", "duration_ms": 900000, "utterance_count": 28 }
  ],
  "summary": {
    "text": "The meeting covered Q4 planning...",
    "type": "deepgram_v2"
  },
  "docling_document": { ... }  // Serialized Docling DOM
}
```

---

## 8. Constraints and Assumptions

### 8.1 Constraints

#### Technical Constraints

- Deepgram API dependency — requires internet connectivity and valid API key
- File size limits — practical limit of ~4 hours per file (longer files split automatically)
- Language support — Nova-2 supports major languages but accuracy varies
- No real-time streaming — batch processing only in this version

#### Business Constraints

- Deepgram costs scale with usage — budget monitoring required
- API rate limits — Deepgram has concurrent request limits based on plan
- Data privacy — audio content leaves infrastructure for Deepgram processing

### 8.2 Assumptions

1. Deepgram API remains available with consistent pricing and capabilities
2. Audio files contain speech (not music, sound effects, or silence)
3. Speakers in recordings speak clearly and sequentially (not constant overlapping)
4. Users accept processing latency of ~12 seconds per minute of audio
5. Downstream pipeline (B, C, D) can handle audio-sourced Docling DOMs without modification
6. Modal infrastructure is available for embedding generation when needed

### 8.3 Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Deepgram API outage | High — all processing stops | Retry logic, queue persistence, alert on failure |
| Cost overrun | Medium — unexpected bills | Usage monitoring, daily/monthly caps, alerts |
| Poor audio quality | Medium — bad transcription | Quality pre-check, user warnings, skip/flag option |
| Diarization errors | Low — wrong speaker labels | Confidence thresholds, flag uncertain segments |
| Long file timeouts | Low — processing fails | Automatic splitting, progress tracking |

---

## 9. Future Considerations

### 9.1 Potential Enhancements (Post-MVP)

#### Phase 2: Enhanced Features

- Real-time/streaming transcription for live events
- Custom vocabulary support for domain-specific terms
- Audio enhancement preprocessing (noise reduction)
- Multiple language support with auto-translation

#### Phase 3: Advanced Capabilities

- Named speaker identification (match voices to known individuals)
- Sentiment analysis per speaker
- Topic extraction and tagging
- Action item and decision detection

#### Phase 4: Alternative Backends

- Local Whisper deployment option (for air-gapped environments)
- Multi-provider fallback (Deepgram → Assembly AI → Whisper)
- On-premise ASR for sensitive content

### 9.2 Integration Opportunities

- Video frame extraction for visual context alongside audio
- Slide synchronization for presentation recordings
- Calendar integration for automatic meeting capture
- Automated transcription of new uploads via file watch

---

## 10. Document Approval

This Vision & Scope document establishes the foundational direction for Project E. Subsequent documents (Architecture Decision Records, Technical Implementation Specification, and Development Roadmap) will provide detailed technical guidance based on this scope.

| Role | Name | Date |
|------|------|------|
| Project Owner | | |
| Technical Lead | | |
| Reviewer | | |

---

*— End of Document —*
