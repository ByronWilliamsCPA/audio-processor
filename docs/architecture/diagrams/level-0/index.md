---
title: "Level 0: Pipeline Context"
schema_type: common
status: published
owner: core-maintainer
purpose: "Pointer from the diagrams tree to the shared Foundry pipeline Level 0 page."
tags:
  - architecture
  - pipeline
---

The Level 0 view is the shared Foundry pipeline page, identical in all five pipeline repositories:
[Pipeline Level 0](../../pipeline-level-0.md). It shows how Ingest, Prepare-Doc, Prepare-Audio, Unify, and Chunk
link together and where the pipeline ends (at chunks).

This repository is the **Prepare-Audio** box (`audio-processor`): the audio track between Ingest and Unify. It
transcribes audio and video with speaker diarization. The next level down is [Level 1](../level-1/index.md).
