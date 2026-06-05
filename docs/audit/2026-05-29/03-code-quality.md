# Code Quality and Maintainability Audit

Repo: ByronWilliamsCPA/audio-processor
Date: 2026-05-29
Scope: code quality and maintainability, read-only.
Auditor domain: senior engineer review.

src/audio_processor ~7450 LOC, tests ~7722 LOC. 178 analyzed blocks. Average cyclomatic
complexity grade A (3.69). All files maintainability index grade A. No bare blanket
ignores. Zero TODO/FIXME in src and tests.

Tooling note: the sandbox has no synced virtualenv (numpy, fastapi, redis, deepgram,
torch, librosa, scipy, soundfile, arq, anyio, sentry_sdk, docling not installed).
basedpyright and pytest could only run partially. Findings affected by this are tagged.

---

## QUAL-01: basedpyright emits 626 warnings in src, contradicting the documented strict-mode-clean claim

Severity: Medium
Effort: L (week+; warnings span the whole untyped third-party surface)

Evidence:
`uv run basedpyright src/` -> `59 errors, 626 warnings, 0 notes`.
Of the 59 errors, 42 are `reportMissingImports` caused by the un-synced sandbox
(anyio, arq, deepgram, docling_core, fastapi, librosa, numpy, redis, scipy,
sentry_sdk, soundfile, torch). Those 42 are environment artifacts, not real defects.
The remaining 17 errors and the 626 warnings are real:

```
error rules: reportMissingImports 42, reportUntypedFunctionDecorator 7, reportInvalidTypeForm 10
warning rules:
  242 reportUnknownMemberType
  176 reportUnknownVariableType
  103 reportUnknownArgumentType
   60 reportAny
   34 reportUnknownParameterType
    6 reportExplicitAny
    4 reportImplicitStringConcatenation
    1 reportMissingTypeArgument
```

CLAUDE.md states "BasedPyright type checking (strict mode)" as a passing quality gate
and "Address ALL type checker warnings, not just errors." 626 unsuppressed warnings is
a systemic gap against that standard. The bulk (555 of 626) is `reportUnknown*` from
untyped third-party libs (redis.asyncio, librosa, numpy member access, sentry SDK).

Recommendation: Re-run `uv run basedpyright src/` against a fully synced env to remove
the 42 import errors and confirm the true count. Then either (a) lower the per-rule
severity for `reportUnknown*` to `none`/`information` in `[tool.basedpyright]` with a
documented rationale, or (b) wrap the untyped libs in thin typed adapters so the
warnings disappear at source. Do not paper over with more inline ignores. Reconcile the
CLAUDE.md "strict mode clean" claim with reality.

---

## QUAL-02: Duplicated audio-load helper across three services and the loader

Severity: Medium
Effort: S (<1day; extract one shared function)

Evidence: the soundfile-then-librosa fallback idiom is copy-pasted near-verbatim:
- src/audio_processor/services/quality_assessor.py:166-173
- src/audio_processor/services/audio_conditioner.py:233-242
- src/audio_processor/services/vad_processor.py:177, :288
- src/audio_processor/preprocessing/loader.py:92-99

quality_assessor.py:166-170 and audio_conditioner.py:233-241 are token-identical except
for a comment:
```python
try:
    audio, sample_rate = sf.read(str(file_path), dtype="float64")
except RuntimeError:
    audio, sample_rate = librosa.load(str(file_path), sr=None, mono=False)
    if audio.ndim > 1:
        audio = audio.T
```
There is already a loader module (preprocessing/loader.py) that does the same thing, so
the services reimplement existing logic, violating the project "Reuse First" principle.

Recommendation: Extract one `load_audio(path, dtype) -> tuple[NDArray, int]` (reuse or
extend preprocessing/loader.py) and call it from the three services. Removes ~4 copies
and the per-copy `# pyright: ignore[reportReturnType]` at audio_conditioner.py:242.

---

## QUAL-03: 109 inline type/pyright ignores concentrated on two untyped dependency boundaries, none with prose justification

