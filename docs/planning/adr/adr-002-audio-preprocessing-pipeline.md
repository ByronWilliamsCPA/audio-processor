---
title: "ADR-002: Audio Signal Conditioning and Preprocessing Pipeline"
schema_type: planning
status: published
owner: core-maintainer
purpose: "Document the audio signal conditioning pipeline required before ASR transcription."
tags:
  - adr
component: Development-Tools
source: "Audio preprocessing research paper analysis"
---

> **Status**: Accepted
> **Date**: 2025-12-04
> **Supersedes**: None
> **Related**: [ADR-001](./adr-001-initial-architecture.md)

## TL;DR

Implement a comprehensive audio signal conditioning pipeline using librosa, pydub, and FFmpeg to standardize all input audio to optimal ASR parameters (16kHz mono PCM) with quality assessment, Voice Activity Detection (VAD), and RMS normalization before Deepgram transcription.

## Context

### Problem

Raw audio files vary dramatically in technical parameters (sampling rate, bit depth, channels, codec, noise levels). The current architecture (ADR-001) sends audio directly to Deepgram, but optimal ASR performance requires standardized signal conditioning. Without preprocessing:

- **Sampling Rate Mismatches**: 44.1kHz or 48kHz audio wastes bandwidth and can introduce aliasing artifacts
- **Stereo Channel Interference**: Phase cancellation or channel imbalance degrades transcription
- **Dynamic Range Issues**: Overly quiet or loud audio affects ASR confidence scores
- **Silence Segments**: Non-speech regions trigger ASR hallucinations and waste API costs
- **Noise Artifacts**: Background noise, HVAC hum, or digital artifacts corrupt transcription

### Constraints

- **Nyquist-Shannon Theorem**: 16kHz sampling provides 8kHz bandwidth (sufficient for human speech 85Hz-8kHz)
- **ASR Model Expectations**: Deepgram Nova-2 and Whisper pre-trained on 16kHz mono audio
- **Computational Efficiency**: Preprocessing must complete in < 10% of audio duration (< 6 minutes for 1-hour file)
- **Lossless Requirements**: Cannot introduce artifacts that permanently corrupt the signal

### Significance

Audio preprocessing quality directly determines:

- **Word Error Rate (WER)**: Poor preprocessing can increase WER from 2.5% to 8%+
- **API Costs**: Silence segments waste money on transcribing non-speech
- **Hallucination Rate**: Improper signal conditioning triggers phantom transcription
- **Speaker Diarization Accuracy**: Channel mixing destroys spatial separation needed for speaker ID

## Decision

**Implement a mandatory audio signal conditioning pipeline that standardizes all input to 16kHz mono 16-bit PCM WAV format with Voice Activity Detection (VAD) and RMS normalization before ASR processing.**

### Rationale

1. **Signal Standardization**: Eliminates codec/format variations that cause inconsistent ASR behavior
2. **Bandwidth Optimization**: 16kHz is theoretically sufficient for human speech (Nyquist theorem)
3. **VAD Filtering**: Removes silence to reduce API costs and prevent hallucinations
4. **Loudness Normalization**: RMS normalization to -20dBFS ensures consistent confidence scores
5. **Channel Strategy**: Mono downmix prevents phase cancellation while preserving speech intelligibility

## Options Considered

### Option 1: Comprehensive Preprocessing Pipeline (librosa + pydub) ✓

**Preprocessing Steps**:

1. **Format Detection & Validation** (magic bytes, duration check)
2. **Codec Conversion** (to WAV PCM for lossless manipulation)
3. **Resampling** (polyphase filter to 16kHz)
4. **Channel Reduction** (stereo → mono via averaging or energy-based selection)
5. **RMS Normalization** (to -20dBFS target)
6. **Voice Activity Detection** (Silero VAD to remove silence)
7. **Quality Assessment** (SNR, clipping ratio, silence ratio metrics)

**Pros**:

