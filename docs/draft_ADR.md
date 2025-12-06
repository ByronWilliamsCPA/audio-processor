# Project E

## Audio Preprocessing Engine

### Architecture Decision Records

**Version 1.0** | December 2024
*RAG Pipeline Project Suite*
*Document 2 of 4*

---

## Document Information

| Field | Value |
|-------|-------|
| Project Name | audio-preprocessing-engine (Project E) |
| Document Type | Architecture Decision Records (Document 2 of 4) |
| Version | 1.0 |
| Status | Draft |
| Last Updated | December 2024 |
| Prerequisites | Project E Vision & Scope v1.0 |

---

## Table of Contents

1. [ADR-001: Deepgram Nova-2 as Primary ASR Engine](#adr-001-deepgram-nova-2-as-primary-asr-engine)
2. [ADR-002: Native Deepgram Diarization](#adr-002-native-deepgram-diarization)
3. [ADR-003: Docling DOM as Unified Output Format](#adr-003-docling-dom-as-unified-output-format)
4. [ADR-004: API-Based Processing Over Local Inference](#adr-004-api-based-processing-over-local-inference)
5. [ADR-005: FFmpeg for Audio Extraction and Conversion](#adr-005-ffmpeg-for-audio-extraction-and-conversion)
6. [ADR-006: Automatic Long File Splitting](#adr-006-automatic-long-file-splitting)
7. [ADR-007: Quality-First Error Handling Strategy](#adr-007-quality-first-error-handling-strategy)
8. [ADR-008: Redis Queue for Job Management](#adr-008-redis-queue-for-job-management)
9. [ADR-009: Speaker-Centric Document Structure](#adr-009-speaker-centric-document-structure)
10. [ADR-010: Deepgram Summarization v2 Over LLM Summarization](#adr-010-deepgram-summarization-v2-over-llm-summarization)

---

## ADR-001: Deepgram Nova-2 as Primary ASR Engine

### Status

**Accepted**

### Context

Project E requires a speech-to-text (ASR) engine to transcribe audio content. The primary options considered were:

1. **Deepgram Nova-2** — Cloud API with state-of-the-art accuracy
2. **OpenAI Whisper (local)** — Open-source model, self-hosted
3. **OpenAI Whisper API** — Cloud-hosted Whisper
4. **AWS Transcribe** — Amazon's ASR service
5. **Google Speech-to-Text** — Google Cloud's ASR service

### Decision

**Use Deepgram Nova-2 as the primary ASR engine.**

### Rationale

| Criteria | Deepgram Nova-2 | Whisper Local | Whisper API | AWS Transcribe |
|----------|-----------------|---------------|-------------|----------------|
| **WER (accuracy)** | 2.5% (best) | 4-5% | 4-5% | 5-7% |
| **Speed** | 0.1x real-time | 0.3-1x real-time | 0.2x real-time | 0.15x real-time |
| **GPU Required** | No | Yes (significant) | No | No |
| **Diarization** | Native, included | Requires Pyannote | Not available | Native, extra cost |
| **Cost/hour** | $0.26 | GPU compute | $0.36 | $0.96 |
| **Latency** | Low | High (local inference) | Medium | Medium |
| **Smart Formatting** | Built-in | Manual post-process | Basic | Basic |

**Key factors:**

1. **Accuracy**: Nova-2's 2.5% WER is industry-leading, significantly better than Whisper's 4-5%
2. **No GPU requirement**: Frees local GPU (P2000) for other pipeline tasks or eliminates Modal dependency for ASR
3. **Native diarization**: Single API call handles transcription + speaker ID (see ADR-002)
4. **Cost-effective**: $0.26/hour is competitive and well under our $0.50 target
5. **Processing speed**: 0.1x real-time means 1 hour of audio processes in ~6 minutes

### Consequences

**Positive:**
- Best-in-class transcription accuracy
- Simplified architecture (no local GPU management for ASR)
- Fast processing with predictable costs
- Native diarization eliminates separate speaker ID system

**Negative:**
- External API dependency (requires internet)
- Audio data leaves infrastructure for processing
- Vendor lock-in to Deepgram
- No offline/air-gapped operation

**Mitigations:**
- Implement retry logic with exponential backoff
- Queue persistence ensures jobs survive API outages
- Future ADR may add Whisper fallback for air-gapped deployments

---

## ADR-002: Native Deepgram Diarization

### Status

**Accepted**

### Context

Speaker diarization (identifying who spoke when) is essential for proper attribution in RAG responses. Options considered:

1. **Deepgram native diarization** — Built into Nova-2 API
2. **Pyannote Audio** — Open-source diarization library
3. **AWS Transcribe diarization** — Separate from transcription
4. **NeMo Speaker Diarization** — NVIDIA's toolkit

### Decision

**Use Deepgram's native diarization exclusively.**

### Rationale

| Criteria | Deepgram Native | Pyannote | AWS Transcribe |
|----------|-----------------|----------|----------------|
| **Integration** | Single API call | Separate pipeline | Separate feature |
| **Additional Cost** | $0.00 | GPU compute | +$0.024/min |
| **Alignment Quality** | Word-level | Segment-level | Word-level |
| **Setup Complexity** | None | High (models, GPU) | Medium |
| **Latency Added** | None | +30-60s/hour | None |

**Key factors:**

1. **Zero additional cost**: Diarization is included with Nova-2 transcription
2. **Perfect alignment**: Speaker labels are attached at the word level during transcription
3. **No additional infrastructure**: No GPU needed for Pyannote, no separate service
4. **Reduced complexity**: One API call instead of two-stage pipeline

### Consequences

**Positive:**
- Dramatically simplified pipeline
- Word-level speaker alignment (superior to post-hoc diarization)
- No additional costs
- Faster end-to-end processing

**Negative:**
- Diarization quality tied to Deepgram's implementation
- No fine-tuning options for specific use cases
- Limited to Deepgram's maximum speaker count

**Trade-offs accepted:**
- Pyannote may have slightly better diarization in edge cases, but the integration complexity and GPU requirements outweigh marginal accuracy gains

---

## ADR-003: Docling DOM as Unified Output Format

### Status

**Accepted**

### Context

Project E needs to output structured data that integrates with the existing RAG pipeline (Projects B, C, D). Options considered:

1. **Docling DOM** — Same format used by Project A and Project B
2. **Custom AudioTranscript schema** — Purpose-built for audio
3. **W3C Web Annotation format** — Standard annotation format
4. **Raw JSON with custom structure** — Bespoke format

### Decision

**Output audio content in Docling Document Object Model format, mapping audio concepts to document concepts.**

### Rationale

**Mapping Strategy:**

| Audio Concept | Docling Element | Rationale |
|---------------|-----------------|-----------|
| Full transcript | `DoclingDocument` | Top-level container |
| Speaker turn | `SectionItem` | Groups utterances by speaker |
| Utterance | `TextItem` | Individual text blocks with timestamps |
| Summary | `SectionItem` | Special section with `is_summary: true` |
| Timestamp | `prov` (provenance) | Metadata attached to each item |

**Key factors:**

1. **Zero downstream changes**: Projects B and C process Docling DOMs unchanged
2. **Unified chunking**: Same chunking strategies work for documents and audio
3. **Consistent provenance**: All RAG chunks have source attribution regardless of origin
4. **Future-proof**: New content types can follow the same pattern

### Consequences

**Positive:**
- Seamless pipeline integration
- Reuse existing Docling processing code
- Consistent RAG chunk structure
- Unified metadata model

**Negative:**
- Some audio concepts don't map perfectly to document concepts
- Additional metadata fields needed for audio-specific data
- Docling DOM wasn't designed for temporal media

**Implementation notes:**
- Audio-specific metadata stored in `meta` field of each item
- Timestamps use `start_ms` and `end_ms` fields
- Speaker info stored in section-level metadata
- Playback URLs generated for each text segment

---

## ADR-004: API-Based Processing Over Local Inference

### Status

**Accepted**

### Context

Project E could process audio either via cloud APIs or local inference. This decision covers the overall processing strategy.

### Decision

**Use API-based processing (Deepgram) as the primary and only processing path for MVP.**

### Rationale

**Resource comparison (processing 1 hour of audio):**

| Aspect | API-Based (Deepgram) | Local (Whisper Large) |
|--------|---------------------|----------------------|
| **GPU Memory** | 0 GB | 10+ GB VRAM |
| **Processing Time** | ~6 minutes | ~20-40 minutes |
| **CPU Usage** | Minimal | High (if CPU fallback) |
| **RAM Usage** | ~500 MB | 8-16 GB |
| **Cost** | $0.35 | GPU compute time |
| **Cold Start** | None | Model loading (30-60s) |

**Infrastructure implications:**

- Local Whisper would require Modal GPU instances (A10G/A100)
- Modal cold starts add 30-60 seconds per job
- GPU instances compete with IQA and embedding workloads
- API approach allows Project E to run on minimal resources

### Consequences

**Positive:**
- Project E container requires minimal resources (2 CPU, 2GB RAM)
- No GPU contention with other pipeline components
- Predictable processing times
- Simpler deployment and scaling

**Negative:**
- Internet dependency for all processing
- Data privacy concerns (audio sent to Deepgram)
- No offline capability
- Vendor dependency

**Future consideration:**
- ADR may be revisited to add local Whisper fallback for air-gapped deployments
- Would require Modal GPU allocation or dedicated local GPU

---

## ADR-005: FFmpeg for Audio Extraction and Conversion

### Status

**Accepted**

### Context

Project E must handle video files (extract audio) and various audio formats. A tool is needed for media manipulation.

### Decision

**Use FFmpeg for all audio extraction and format conversion.**

### Rationale

| Tool | Capability | License | Deployment |
|------|------------|---------|------------|
| **FFmpeg** | Full audio/video processing | LGPL/GPL | Single binary |
| **pydub** | Python wrapper (uses FFmpeg) | MIT | Python package |
| **moviepy** | Video editing (uses FFmpeg) | MIT | Python package |
| **libav** | FFmpeg fork | LGPL | Single binary |

**FFmpeg advantages:**

1. **Industry standard**: Most widely used, best documented
2. **Format support**: Handles every audio/video format we need
3. **Performance**: Highly optimized, hardware acceleration available
4. **Reliability**: Battle-tested in production systems worldwide
5. **Single dependency**: One binary handles all media operations

### Consequences

**Positive:**
- Universal format support
- High performance
- Well-documented with extensive examples
- Available in all base images

**Negative:**
- Large binary (~100MB with all codecs)
- GPL licensing considerations for some codecs
- Complex command-line interface

**Implementation:**
```python
# Audio extraction from video
ffmpeg -i input.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 output.wav

# Format conversion for Deepgram
ffmpeg -i input.m4a -acodec libmp3lame -ar 16000 -ac 1 output.mp3
```

---

## ADR-006: Automatic Long File Splitting

### Status

**Accepted**

### Context

Deepgram has practical limits on file duration (~4 hours) and very long files may timeout or consume excessive memory. A strategy is needed for handling extended recordings.

### Decision

**Automatically split files longer than 4 hours into segments, process independently, then merge results.**

### Rationale

**Split strategy:**

| Approach | Pros | Cons |
|----------|------|------|
| **Fixed duration split** | Simple, predictable | May split mid-sentence |
| **Silence-based split** | Natural boundaries | Unreliable for continuous speech |
| **Fixed with overlap** | Handles boundary issues | Requires deduplication |

**Chosen approach: Fixed duration (3.5 hours) with 30-second overlap**

1. Split at 3.5-hour marks (under 4-hour limit)
2. Include 30-second overlap to capture boundary speech
3. Deduplicate overlapping segments during merge
4. Maintain continuous timestamps across segments

### Consequences

**Positive:**
- Handles arbitrarily long recordings
- Stays within API limits
- Enables parallel processing of segments
- Graceful handling of very long content

**Negative:**
- Complexity in result merging
- Potential for speaker ID inconsistency across segments
- Overlap processing adds ~1.4% overhead

**Implementation notes:**
- Use FFmpeg segment feature for splitting
- Track segment boundaries in metadata
- Merge algorithm aligns overlapping text by timestamp
- Speaker IDs normalized across segments (Speaker_1 in segment 2 may be Speaker_0 in segment 1)

---

## ADR-007: Quality-First Error Handling Strategy

### Status

**Accepted**

### Context

Audio quality varies significantly. Poor quality audio produces unreliable transcriptions. A strategy is needed for handling quality issues.

### Decision

**Implement quality assessment before transcription with configurable thresholds and user warnings.**

### Rationale

**Quality assessment metrics:**

| Metric | Measurement | Threshold | Action |
|--------|-------------|-----------|--------|
| **SNR (Signal-to-Noise)** | librosa/pydub | < 10 dB | Warn user |
| **Silence Ratio** | % of file that is silence | > 80% | Warn user |
| **Clipping** | % of samples at max amplitude | > 5% | Warn user |
| **Duration** | File length | < 1 second | Reject |

**Strategy: Warn but process (with quality metadata)**

1. Assess quality before sending to Deepgram
2. Attach quality scores to output metadata
3. Warn users about low-quality files but still process
4. Include confidence scores in RAG chunks for downstream filtering

### Consequences

**Positive:**
- Users informed about potential quality issues
- Quality metadata enables downstream filtering
- No silent failures on poor audio
- Flexibility in handling edge cases

**Negative:**
- Quality assessment adds processing time (~2-5 seconds)
- Threshold tuning may be needed for specific use cases
- Some users may ignore warnings

**Implementation:**
```python
class AudioQuality(BaseModel):
    snr_db: float           # Signal-to-noise ratio
    silence_ratio: float    # 0.0 - 1.0
    clipping_ratio: float   # 0.0 - 1.0
    quality_score: float    # 0.0 - 1.0 (composite)
    warnings: list[str]     # Human-readable warnings
```

---

## ADR-008: Redis Queue for Job Management

### Status

**Accepted**

### Context

Project E needs to manage async jobs, handle retries, and integrate with the existing pipeline's job system.

### Decision

**Use Redis with RQ (Redis Queue) for job management, consistent with other pipeline components.**

### Rationale

| System | Complexity | Existing Use | Features |
|--------|------------|--------------|----------|
| **Redis + RQ** | Low | Gateway, Project A | Simple, Python-native |
| **Celery + Redis** | Medium | None | More features, more complexity |
| **AWS SQS** | Low | None | Managed, but external |
| **RabbitMQ** | High | None | Enterprise features |

**Key factors:**

1. **Consistency**: Gateway already uses Redis + RQ
2. **Simplicity**: RQ is lightweight with minimal boilerplate
3. **Visibility**: Redis provides job status, progress tracking
4. **Retry support**: Built-in retry with exponential backoff

### Consequences

**Positive:**
- Consistent with existing pipeline architecture
- Shared Redis instance reduces infrastructure
- Simple Python integration
- Built-in job monitoring

**Negative:**
- RQ less feature-rich than Celery
- Single Redis instance is a SPOF
- Limited to Python workers

**Job structure:**
```python
@rq.job('audio-processing', timeout=3600, retry=Retry(max=3, interval=[60, 300, 900]))
def process_audio(job_id: str, file_path: str, options: dict):
    """Process audio file through Deepgram pipeline."""
    pass
```

---

## ADR-009: Speaker-Centric Document Structure

### Status

**Accepted**

### Context

When converting transcripts to Docling DOM, we must choose how to organize content: chronologically (by time) or by speaker.

### Decision

**Structure documents by speaker turns (speaker-centric), not by raw chronological order.**

### Rationale

**Comparison:**

| Structure | Example | RAG Benefit |
|-----------|---------|-------------|
| **Speaker-centric** | Speaker 1: "..." Speaker 2: "..." | Clear attribution, coherent chunks |
| **Chronological** | 00:01 "..." 00:05 "..." | Preserves flow, loses speaker context |
| **Paragraph-based** | Deepgram paragraphs as-is | Natural breaks, may split speaker turns |

**Speaker-centric advantages:**

1. **Attribution clarity**: Each chunk clearly belongs to one speaker
2. **Coherent context**: Speaker's full thought captured together
3. **Better RAG responses**: "Speaker 2 said..." is more useful than "At 14:32..."
4. **Chunking alignment**: Speaker turns are natural chunk boundaries

### Consequences

**Positive:**
- Clear speaker attribution in RAG responses
- Natural chunk boundaries
- Easier to cite specific speakers
- Coherent context within chunks

**Negative:**
- Loses strict chronological order within document
- Back-and-forth dialogue may seem disjointed
- Very long speaker turns may need sub-chunking

**Implementation:**
```python
# Docling DOM structure
Document:
  - SectionItem (speaker_id: "speaker_0", label: "Speaker 1")
    - TextItem (utterance 1, timestamps)
    - TextItem (utterance 2, timestamps)
  - SectionItem (speaker_id: "speaker_1", label: "Speaker 2")
    - TextItem (utterance 1, timestamps)
    - TextItem (utterance 2, timestamps)
```

---

## ADR-010: Deepgram Summarization v2 Over LLM Summarization

### Status

**Accepted**

### Context

Summaries improve RAG retrieval and user experience. Options for generating summaries:

1. **Deepgram Summarization v2** — Built into transcription API
2. **LLM summarization (Claude/GPT)** — Post-processing with LLM
3. **Extractive summarization** — Select key sentences algorithmically
4. **No summarization** — Let downstream handle it

### Decision

**Use Deepgram Summarization v2 for all audio summaries.**

### Rationale

| Method | Cost | Latency | Quality | Integration |
|--------|------|---------|---------|-------------|
| **Deepgram v2** | +$0.09/hr | None (parallel) | Good | Single API call |
| **Claude** | ~$0.15/hr | +10-30s | Excellent | Separate call |
| **GPT-4** | ~$0.20/hr | +10-30s | Excellent | Separate call |
| **Extractive** | Free | +1-2s | Fair | Local processing |

**Key factors:**

1. **Integration**: Summarization happens during transcription, no additional call
2. **Cost**: $0.09/hour is cheaper than LLM alternatives
3. **Latency**: Zero additional latency (processed in parallel)
4. **Quality**: Good enough for RAG context; users can request LLM summary if needed

### Consequences

**Positive:**
- No additional API calls or latency
- Cost-effective
- Consistent with single-vendor approach
- Always available (no LLM quota concerns)

**Negative:**
- Quality may be lower than LLM summaries
- Less customizable (no prompt control)
- Summary style fixed by Deepgram

**Future enhancement:**
- Optional LLM summarization can be added as a post-processing step
- User preference could trigger Claude summarization for premium quality

---

## Decision Log Summary

| ADR | Decision | Status | Impact |
|-----|----------|--------|--------|
| 001 | Deepgram Nova-2 for ASR | Accepted | Core architecture |
| 002 | Native Deepgram diarization | Accepted | Simplifies pipeline |
| 003 | Docling DOM output format | Accepted | Enables integration |
| 004 | API-based processing | Accepted | Resource efficiency |
| 005 | FFmpeg for media handling | Accepted | Format support |
| 006 | Auto long file splitting | Accepted | Robustness |
| 007 | Quality-first error handling | Accepted | User experience |
| 008 | Redis + RQ for jobs | Accepted | Consistency |
| 009 | Speaker-centric structure | Accepted | RAG quality |
| 010 | Deepgram summarization v2 | Accepted | Cost/speed |

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | December 2024 | — | Initial ADR document |

---

*— End of Document —*
