# Architecture and Structure Audit

Date: 2026-05-29
Scope: module boundaries, layering, configuration centralization, abstraction duplication, convention drift, importability.
Method: static analysis of `src/audio_processor/` and planning docs. READ-ONLY.

## Import map (production paths)

```
cli.py ............. core.config, utils.logging
api/routes.py ...... core.config, core.exceptions, core.models, services.audio_converter, utils.logging
jobs/audio_tasks.py  core.config, core.exceptions, core.models, services.audio_converter,
                     services.quality_assessor, services.deepgram_client (lazy), utils.logging
jobs/worker.py ..... core.config, jobs.audio_tasks
services/* ......... core.config, core.exceptions, core.models, utils.logging
preprocessing/* .... audio_processor.exceptions (the 36-line module) ONLY
core/* ............. core only (no upward imports)  -> direction is clean
utils/* ............ utils only                      -> direction is clean
```

Layering direction (core <- services <- jobs/api/cli) is correct. No core-imports-services and no
utils-imports-upward violations found. No circular imports found. The structural problems are
duplication and dead code, not dependency direction.

---

## ARCH-01: `preprocessing/` is a parallel, orphaned reimplementation of `services/`

Severity: High
Effort: M (delete or wire-in across 4 modules + tests, decide which is canonical)

Evidence:
- `src/audio_processor/preprocessing/vad.py:58` `detect_speech_segments` vs `src/audio_processor/services/vad_processor.py:81` `VADProcessor` (both wrap Silero VAD via torch).
- `src/audio_processor/preprocessing/quality.py:21` `check_snr` / `:62` `check_clipping` vs `src/audio_processor/services/quality_assessor.py:30` `QualityAssessor` (same SNR/clipping metrics).
- `src/audio_processor/preprocessing/ffmpeg.py:50` `convert_to_wav` / `preprocessing/loader.py:27` `load_audio` vs `src/audio_processor/services/audio_converter.py:93` `AudioConverter` and `services/audio_conditioner.py:60` `AudioConditioner`.
- No production module imports `preprocessing.*`. The only importers are tests: `tests/unit/preprocessing/test_*.py`. Confirmed via `git grep preprocessing -- 'src/**/*.py'` (matches are docstrings/config descriptions only).
- ADR-002 and `docs/planning/tech-spec.md:110-111` name `AudioConditioner` and `VADProcessor` (the `services/` classes) as canonical. `preprocessing/` is named in neither.

Recommendation: Pick one home. Since the wired pipeline and the specs use `services/`, delete `preprocessing/` (and its tests) or formally demote it to a documented low-level helper layer that `services/` actually calls.

---

## ARCH-02: Two exception modules; `preprocessing/` uses the orphaned one

Severity: Medium
Effort: S

Evidence:
- `src/audio_processor/exceptions.py` (36 lines) defines `AudioLoadError`, `FfmpegConversionError`, both subclassing `ProjectBaseError`.
- `src/audio_processor/core/exceptions.py` (545 lines) is the canonical hierarchy; CLAUDE.md "Exception Hierarchy" points all imports at `core.exceptions`.
- Only `preprocessing/ffmpeg.py:21` and `preprocessing/loader.py:16` import the top-level module; all `services/*` and `jobs/*` import `core.exceptions`. The split tracks exactly the ARCH-01 dead/live divide.

Recommendation: Move `AudioLoadError` and `FfmpegConversionError` into `core/exceptions.py` and delete `src/audio_processor/exceptions.py`, so there is one exception home as CLAUDE.md requires.

---

## ARCH-03: Spec-mandated VAD and conditioning are not wired into the pipeline

Severity: High
Effort: M

Evidence:
- ADR-002 ("Decision") mandates VAD silence removal and RMS normalization before ASR.
- The live pipeline `jobs/audio_tasks.py:99-136` instantiates only `AudioConverter` and `QualityAssessor`, then calls Deepgram (`:163`). No `AudioConditioner`, no `VADProcessor`.
- `AudioConditioner`, `VADProcessor`, `DOMBuilder`, `TranscriptFormatter` have zero production callers; only `services/__init__.py` re-exports them. Confirmed via `git grep` excluding self and `__init__`.

Recommendation: Either integrate `AudioConditioner`/`VADProcessor` into `audio_tasks.py` as ADR-002 specifies, or update the ADR to record that conditioning/VAD are deferred so the code and the accepted decision stop disagreeing.

---

## ARCH-04: Duplicated config values; `preprocessing/` hardcodes what `services/`+config own

Severity: Medium
Effort: S

Evidence:
- `core/config.py:103-163` centralizes `audio_target_sample_rate`, `audio_target_rms_db`, `vad_threshold`, `quality_snr_*_db`, `quality_max_clipping_ratio`, etc.
- `services/*` correctly read these: e.g. `services/audio_conditioner.py:94-99`, `services/quality_assessor.py:62-67`.
- `preprocessing/` bypasses config with module-level constants: `preprocessing/loader.py:21` `TARGET_SAMPLE_RATE = 16_000`, `preprocessing/quality.py:62` `threshold = 0.99`. Same magnitudes, no link to `settings`. Two sources of truth for the same tuning numbers.

Recommendation: If `preprocessing/` survives ARCH-01, route its constants through `core.config.settings`; otherwise removing the package resolves this.

---

## ARCH-05: Env reads outside `core/config.py`

Severity: Low
Effort: S

