---
title: "ADR-001: Initial Architecture - Deepgram-Centric Audio Processing"
schema_type: planning
status: published
owner: core-maintainer
purpose: "Document the critical architectural decision to use Deepgram Nova-2 as the exclusive ASR engine."
tags:
  - adr
  - architecture
component: Development-Tools
source: "/plan command generation"
---

> **Status**: Accepted
> **Date**: 2025-12-04
> **Supersedes**: None

## TL;DR

Use Deepgram Nova-2 as the exclusive ASR engine with native diarization and summarization, outputting Docling DOM format for seamless integration with the existing image_detection RAG pipeline.

## Context

### Problem

Audio Processor needs a high-accuracy, cost-effective transcription solution that integrates with the existing RAG pipeline. The solution must handle speaker identification, produce structured output compatible with downstream processing, and minimize infrastructure complexity.

### Constraints

- **Technical**: Must integrate with existing Docling DOM-based pipeline, support async processing via Redis Queue, handle files up to 4 hours
- **Business**: Target cost < $0.50/hour audio, processing speed < 0.2x real-time, single developer timeline

### Significance

The ASR engine choice determines accuracy, cost structure, infrastructure requirements, and integration complexity. Wrong choice could lead to:
- Poor transcription quality affecting RAG retrieval
- High GPU costs competing with other pipeline components
- Complex integration requiring special handling for audio content
- Vendor lock-in or offline capability limitations

## Decision

**We will use Deepgram Nova-2 API as the exclusive ASR engine with native diarization and summarization, outputting Docling DOM format for pipeline integration.**

### Rationale

1. **Best-in-class accuracy**: Nova-2 achieves 2.5% WER vs. Whisper's 4-5%
2. **Zero GPU requirement**: API-based processing frees local GPU for other tasks
3. **Native diarization**: Single API call handles transcription + speaker ID (no Pyannote needed)
4. **Cost-effective**: $0.35/hour (including summarization) vs. GPU compute costs
5. **Processing speed**: 0.1x real-time means 1 hour audio in ~6 minutes
6. **Pipeline integration**: Docling DOM format enables unified downstream processing

## Options Considered

### Option 1: Deepgram Nova-2 (API) ✓

**Pros**:
- ✅ 2.5% WER (industry-leading accuracy)
- ✅ Native diarization included at no extra cost
- ✅ Fast processing (0.1x real-time)
- ✅ No GPU infrastructure needed
- ✅ Built-in smart formatting and summarization
- ✅ Predictable costs at $0.35/hour

**Cons**:
- ❌ External API dependency (requires internet)
- ❌ Audio data leaves infrastructure
- ❌ Vendor lock-in
- ❌ No offline capability

### Option 2: Local Whisper Large (Modal GPU)

**Pros**:
- ✅ Open-source, self-hosted
- ✅ No external API dependency
- ✅ Data stays local

**Cons**:
- ❌ 4-5% WER (lower accuracy)
- ❌ Requires 10+ GB VRAM (A10G/A100)
- ❌ Modal cold starts add 30-60s per job
- ❌ GPU contention with IQA and embedding workloads
- ❌ Requires separate Pyannote for diarization
- ❌ Slower processing (0.3-1x real-time)

### Option 3: Whisper API (OpenAI)

**Pros**:
- ✅ No local GPU needed
- ✅ Fast processing

**Cons**:
- ❌ 4-5% WER (same as local Whisper)
- ❌ No native diarization
- ❌ Higher cost ($0.36/hour transcription only)
- ❌ Basic formatting vs. Deepgram's smart formatting

## Consequences

### Positive

- ✅ **Best Accuracy**: 2.5% WER significantly improves RAG retrieval quality
- ✅ **Simplified Architecture**: No GPU management, no separate diarization pipeline
- ✅ **Fast Processing**: 1 hour audio processes in ~6 minutes
- ✅ **Cost Predictable**: $0.35/hour well under $0.50 target
- ✅ **Pipeline Integration**: Docling DOM enables unified downstream processing

### Trade-offs

- ⚠️ **Internet Dependency**: Mitigated by retry logic, queue persistence, and job recovery
- ⚠️ **Vendor Lock-in**: Future ADR may add Whisper fallback for air-gapped deployments
- ⚠️ **Data Privacy**: Audio sent to Deepgram (acceptable for non-sensitive use cases)

### Technical Debt

- **Air-gapped Support**: Phase 2 may add local Whisper option for sensitive environments
- **Multi-provider Fallback**: Future enhancement could add Assembly AI or alternatives

## Implementation

### Components Affected

1. **Audio Processing Service**: Deepgram SDK integration, async API calls with timeout handling
2. **Quality Assessment**: Pre-flight audio analysis (SNR, silence, clipping) before API call
3. **DOM Builder**: Map Deepgram utterances/speakers to Docling SectionItems and TextItems
4. **Job Queue**: Redis Queue with retry logic for API failures
5. **Configuration**: Environment variables for API key, timeout, quality thresholds

### Testing Strategy

- **Unit**: Mock Deepgram responses, test DOM mapping, quality assessment logic
- **Integration**: Real API calls with test audio (verify WER, diarization, cost)
- **E2E**: Full pipeline test with various audio types (meetings, podcasts, noisy audio)

## Validation

### Success Criteria

- [ ] Transcription achieves < 3% WER on clear speech test set
- [ ] Diarization achieves < 10% error rate on multi-speaker audio
- [ ] Processing completes in < 0.2x real-time for typical 1-hour files
- [ ] Cost stays under $0.50/hour including all features
- [ ] Docling DOM output processes successfully through existing pipeline

### Review Schedule

- **Initial**: Week 4 (MVP completion) - Validate metrics against targets
- **Ongoing**: Monthly cost/accuracy review, quarterly vendor evaluation

## Related

- [Project Vision](../project-vision.md): Overall goals and constraints
- [Tech Spec](../tech-spec.md): Detailed API integration, data models, processing pipeline
- [Roadmap](../roadmap.md): Implementation phases and timeline
