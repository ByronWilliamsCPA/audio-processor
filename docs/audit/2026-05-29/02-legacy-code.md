# Legacy Code Patterns Audit

Repo: ByronWilliamsCPA/audio-processor
Date: 2026-05-29
Scope: src/audio_processor/ (~7450 LOC). READ-ONLY review.
Auditor domain: legacy code patterns.

## Headline

The source is modern. Type hints use builtin generics and `X | None`, datetimes
use `datetime.now(UTC)` (not the deprecated `utcnow`), there is no `os.path`,
no `pkg_resources`, no `asyncio.get_event_loop`, and no pydantic v1 patterns.
The real legacy debt is structural: two overlapping exception modules, unmodified
cookiecutter template scaffolding (demo background tasks, an empty `financial.py`),
a dead function parameter, one commented-out code block, and `vulture` is not in
the toolchain so dead code is not caught in CI.

---

## LEG-01: Duplicate exception modules with a thin re-parenting shim

Severity: Medium
Effort: M (move 2 classes, update 4 import sites incl. 2 tests, re-export for compat)

Evidence:
- `src/audio_processor/exceptions.py` (36 lines) defines `AudioLoadError` and
  `FfmpegConversionError`, both inheriting `ProjectBaseError` imported from
  `core/exceptions.py:10`.
- `src/audio_processor/core/exceptions.py` (545 lines) is the canonical hierarchy
  (`ProjectBaseError` plus `ValidationError`, `ResourceNotFoundError`,
  `ConfigurationError`, etc.) and is what `core/__init__.py:4` re-exports.
- Both modules are imported in production:
  - top-level: `preprocessing/ffmpeg.py:21`, `preprocessing/loader.py:16`
    (+ tests `test_ffmpeg.py:11`, `test_loader.py:11`)
  - core: `api/routes.py:26`, `jobs/audio_tasks.py:21`, and 6 service modules.
- The top-level module is not a pure legacy shim; it holds the only two
  preprocessing-specific exceptions and is the active import path for the
  preprocessing package. The split is by domain, not by deprecation, but it is
  undocumented and easy to mistake for a duplicate.

Recommendation: Either fold the two preprocessing exceptions into
`core/exceptions.py` (canonical single source) keeping a re-export in
`exceptions.py` for back-compat, or add a module docstring note clarifying that
`exceptions.py` is the public preprocessing surface. Pick one home and document it.

---

## LEG-02: Cookiecutter template demo tasks left in worker.py

Severity: Medium
Effort: S (delete 3 functions and their registration entries)

Evidence:
- `jobs/worker.py:71` `example_background_task` simulates work with
  `asyncio.sleep(2)` and writes a fake `task_result:{user_id}` to Redis.
- `jobs/worker.py:102` `send_email_task` is a stub: `asyncio.sleep(1)` then
  returns `{"status": "sent"}`. It accepts `body` but never uses it
  (`worker.py:106`, flagged `# noqa: ARG001`, vulture 100% confidence).
- `jobs/worker.py:138` `process_file_upload` is a generic file-upload demo
  unrelated to the audio pipeline.
- All three are registered live in `WorkerSettings.functions`
  (`worker.py:246-248`), so they are deployable no-op/fake handlers, not just
  dead code.

Recommendation: Remove the three template demo tasks and their registrations;
keep only `process_audio_job` and `cleanup_old_data`. A stubbed `send_email_task`
that reports success without sending is a correctness hazard if ever called.

---

## LEG-03: Empty template stub utils/financial.py

Severity: Low
Effort: S (delete file, drop from REUSE/packaging if listed)

Evidence:
- `src/audio_processor/utils/financial.py` is 1 line: a module docstring
  `"""Financial utilities module."""` and nothing else (34 bytes).
- No imports of it anywhere; the only `Decimal` usage in the project lives in
  `core/models.py` and `services/deepgram_client.py` for cost math and does not
  reference this module.
- This is unmodified cookiecutter scaffolding for a financial template,
  irrelevant to an audio pipeline.

Recommendation: Delete the file. It is template residue with zero references.

---

## LEG-04: Dead function parameter include_correlation in setup_logging

Severity: Low
Effort: S (remove param or implement; update docstring + 1 call example)

Evidence:
- `utils/logging.py:42` declares `include_correlation: bool = True`.
- The parameter is referenced only in the docstring (`logging.py:56`) and the
  doctest example (`logging.py:64`); it is never read in the function body.
  Confirmed by grep: no body reference.
- Vulture flags it at 100% confidence (`utils/logging.py:42`).

Recommendation: Either wire the flag into the structlog processor chain (it
promises correlation-ID inclusion) or remove the parameter. As written it is a
false promise to callers.

---

## LEG-05: Commented-out SendGrid integration block

Severity: Low
Effort: S (delete 4 lines)

Evidence:
- `jobs/worker.py:124-127`: four commented import/usage lines for SendGrid, each
  tagged `# noqa: ERA001` to suppress the commented-code linter:
  - `#   from sendgrid import SendGridAPIClient  # noqa: ERA001`
  - `#   sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))  # noqa: ERA001`