- ✅ Maximizes ASR accuracy through optimal signal conditioning
- ✅ Reduces API costs by removing silence segments
- ✅ Provides quality metrics for user feedback
- ✅ Prevents hallucinations in silence regions
- ✅ Enables advanced channel separation strategies

**Cons**:

- ❌ Adds 5-10% processing time overhead
- ❌ Increases implementation complexity
- ❌ Requires additional Python dependencies (librosa, pydub, silero-vad)
- ❌ Temporary storage needed for intermediate formats

### Option 2: Minimal FFmpeg-Only Conversion

**Preprocessing Steps**:

1. Convert to 16kHz mono MP3 via FFmpeg
2. Send directly to Deepgram

**Pros**:

- ✅ Minimal implementation complexity
- ✅ Fast processing (< 1% overhead)

**Cons**:

- ❌ No VAD = wasted API costs on silence
- ❌ No quality assessment = no user warnings
- ❌ No RMS normalization = variable confidence scores
- ❌ Simple channel averaging can cause phase cancellation

### Option 3: Deepgram-Native Preprocessing

**Approach**: Rely entirely on Deepgram's internal preprocessing

**Pros**:

- ✅ Zero implementation effort
- ✅ No processing time overhead

**Cons**:

- ❌ No control over preprocessing parameters
- ❌ Cannot optimize for cost (silence removal)
- ❌ No quality feedback to users
- ❌ Vendor lock-in to Deepgram's black-box preprocessing

## Consequences

### Positive

- ✅ **Higher WER Accuracy**: Optimal signal conditioning improves transcription from 2.9% → 2.5% WER
- ✅ **Cost Reduction**: VAD removes 10-30% of audio (silence), saving $0.03-$0.10/hour
- ✅ **Quality Transparency**: Users receive quality warnings before expensive transcription
- ✅ **Hallucination Prevention**: Silence removal eliminates phantom phrases
- ✅ **Consistent Performance**: Standardization reduces variability across diverse audio sources

### Trade-offs

- ⚠️ **Processing Overhead**: Adds 30-60 seconds preprocessing time per hour of audio (0.8-2% overhead)
- ⚠️ **Storage Requirements**: Intermediate WAV files require 10MB/min (cleaned up after processing)
- ⚠️ **Complexity**: Requires expertise in signal processing for maintenance

### Technical Debt

- **Advanced Denoising**: Phase 2 may add Facebook Denoiser for noisy environments (conservative settings to avoid musical noise artifacts)
- **Channel Separation**: Phase 2 may add intelligent channel analysis to process stereo interviews as dual-mono
- **Adaptive VAD Thresholds**: Phase 2 may tune VAD sensitivity based on detected noise floor

## Implementation

### Components Affected

1. **AudioConditioner Service** (NEW):
   - Format detection and validation
   - Resampling with polyphase filters
   - Channel reduction strategies
   - RMS normalization to -20dBFS
   - Temporary file management

2. **VADProcessor Service** (NEW):
   - Silero VAD model integration
   - Silence segment detection and removal
   - Speech probability threshold configuration
   - Timeline reconstruction after VAD

3. **QualityAssessor** (UPDATED - from ADR-001):
   - SNR calculation (via librosa)
   - Silence ratio measurement
   - Clipping detection (samples at max amplitude)
   - Composite quality score (0.0-1.0)
   - Quality warning generation

4. **AudioProcessor** (UPDATED - from ADR-001):
   - Insert conditioning pipeline before Deepgram call
   - Pipeline flow: Validate → Condition → VAD → Quality → Deepgram

### Technology Stack

```python
# Signal Processing
librosa==0.10+         # Polyphase resampling, SNR calculation
pydub==0.25+           # High-level audio manipulation, RMS normalization
ffmpeg-python==0.2+    # Robust codec conversion

# Voice Activity Detection
silero-vad==4.0+       # Pre-trained VAD model (CPU-efficient)

# Validation
soundfile==0.12+       # Audio file I/O and validation
```

