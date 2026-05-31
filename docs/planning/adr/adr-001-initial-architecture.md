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

Use Deepgram Nova-2 as the exclusive ASR engine with native diarization and summarization, outputting Docling DOM format for direct integration with the existing image_detection RAG pipeline.

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

1. **Competitive accuracy**: Nova-2 achieves 6-9% WER (industry benchmark ~8.4%) vs. Whisper's 4-5% (Whisper has better WER but lacks native diarization)
2. **Zero GPU requirement**: API-based processing frees local GPU for other tasks
3. **Native diarization**: Single API call handles transcription + speaker ID (no Pyannote needed) - this integration benefit outweighs WER difference
4. **Cost-effective**: $0.35/hour (including summarization) vs. GPU compute costs
5. **Processing speed**: ~0.0083x real-time (~30 seconds per hour of audio)
6. **Pipeline integration**: Docling DOM format enables unified downstream processing

## Options Considered

### Option 1: Deepgram Nova-2 (API) ✓

**Pros**:

- ✅ Competitive accuracy (6-9% WER, industry benchmark ~8.4%)
- ✅ Native diarization included at no extra cost (key differentiator vs. Whisper)
- ✅ Very fast processing (~0.0083x real-time, ~30 seconds per hour of audio)
- ✅ No GPU infrastructure needed
- ✅ Built-in smart formatting and summarization
- ✅ Predictable costs at $0.35/hour

**Cons**:

- ❌ External API dependency (requires internet)
- ❌ Audio data leaves infrastructure (see data privacy considerations below)
- ❌ Vendor lock-in
- ❌ No offline capability

### Option 2: Local Whisper Large (Modal GPU)

**Pros**:

- ✅ Open-source, self-hosted
- ✅ No external API dependency
- ✅ Data stays local (critical for sensitive content)
- ✅ Better raw WER (4-5% vs. Deepgram's 6-9%)

**Cons**:

- ❌ Requires 10+ GB VRAM (A10G/A100)
- ❌ Modal cold starts add 30-60s per job
- ❌ GPU contention with IQA and embedding workloads
- ❌ Requires separate Pyannote for diarization (two-step pipeline)
- ❌ Slower overall processing (0.3-1x real-time including diarization)

### Option 3: Whisper API (OpenAI)

**Pros**:

- ✅ No local GPU needed
- ✅ Fast processing
- ✅ Better WER (4-5%)

**Cons**:

- ❌ No native diarization (requires separate Pyannote)
- ❌ Higher cost ($0.36/hour transcription only, more with diarization)
- ❌ Basic formatting vs. Deepgram's smart formatting
- ❌ Audio data leaves infrastructure

## Consequences

### Positive

- ✅ **Integrated Diarization**: Native speaker ID in single API call (vs. two-step Whisper+Pyannote pipeline)
- ✅ **Simplified Architecture**: No GPU management, no alignment algorithms
- ✅ **Very Fast Processing**: 1 hour audio processes in ~30 seconds
- ✅ **Cost Predictable**: $0.35/hour well under $0.50 target
- ✅ **Pipeline Integration**: Docling DOM enables unified downstream processing
- ✅ **Smart Formatting**: Automatic entity formatting (dates, numbers, currency)

### Trade-offs

- ⚠️ **WER vs. Integration**: Accept 6-9% WER (vs. Whisper's 4-5%) for native diarization benefit
- ⚠️ **Internet Dependency**: Mitigated by retry logic, queue persistence, and job recovery
- ⚠️ **Vendor Lock-in**: Future ADR may add Whisper fallback for air-gapped deployments
- ⚠️ **Data Privacy**: Audio sent to Deepgram (see guidance below)

### Data Privacy Considerations

**When to use Deepgram** (API-based):

- General business meetings, podcasts, public content
- Internal non-sensitive communications
- Content already shared externally

**When to use Whisper fallback** (local processing - Phase 2):

- **PII/PHI**: Audio containing personally identifiable information or protected health information
- **Legal/Confidential**: Attorney-client privileged communications, NDAs, trade secrets
- **Compliance Requirements**: HIPAA, GDPR Article 32, FedRAMP, or other data residency mandates
- **Sensitive HR**: Performance reviews, disciplinary actions, salary discussions

**Recommendation**: For sensitive content, defer to Phase 2 local Whisper implementation despite higher complexity.

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

- [ ] Transcription achieves < 10% WER on clear speech test set (target 6-9% range)
- [ ] Diarization achieves < 10% error rate on multi-speaker audio
- [ ] Processing completes in < 0.02x real-time (< 1 minute per hour of audio)
- [ ] Cost stays under $0.50/hour including all features
- [ ] Docling DOM output processes successfully through existing pipeline

### Review Schedule

- **Initial**: Week 4 (MVP completion) - Validate metrics against targets
- **Ongoing**: Monthly cost/accuracy review, quarterly vendor evaluation

## Security Considerations

### Authentication and Authorization

The Deepgram API key is the primary credential for this architecture. It must
be loaded exclusively from environment variables (via Pydantic Settings) and
must never appear in source files, logs, or commit history. The pre-commit
`detect-secrets` and TruffleHog hooks enforce this automatically.

Access to the processing API endpoint should be gated by authentication
(API key or JWT) before any audio is accepted. Authorization must be checked
before audio files are retrieved from storage or queued for processing.

### Dependency Scanning Posture

The pipeline depends on `deepgram-sdk`, `redis[hiredis]`, `rq`, `docling-core`,
and their transitive dependencies. `pip-audit` runs in CI on every push to
detect known CVEs. Any new dependency added to the `audio` or `jobs` extras
must be reviewed for known vulnerabilities before merging. Unfixed CVEs are
documented in `docs/known-vulnerabilities.md` per the 60-day reassessment
policy.

### Supply Chain Controls

Third-party GitHub Actions in CI workflows are pinned to commit SHAs. The
`supply-chain` dependency group provides `cyclonedx-bom` for SBOM generation
on tagged releases, enabling downstream consumers to audit the full dependency
graph. Renovate automates dependency updates; PRs from Renovate trigger the
full CI security scan before merge.

### Audio Data Privacy

Audio data sent to Deepgram leaves the local infrastructure. For PII, PHI,
or legally privileged audio, the Phase 2 local Whisper fallback (noted under
Technical Debt) must be used instead. The processing pipeline must not log
audio content or expose it in error messages.

## Related

- [Project Vision](../project-vision.md): Overall goals and constraints
- [Tech Spec](../tech-spec.md): Detailed API integration, data models, processing pipeline
- [Roadmap](../roadmap.md): Implementation phases and timeline