- This is the only commented-out code in src (ruff ERA is otherwise clean across
  the tree). It rides along with the demo `send_email_task` (see LEG-02).

Recommendation: Delete the block with the demo task. If email is a real roadmap
item, capture it in an issue, not as suppressed commented code.

---

## LEG-06: vulture not in the dev toolchain

Severity: Low
Effort: S (add dev dependency + optional pre-commit/CI step)

Evidence:
- `uv run vulture` failed: `Failed to spawn: vulture ... No such file or directory`.
  Had to run via `uvx vulture` ephemerally.
- `pyproject.toml` lists ruff, basedpyright, bandit, pip-audit but no vulture.
- A run at `--min-confidence 60` produced ~85 candidates; most are framework
  false positives (FastAPI route handlers in `api/routes.py`, pydantic
  `model_config`/field declarations in `core/models.py`, public CLI/service
  methods invoked dynamically). Genuine hits cross-referenced above:
  `body` (LEG-02), `include_correlation` (LEG-05/04). The high false-positive
  rate is expected for FastAPI+pydantic and argues for a tuned whitelist.

Recommendation: Add `vulture` as a dev dependency with a committed whitelist
(or `--min-confidence 80` plus per-decorator ignores) so dead code is caught
without drowning in framework false positives.

---

## LEG-07: from __future__ import annotations missing in 7 of 31 source files

Severity: Low
Effort: S (add one import line per file)

Evidence:
- 24/31 src files carry `from __future__ import annotations`; missing in:
  `__init__.py`, `cli.py`, `core/__init__.py`, `middleware/__init__.py`,
  `utils/__init__.py`, `utils/financial.py`, `utils/logging.py`.
- House standard (CLAUDE.md) lists `from __future__ import annotations` as
  required. Several misses are trivial `__init__.py` files; `cli.py` and
  `utils/logging.py` are the substantive ones.
- Note `financial.py` is slated for deletion (LEG-03), so 6 files effectively.

Recommendation: Add the future import to the substantive modules (`cli.py`,
`utils/logging.py`) for consistency with the stated standard; package
`__init__.py` files are low value but cheap to align.

---

## Clean areas (one line each)

- Deprecated stdlib/library APIs: none found. No `datetime.utcnow`, `pkg_resources`,
  `asyncio.get_event_loop`; datetimes use `datetime.now(UTC)`.
- Pydantic v1 patterns: none. pydantic `>=2.0.0` pinned (2.12.5 installed); no
  `.dict()`, `.parse_obj`, `parse_raw`, or `class Config` (the one `class Config`
  grep hit, `core/exceptions.py:101`, is `class ConfigurationError`, a false match).
- typing.List/Dict/Optional/Union/Tuple/Set in type position: none. All `Optional`
  grep hits are docstring prose; type hints use `list`/`dict` and `X | None`.
- Pre-f-string formatting: only two `%s` uses (`core/sentry.py:157,165`), both
  correct lazy-logging format args, not string interpolation.
- os.path: none (pathlib throughout).
- Vendored copies that should be dependencies: none. No vendor/third_party dirs,
  no non-Python files tracked under src.
- Resolved feature flags never removed: none. The `enable_*` flags
  (diarization/summarization/tracing/profiling) are live runtime options, not
  stale toggles.

---

## Summary table

| ID | Title | Severity | Effort | Files | Evidence | Recommendation | CVE |
|----|-------|----------|--------|-------|----------|----------------|-----|
| LEG-01 | Duplicate exception modules / re-parenting shim | Medium | M | exceptions.py; core/exceptions.py | exceptions.py:10; both imported (ffmpeg.py:21, loader.py:16 vs routes.py:26 + 6 services) | Pick one home for preprocessing exceptions, re-export or document | n/a |
| LEG-02 | Template demo tasks in worker.py | Medium | S | jobs/worker.py | example_background_task:71, send_email_task:102 (stub, unused body:106), process_file_upload:138, registered :246-248 | Delete demo tasks + registrations; stub email returning success is a hazard | n/a |
| LEG-03 | Empty stub utils/financial.py | Low | S | utils/financial.py | 1 line, 34 bytes, zero references | Delete template residue | n/a |
| LEG-04 | Dead param include_correlation | Low | S | utils/logging.py | declared :42, only in docstring :56/:64, vulture 100% | Wire into processor chain or remove | n/a |
| LEG-05 | Commented-out SendGrid block | Low | S | jobs/worker.py | lines 124-127, 4x noqa ERA001 | Delete with LEG-02; track email as issue | n/a |
| LEG-06 | vulture absent from toolchain | Low | S | pyproject.toml | uv run vulture fails; not a dev dep | Add vulture dev dep + whitelist/min-confidence 80 | n/a |
| LEG-07 | Missing future annotations in 7 files | Low | S | __init__.py x4, cli.py, financial.py, utils/logging.py | 24/31 have it; standard requires it | Add import to cli.py + logging.py at minimum | n/a |