Evidence:
- CLAUDE.md names `core/config.py` (Pydantic Settings) as the configuration home.
- Direct `os.getenv`/`os.environ` outside it: `core/cache.py:81` (`REDIS_URL`), `core/sentry.py:87,94-97` (`SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `ENVIRONMENT`, `SENTRY_RELEASE`). `jobs/worker.py:126` is commented example code (`# noqa: ERA001`), not active.

Recommendation: Promote `REDIS_URL` and the Sentry vars to `Settings` fields and read them through `settings`, keeping one config surface.

---

## ARCH-06: Heavy scientific libs imported at module top level

Severity: Medium
Effort: M

Evidence:
- `numpy`, `librosa`, `torch`, `scipy`, `soundfile` are runtime (not `TYPE_CHECKING`) top-level imports in every `services/` audio module and every `preprocessing/` module: `services/vad_processor.py:15-18`, `services/quality_assessor.py:14-16`, `services/audio_conditioner.py:16-18`, `preprocessing/loader.py:12-14`, `preprocessing/quality.py:12-13`, `preprocessing/vad.py:16`.
- `pyproject.toml:80` places these behind optional extras (`[project.optional-dependencies]`, `torch`/`librosa`/`scipy`/`soundfile` at lines 127-163).
- Effect: `import audio_processor.services` (triggered by `api/routes.py:34` and `jobs/audio_tasks.py:28`) hard-fails without the extras installed. The top-level package `audio_processor/__init__.py` is clean and importable, but any consumer of services is not. Layering claim "audio behind extras" is contradicted by eager imports. (Could not exercise at runtime: package not installed in audit env; finding is from static import inspection.)

Recommendation: Defer heavy imports into method bodies or `TYPE_CHECKING` plus lazy local import (the deepgram pattern at `jobs/audio_tasks.py:159` already does this), so `services` is importable without optional extras and the extras boundary is real.

---

## ARCH-07: Template residue: `utils/financial.py`, empty `middleware/`, generic financial guidance

Severity: Low
Effort: S

Evidence:
- `src/audio_processor/utils/financial.py` ("Financial utilities module") is unused; no `src/` module imports it. The project's actual money handling (Deepgram cost) lives in `services/deepgram_client.py:48-50` and `core/models.py:218` using `Decimal` directly, not via this util.
- `src/audio_processor/middleware/__init__.py` is empty; no middleware exists and nothing imports the package.
- CLAUDE.md carries generic "Payment/Financial" RAD categories and a Payment example, irrelevant to an audio tool.

Recommendation: Remove `utils/financial.py` and the empty `middleware/` package, or replace `financial.py` with the Deepgram cost helpers if a shared money util is wanted; trim payment-specific boilerplate from project docs.

---

## Clean areas

- Dependency direction (core <- services <- jobs/api/cli, utils leaf) is correct; no upward or circular imports.
- `core/config.py` is a single well-structured Settings class (30 typed fields) and `services/` consume it correctly.

---

## Summary table

| ID | Title | Severity | Effort | Files | Evidence | Recommendation | CVE |
|----|-------|----------|--------|-------|----------|----------------|-----|
| ARCH-01 | `preprocessing/` is parallel orphaned reimplementation of `services/` | High | M | preprocessing/{vad,quality,ffmpeg,loader}.py, services/{vad_processor,quality_assessor,audio_converter,audio_conditioner}.py | preprocessing/vad.py:58 vs services/vad_processor.py:81; no prod importer of preprocessing.*; tech-spec.md:110-111 names services classes | Pick one home; delete `preprocessing/` or wire it under `services/` | n/a |
| ARCH-02 | Two exception modules; dead one used by `preprocessing/` | Medium | S | exceptions.py, core/exceptions.py | exceptions.py:1-36; preprocessing/ffmpeg.py:21, loader.py:16 import it; all else uses core.exceptions | Fold the two classes into core/exceptions.py, delete top-level module | n/a |
| ARCH-03 | Spec-mandated VAD/conditioning not wired into pipeline | High | M | jobs/audio_tasks.py, services/{audio_conditioner,vad_processor}.py | audio_tasks.py:99-136 uses only converter+assessor; ADR-002 mandates VAD+RMS; conditioner/VAD have zero prod callers | Integrate per ADR-002 or amend ADR to mark deferred | n/a |
| ARCH-04 | Duplicated config values; preprocessing hardcodes them | Medium | S | core/config.py, preprocessing/loader.py, preprocessing/quality.py | config.py:103-163 owns values; loader.py:21, quality.py:62 hardcode 16000/0.99 | Route preprocessing constants through settings, or remove with ARCH-01 | n/a |
| ARCH-05 | Env reads outside core/config.py | Low | S | core/cache.py, core/sentry.py | cache.py:81; sentry.py:87,94-97 | Add Settings fields, read via settings | n/a |
| ARCH-06 | Heavy libs imported at module top; services not importable without extras | Medium | M | services/*, preprocessing/*, pyproject.toml | services/vad_processor.py:15-18 et al; pyproject.toml:80,127-163 extras | Lazy-import heavy libs (mirror deepgram pattern audio_tasks.py:159) | n/a |
| ARCH-07 | Template residue: financial util, empty middleware, payment docs | Low | S | utils/financial.py, middleware/__init__.py | financial.py unused; middleware/__init__.py empty; real cost logic in deepgram_client.py:48-50 | Remove unused util + empty package; trim payment boilerplate | n/a |
