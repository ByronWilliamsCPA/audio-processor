---
schema_type: common
title: "Architecture Overview"
status: published
owner: core-maintainer
purpose: "Canonical home for architecture reference material: ADRs, system diagrams, and component descriptions."
tags:
  - architecture
  - documentation
---

This directory is the canonical home for architecture reference material:
Architecture Decision Records (ADRs), system diagrams, and component
descriptions.

## Architecture Decision Records

ADRs for this project live in two locations:

| Location | Contents |
|----------|----------|
| [`docs/planning/adr/`](../planning/adr/) | Accepted ADRs authored during initial planning (ADR-001, ADR-002) |
| [`docs/ADRs/`](../ADRs/) | Draft and template ADRs carried in from the project template |

### Accepted ADRs

- [ADR-001: Initial Architecture - Deepgram-Centric Audio Processing](../planning/adr/adr-001-initial-architecture.md)
  Selects Deepgram Nova-2 as the exclusive ASR engine with native diarization
  and Docling DOM output for RAG pipeline integration.

- [ADR-002: Audio Signal Conditioning and Preprocessing Pipeline](../planning/adr/adr-002-audio-preprocessing-pipeline.md)
  Defines the mandatory audio preprocessing pipeline (librosa, pydub, FFmpeg,
  Silero VAD) that standardizes all input to 16kHz mono PCM before
  transcription.

## Adding a New ADR

1. Copy `docs/ADRs/draft_ADR.md` (or `docs/draft_ADR.md`) as a starting point.
2. Name the file `adr-NNN-short-title.md` and place it in `docs/planning/adr/`.
3. Set `status: Proposed` in the front matter; update to `Accepted` after review.
4. Add a row to the table above once accepted.

## System Context

The audio processor is a pipeline service that:

1. Accepts raw audio files via an API endpoint or CLI.
2. Validates and preprocesses audio to 16kHz mono PCM (ADR-002).
3. Sends conditioned audio to Deepgram Nova-2 for transcription and
   diarization (ADR-001).
4. Converts the Deepgram response to Docling DOM format for downstream
   RAG pipeline consumption.

For detailed component specifications, see
[`docs/planning/tech-spec.md`](../planning/tech-spec.md).