### Processing Pipeline

```python
# Pseudocode for preprocessing pipeline
async def preprocess_audio(input_path: Path) -> PreprocessedAudio:
    # 1. Validate and detect format
    audio_info = await validate_audio(input_path)

    # 2. Convert to WAV PCM (lossless intermediate)
    wav_path = await ffmpeg_convert_to_wav(input_path)

    # 3. Load with librosa for signal analysis
    audio, sr = librosa.load(wav_path, sr=None, mono=False)

    # 4. Assess quality BEFORE modifications
    quality = assess_quality(audio, sr)

    # 5. Resample to 16kHz if needed
    if sr != 16000:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
        sr = 16000

    # 6. Convert stereo to mono (energy-based channel selection)
    if audio.ndim == 2:
        audio = smart_mono_mix(audio)

    # 7. RMS normalization to -20dBFS
    audio = normalize_rms(audio, target_dbfs=-20.0)

    # 8. Voice Activity Detection (remove silence)
    speech_segments, vad_timeline = silero_vad(audio, sr)
    audio_filtered = concatenate_speech_segments(audio, speech_segments)

    # 9. Save conditioned audio
    output_path = save_wav(audio_filtered, sr=16000, bit_depth=16)

    return PreprocessedAudio(
        path=output_path,
        original_duration_ms=len(audio) / sr * 1000,
        processed_duration_ms=len(audio_filtered) / sr * 1000,
        quality=quality,
        vad_removed_percent=(1 - len(audio_filtered)/len(audio)) * 100
    )
```

### Testing Strategy

- **Unit Tests**:
  - Resampling accuracy (compare output spectrum to reference)
  - RMS normalization correctness (verify target dBFS)
  - VAD precision/recall on synthetic audio (speech + silence)
  - Channel reduction phase cancellation detection

- **Integration Tests**:
  - End-to-end pipeline with diverse audio formats (MP3, M4A, WAV, FLAC)
  - Processing time validation (< 10% of audio duration)
  - Quality assessment accuracy on reference audio with known SNR

- **Regression Tests**:
  - WER comparison: preprocessed vs. raw audio (expect 10-20% WER improvement)
  - Cost comparison: VAD-filtered vs. full audio (expect 10-30% savings)

## Validation

### Success Criteria

- [ ] Resampling maintains > 99% spectral fidelity in speech band (300Hz-3.4kHz)
- [ ] RMS normalization achieves -20dBFS ± 2dB
- [ ] VAD removes > 80% of silence without clipping speech onset/offset
- [ ] Preprocessing completes in < 10% of audio duration (< 6min for 1hr)
- [ ] WER improves by 10-20% compared to raw audio baseline
- [ ] API cost reduces by 10-30% through VAD filtering

### Performance Targets

| Metric                      | Target                  | Measurement Method           |
|-----------------------------|-------------------------|------------------------------|
| Preprocessing Overhead      | < 10% audio duration    | Wall-clock timing            |
| VAD False Negative Rate     | < 5%                    | Manual annotation comparison |
| RMS Normalization Accuracy  | ± 2dB                   | Peak analysis                |
| Resampling Quality          | > 99% spectral fidelity | FFT comparison               |
| Cost Reduction              | 10-30%                  | API billing comparison       |

### Review Schedule

- **Initial**: Week 2 (Phase 1) - Validate preprocessing quality with sample audio
- **Mid-Implementation**: Week 3 - WER comparison preprocessed vs. raw
- **Ongoing**: Monthly review of quality warnings and user feedback

## Related

- [ADR-001](./adr-001-initial-architecture.md): Deepgram Nova-2 ASR architecture
- [Tech Spec](../tech-spec.md): AudioConditioner and VADProcessor specifications
- [Roadmap](../roadmap.md): US-009 Implement Audio Preprocessing Pipeline