Severity: Medium
Effort: M (few days; root-cause is two libraries)

Evidence: `git grep -nE "type: ?ignore|pyright: ?ignore" -- 'src/*.py'` -> 109 hits, all
rule-coded (no bare `# type: ignore`). Distribution by file:
```
 36 core/cache.py
 24 core/sentry.py
 14 jobs/worker.py
  9 services/deepgram_client.py
  8 services/dom_builder.py
  4 services/audio_converter.py
  3 services/vad_processor.py   3 jobs/audio_tasks.py
  2 cli.py   2 api/routes.py
  1 each: quality_assessor, audio_conditioner, core/models, core/exceptions
```
Two root causes dominate:
- redis.asyncio untyped stubs: every `type: ignore[call-arg]` in cache.py is on a
  structlog logger call (cache.py:95,168,172,185,...) and every `reportUnknown*`/
  `reportAny` is on a redis call (cache.py:166,255,299,327,453-464).
- sentry_sdk dict access: sentry.py:191-235 tags 20+ lines as `reportAny`.

These are individually defensible (third-party gaps) but none carries an inline reason,
which CLAUDE.md requires ("If a finding is a false positive, document WHY with inline
comments"). 60 of them are sprawled across single expressions (cache.py:455-464 has the
hit-rate dict tagged on 9 consecutive lines).

Recommendation: Collapse the per-line ignores at their source. For structlog, type the
logger once (`logger: structlog.stdlib.BoundLogger`) to kill the `call-arg` cluster. For
redis, add a typed wrapper or `redis[hiredis]` type stubs. For each remaining block, add
a one-line `# reason:` comment per the project standard. This shrinks the 109 toward the
~20 genuinely irreducible cases.

---

## QUAL-04: Test suite cannot be collected or coverage-measured without optional extras; 14 of ~21 modules fail import

Severity: Medium
Effort: S (<1day to document and add a CI-vs-local note; env-dependent)

Evidence:
`uv run pytest --cov=src -q` -> `pytest: error: unrecognized arguments: --cov` because
pytest-cov is not installed in this sandbox.
`uv run pytest -o addopts="" --collect-only` -> `80 tests collected, 14 errors during
collection` (test_api, test_audio_services, test_cache, test_jobs_init, test_models,
test_phase2_services, test_routes, test_sentry, test_service_coverage, test_worker, and
others all ERROR on import of missing deps).
Total test functions present: 458 (`git grep -cE "def test_"`). Only 80 collectable here.

This is primarily an environment artifact, not a defect in the tests. But it means the
80% coverage gate (pyproject.toml:548 `--cov-fail-under=80`) cannot be verified outside a
fully synced env, and a developer running `uv run pytest` without all extras gets a wall
of import errors rather than skips.

Recommendation: Run the gate in CI with `uv sync --all-extras` (already documented) and
confirm the actual coverage number there. Optionally guard heavy-dep test modules with
`pytest.importorskip` so a partial local env degrades to skips instead of collection
errors. Record the real coverage figure in this audit once measured in CI.

---

## QUAL-05: Six low-value tests assert nothing meaningful

Severity: Low
Effort: S (<1day)

Evidence:
- `assert True` placeholders: tests/test_example.py:388 (relies only on "no exception"),
  tests/unit/test_correlation.py:16 (a literal placeholder class).
- Tests with no assert / no `pytest.raises` / no mock `assert_*` (AST scan):
  tests/unit/test_cache.py:121 `test_close_redis_when_pool_none`,
  tests/unit/test_sentry.py:394 `test_set_user_context_sdk_not_installed`,
  tests/unit/test_sentry.py:430 `test_add_breadcrumb_sdk_not_installed`.

These pass as long as the call does not raise; they assert no observable behavior. The
two `assert True` cases inflate the test count without adding signal.

Recommendation: For the "should not raise" tests, assert the post-condition (return
value, mock not-called, state). Delete or convert the `assert True` placeholders. Low
risk: they do not hide bugs, they just provide false coverage comfort.

