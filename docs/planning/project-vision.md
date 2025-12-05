---
title: "Audio Processor - Project Vision & Scope"
schema_type: planning
status: published
owner: core-maintainer
purpose: "Document the project vision, scope, and success criteria."
tags:
  - planning
  - scope
component: Strategy
source: "/plan command generation"
---

> **Status**: Active | **Version**: 1.0 | **Updated**: 2025-12-04

## TL;DR

Audio Processor is a Deepgram-powered audio transcription pipeline that converts audio/video files into structured, RAG-ready content through high-accuracy speech-to-text, speaker diarization, and automatic summarization, outputting unified Docling DOM format for seamless integration with the existing image_detection RAG pipeline.

## Problem Statement

### Pain Point

The existing RAG pipeline (/home/byron/dev/image_detection/) handles text documents and images but lacks support for audio content. Organizations increasingly need to ingest meeting recordings, podcasts, interviews, and video content into knowledge bases, but this content remains unsearchable and disconnected from document-based knowledge without a parallel audio processing path.

### Target Users

- **Primary**: Knowledge management teams and researchers who need to index audio/video content alongside documents
- **Context**: Processing meeting recordings, interviews, podcasts, and educational content for semantic search and retrieval in a unified RAG system accessed through a shared web UI

### Success Metrics

- **Transcription Accuracy**: Achieve < 3% WER on clear speech, < 8% on noisy audio (Deepgram Nova-2 benchmark)
- **Processing Speed**: < 0.2x real-time (1 hour audio processes in < 12 minutes)
- **Pipeline Integration**: 100% compatibility with downstream chunking and vector indexing (no special handling required)
- **Cost Efficiency**: < $0.50 per hour of audio processed (including all features)
- **Uptime**: > 99.5% excluding external API dependencies

## Solution Overview

### Core Value

Audio Processor transforms spoken content into searchable, attributable text chunks that integrate seamlessly with existing document processing pipelines, enabling unified semantic search across all content types.

### Key Capabilities (MVP)

1. **Universal Audio Ingestion**: Accept audio files (MP3, WAV, M4A, FLAC, OGG, AAC) and video files (MP4, MOV, AVI, MKV, WEBM) with automatic audio extraction from video
2. **High-Accuracy Transcription**: Deepgram Nova-2 ASR with 2.5% WER, smart formatting, word-level timestamps, and confidence scores
3. **Speaker Attribution**: Native Deepgram diarization providing word-level speaker identification without separate processing steps
4. **Content Summarization**: Automatic summarization via Deepgram v2 for improved retrieval and user experience
5. **RAG Integration**: Output Docling Document Object Model (DOM) format matching the image_detection pipeline for unified downstream processing

## Scope Definition

### In Scope (MVP)

- ✅ **Audio/Video Support**: All major audio formats plus video files with audio extraction via FFmpeg
- ✅ **Deepgram Processing**: Nova-2 transcription, native diarization, v2 summarization in single API call
- ✅ **Quality Assessment**: Pre-transcription quality analysis (SNR, silence ratio, clipping detection) with user warnings
- ✅ **Long File Handling**: Automatic splitting of files > 4 hours with overlap and result merging
- ✅ **Docling DOM Output**: Speaker-centric document structure with utterances as TextItems, speakers as SectionItems
- ✅ **Job Management**: Async processing via Redis Queue with status tracking, progress updates, and retry logic
- ✅ **Playback URLs**: Media fragment URIs for timestamp-based playback links in RAG responses

### Out of Scope

- ❌ **Real-time Streaming**: Batch processing only (real-time transcription excluded)
- ❌ **Speaker Identification**: Anonymous speaker labels only (no name matching)
- ❌ **Audio Enhancement**: No noise reduction, equalization, or audio cleanup
- ❌ **Translation**: Single-language output only (language detection supported)
- ❌ **Custom Vocabularies**: No domain-specific training or vocabulary injection
- 🔄 **Local ASR Deployment**: Whisper fallback deferred to Phase 2 for air-gapped environments
- 🔄 **Advanced Analytics**: Sentiment analysis, topic extraction, action item detection deferred to Phase 3

## Constraints

### Technical

- **Platform**: Python 3.12 CLI application with FastAPI endpoints
- **Language**: Python with UV package manager, Ruff linting, BasedPyright type checking
- **Performance**:
  - Process 1 hour of audio in < 12 minutes end-to-end
  - Support files up to 4 hours (auto-split longer files)
  - Max file size: 2GB
- **External Dependencies**:
  - Deepgram API (critical path - no offline mode)
  - FFmpeg for media manipulation
  - Redis for job queue and status

### Business

- **Timeline**: MVP functional within 4 weeks (foundation + core features + integration testing)
- **Resources**: Single developer, leveraging existing RAG pipeline infrastructure
- **Cost Model**: Deepgram pricing $0.26/hour (base) + $0.09/hour (summarization) = $0.35/hour target

## Integration Architecture

```
Web UI (Shared)
    │
    ├── Route: Documents/Images → image_detection/
    │                               ↓
    │                        Docling DOM Output
    │                               ↓
    └── Route: Audio/Video    → audio_processor/
                                    ↓
                             Deepgram Processing
                                    ↓
                             Docling DOM Output
                                    ↓
                        ┌───────────┴───────────┐
                        ▼                       ▼
                  Unified Chunking         Vector Indexing
                  (same logic for         (same embeddings
                   all content types)      for all sources)
```

## Assumptions to Validate

- [ ] Deepgram Nova-2 accuracy meets < 3% WER target on typical use case audio (meetings, podcasts)
- [ ] Deepgram native diarization provides adequate speaker separation (< 10% error rate)
- [ ] Docling DOM speaker-centric structure supports effective chunking strategies
- [ ] Downstream pipeline (chunking, embedding, vector indexing) handles audio-sourced DOMs without modification
- [ ] Processing cost stays under $0.50/hour including API calls and compute
- [ ] Redis queue handles expected job volumes with adequate retry/persistence

## Related Documents

- [Architecture Decisions](./adr/adr-001-initial-architecture.md)
- [Technical Spec](./tech-spec.md)
- [Development Roadmap](./roadmap.md)