Positive: zero `@pytest.mark.skip`/`xfail`/`pytest.skip` in the suite
(`git grep -cE "@pytest.mark.(skip|xfail)|pytest.skip" -- tests/` -> 0). 731 assert
statements across 458 tests is a healthy assert-per-test ratio.

---

## QUAL-06: Actionable time-boxed TODOs in CI workflows past or near their tighten-by date

Severity: Low
Effort: S (<1day)

Evidence: `git grep -nE "TODO|FIXME|HACK|XXX"` over the whole repo confirms 0 in src and
tests. The only actionable TODOs are in CI hardening config, all "tighten egress to block
after 2026-06-30":
- .github/workflows/fips-compatibility.yml:62, :216
- .github/workflows/pr-validation.yml:55
- .github/workflows/sonarcloud.yml:58, :86

Oldest by blame: 2026-05-18 (sonarcloud.yml). The 2026-06-30 deadline is one month out
from this audit (2026-05-29). The remaining `XXX`/`TODO` hits are template placeholders
in .claude/skills and docs (ADR-XXX, CVE-YYYY-XXXXX), not debt.

Recommendation: Track the 2026-06-30 step-security egress hardening as a dated task so
the audit-block workflows are switched to block-mode on schedule.

---

## Lightweight / clean areas

- Cyclomatic complexity: clean. C901 at max-complexity 10 -> "All checks passed". Worst
  radon function is deepgram_client._parse_utterances_and_speakers C(15); only 6 blocks
  exceed grade B; average A(3.69).
- Maintainability index: clean. All 20 src files grade A; lowest is jobs/worker.py 39.70.
- `Any` annotations: clean. 11 occurrences, every one inline-justified for an external
  SDK boundary (cli.py:65/97 Click ctx, sentry.py:31-37 SDK types, vad.py:25-45 torch
  hub load). No unjustified `Any` in domain code.
- noqa debt: low. 50 `# noqa` in src, all rule-coded (ARG001, PLC0415, S603, UP017,
  TRY300, PLW0603); no blanket `# noqa`.
- Branch hygiene: on feature branch claude/repo-audit-CW81U, not main.

---

## Summary table

| ID | Title | Severity | Effort | Files | Evidence | Recommendation | CVE |
|----|-------|----------|--------|-------|----------|----------------|-----|
| QUAL-01 | basedpyright 626 warnings vs strict-clean claim | Medium | L | src/ (all) | `basedpyright src/` -> 59 err / 626 warn; 555 reportUnknown* | Re-run synced; set rule severities or add typed adapters; reconcile CLAUDE.md | n/a |
| QUAL-02 | Duplicated audio-load fallback helper | Medium | S | services/quality_assessor.py:166, audio_conditioner.py:233, vad_processor.py:177/288, preprocessing/loader.py:92 | token-identical sf.read/librosa.load blocks | Extract one load_audio(), reuse loader.py | n/a |
| QUAL-03 | 109 inline ignores on 2 untyped lib boundaries, no prose reason | Medium | M | core/cache.py (36), core/sentry.py (24), jobs/worker.py (14), +others | `git grep type:ignore` -> 109; redis + structlog + sentry clusters | Type logger once, wrap redis, add per-block reason comments | n/a |
| QUAL-04 | Tests un-collectable / coverage unmeasurable without extras | Medium | S | tests/unit/* (14 modules), pyproject.toml:548 | pytest collect -> 80/458, 14 import errors; pytest-cov absent | Verify gate in CI with --all-extras; importorskip heavy modules | n/a |
| QUAL-05 | Six tests assert nothing meaningful | Low | S | test_example.py:388, test_correlation.py:16, test_cache.py:121, test_sentry.py:394/430 | `assert True` + AST no-assert scan | Assert real post-conditions; drop placeholders | n/a |
| QUAL-06 | Dated CI hardening TODOs near 2026-06-30 | Low | S | .github/workflows/{fips-compatibility,pr-validation,sonarcloud}.yml | 5 "tighten to block after 2026-06-30"; oldest blame 2026-05-18 | Track dated task; flip egress to block on schedule | n/a |
