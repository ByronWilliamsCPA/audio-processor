# Documentation and Developer Experience Audit

Date: 2026-05-29
Scope: README, CONTRIBUTING, CLAUDE/AGENTS/GEMINI/copilot, docs/ tree, mkdocs.yml, draft vs planning, CHANGELOG.
Method: read-only. Repo is cookiecutter-template generated; much root doc is unspecialized boilerplate.

Summary verdict: the user-facing guides under `docs/guides/` and the planning ADRs are accurate and audio-specific. The repo root README and CONTRIBUTING are still generic template boilerplate that describe a non-existent API and fake CLI commands. Four leftover `draft_*.md` files duplicate the finalized planning docs. These two issues are the real onboarding blockers.

---

## DOCS-01: README quick-start describes code that does not exist

Severity: High
Effort: M (rewrite README Overview, Features, Basic Usage, CLI Usage, Project Structure against real modules)

Evidence:
- `README.md:96-104` library example imports `from audio_processor import YourModule` and calls `module.process()`. No `YourModule` symbol exists anywhere in `src/`. Confirmed: `git grep YourModule` returns only README.md and CONTRIBUTING.md.
- `README.md:110-116` CLI examples show `audio_processor command --option value` and `audio_processor process input.txt --output result.json`. Actual CLI (`src/audio_processor/cli.py:48,86`) exposes only two subcommands: `hello` and `config`. No `process` command exists.
- `README.md:478-483` Project Structure lists `src/audio_processor/core.py` ("Core functionality"). No `core.py` exists; the package has `core/` (config, cache, exceptions, models, sentry) plus `services/`, `preprocessing/`, `jobs/`, `api/`. The structure block omits every audio module.
- `README.md:36-54` Overview/Features make no mention of Deepgram, FFmpeg, VAD, Docling, or transcription. It reads as a generic "ML Ready" template.

Recommendation: Replace the boilerplate Overview, Basic Usage, CLI Usage, and Project Structure sections with the real feature set and module layout. The accurate content already exists in `docs/guides/usage.md` and `docs/guides/configuration.md`; port it up.

---

## DOCS-02: README install command uses invalid extras syntax

Severity: High
Effort: S (one-line fix)

Evidence:
- `README.md:87-88`: `uv sync --all-extras,ml`. This is not valid uv syntax. `--all-extras` takes no value, and a comma-joined extra is not parsed. A new contributor copy-pasting this gets an error on their first command.
- Extras defined in `pyproject.toml:80+` are `dev`, plus `ml`, `audio`, `jobs`, `api` (per repo facts). `--all-extras` already installs all of them, so the second line is also redundant.

Recommendation: Remove line 88 entirely (since line 86 `--all-extras` covers ml), or replace with `uv sync --extra ml` if a non-all install is intended.

---

## DOCS-03: Leftover draft_*.md files duplicate finalized planning docs

Severity: Medium
Effort: S (delete four files, fix two stale references)

Evidence:
- `docs/draft_vision.md` (541 lines), `docs/draft_tech_spec.md` (1626 lines), `docs/draft_ADR.md` (632 lines), `docs/draft_audio_preprocessing.md` (343 lines) all carry front-matter `status: draft` and title `Project E - Audio Preprocessing Engine`.
- Finalized equivalents exist and are referenced by mkdocs/CLAUDE: `docs/planning/project-vision.md`, `docs/planning/tech-spec.md`, `docs/planning/adr/adr-001-initial-architecture.md`, `docs/planning/adr/adr-002-audio-preprocessing-pipeline.md`. The draft tech-spec alone (1626 lines) is larger than the entire finalized planning set and contradicts it in places (different project name "Project E").
- Two live docs still point at the drafts: `docs/architecture/index.md:39` ("Copy `docs/ADRs/draft_ADR.md` (or `docs/draft_ADR.md`)") and `docs/planning/PROJECT-PLAN.md:361` ("Accepted (documented in draft_ADR.md)"). Both should cite the adr/ files.

Recommendation: Delete the four `docs/draft_*.md` files and repoint `docs/architecture/index.md:39` and `docs/planning/PROJECT-PLAN.md:361` at `docs/planning/adr/adr-001`/`adr-002`. (Read-only audit: not done here.)

---

## DOCS-04: planning/README shows "Awaiting Generation" for docs that exist

Severity: Medium
Effort: S (update four status cells)

Evidence:
- `docs/planning/README.md:37-40` lists project-vision.md, tech-spec.md, roadmap.md, and adr/ all with status "Awaiting Generation".
- All four are populated: `docs/planning/project-vision.md`, `tech-spec.md`, `roadmap.md`, and `adr/adr-001`+`adr-002` exist with real content (verified above). The status table is a stale placeholder.

Recommendation: Update the four status cells to "Generated" / "Accepted". Note this is a template placeholder pattern; consider feeding back to the template per CLAUDE.md template-feedback requirement.

---

## DOCS-05: api-reference.md omits all audio modules

Severity: Medium
Effort: M (add mkdocstrings blocks for services, preprocessing, jobs, api, core models)

Evidence:
- `docs/api-reference.md` renders only `audio_processor.core.config`, `audio_processor.utils.logging`, and `audio_processor.cli`.
- The actual public surface includes `services/` (deepgram_client, dom_builder, audio_converter, audio_conditioner, vad_processor, quality_assessor, transcript_formatter), `preprocessing/` (ffmpeg, loader, quality, vad), `jobs/` (audio_tasks, worker), `api/routes`, and `core/models`. None are documented. The published API reference covers maybe 10% of the library.

Recommendation: Add `:::` mkdocstrings blocks for the services, preprocessing, jobs, api, and core.models modules so the generated API site matches the shipped code.

---

## DOCS-06: No ADR for the ARQ background-job decision

Severity: Low
Effort: S (one ADR, or a note in ADR-001)

Evidence:
- ADR-001 and ADR-002 cover Deepgram (exclusive ASR), Docling DOM output, and the librosa/pydub/FFmpeg/Silero-VAD preprocessing pipeline. Strong coverage of those decisions.
- The job system uses ARQ (`src/audio_processor/jobs/worker.py`, `audio_tasks.py`), but `git grep -i '\barq\b'` over `docs/planning/adr/` and `docs/ADRs/` returns nothing. ADR-001 references "Redis Queue" generically (`adr-001:30`) without recording the choice of ARQ over RQ or Celery. The preprocessing/ vs services/ package split is also undocumented as a decision.

Recommendation: Add a short ADR-003 recording ARQ selection (vs RQ/Celery) and the preprocessing/services module boundary, or append a "Job framework" subsection to ADR-001.

---

## DOCS-07: CHANGELOG references Poetry and has a duplicate section header

Severity: Low
Effort: S (edit two spots in CHANGELOG)

Evidence:
- `CHANGELOG.md` [0.1.0] section: "Initial project structure with Poetry package management" and "Poetry dependency management with lock file". The project uses UV (`pyproject.toml` PEP 621 + uv.lock; CLAUDE.md states Package Manager UV). Poetry is never used.
- The [Unreleased] block contains two separate `### Fixed` headers back to back (the audio-pipeline fixes, then the renovate/ci fixes). Keep a Changelog expects one Fixed subsection per release.
- Otherwise the [Unreleased] block is accurate and current: it matches the real feature commits (`feat: phase 1 MVP + Docling DOM #43`, `feat(preprocessing) #27`, `feat: Phase 0 #4`) and the CVE bumps. CVE citation policy from CLAUDE.md is followed.

Recommendation: Replace "Poetry" with "UV" in the [0.1.0] Added/Infrastructure lines and merge the two `### Fixed` subsections into one.

---

## DOCS-08: Python version statements conflict across docs

Severity: Low
Effort: S (align badges and prose to pyproject)

Evidence:
- Source of truth `pyproject.toml:12`: `requires-python = ">=3.11,<3.14"` (so 3.11, 3.12, 3.13).
- `README.md:60` and `.standards/README.baseline.md:63`: "Python 3.10+ (tested with 3.12)", claims 3.10, which pyproject forbids.
- `docs/PYTHON_COMPATIBILITY.md:13`: "supports Python 3.10, 3.11, 3.12, 3.13, and 3.14 with full testing across all versions", claims 3.10 and 3.14, both outside the pyproject range.
- `CONTRIBUTING.md:27`, `docs/development/setup.md:18`, `docs/development/contributing.md:18`, `docs/guides/overview.md:18`, `docs/index.md:35`: "Python 3.12+", a fourth distinct statement.
- README badge `README.md:23` and planning docs (`tech-spec.md:24`, `PROJECT-PLAN.md:285`) say 3.12 only.

Four mutually inconsistent claims (3.10+, 3.12, 3.12+, 3.10-3.14). Onboarding contributors cannot tell which interpreters are supported.

Recommendation: Pick one statement matching pyproject ("Python 3.11-3.13, primary 3.12") and apply it to README line 60, PYTHON_COMPATIBILITY.md, CONTRIBUTING.md, and the docs/development + docs/guides files.

---

## DOCS-09: Generic Payment/Financial guidance retained in audio project

Severity: Low
Effort: S (remove or replace the financial examples)

Evidence:
- `CLAUDE.md:79,97` carry the template's RAD examples: "Payment processing, auth flows" and "**Payment/Financial**: Transaction integrity, retry logic, rollback handling" as a MANDATORY tagging category.
- `CLAUDE.md:445` Project Structure documents `utils/financial.py` ("Financial utilities (Decimal precision)"), which exists (`src/audio_processor/utils/financial.py`) but is template boilerplate with no role in an audio/RAG pipeline.
- These trace to `.standards/CLAUDE.baseline.md:33,51`, so the unspecialized text is inherited from the baseline.

Recommendation: Replace the payment/financial RAD category with an audio-relevant critical category (for example external ASR API calls, FFmpeg subprocess handling, large-file streaming). Note the dead `utils/financial.py` for the code-quality auditor.

---

## DOCS-10: Agent instruction files overlap but are mostly thin pointers (low duplication)

Severity: Low
Effort: S (no urgent action)

Evidence:
- Four agent-facing files exist: `CLAUDE.md` (~25 KB, the authority), `AGENTS.md` (~4.6 KB), `GEMINI.md` (684 bytes), `.github/copilot-instructions.md` (122 lines).
- `GEMINI.md` is a pure pointer to CLAUDE.md and AGENTS.md, no duplicated rules. `AGENTS.md` adds genuinely new audio-specific agent rules (FFmpeg via ffmpeg-python only, path-traversal resolution, Deepgram key handling) and references CLAUDE.md for the rest. Overlap with CLAUDE.md is limited to the Model Selection table and the subagent assignment list (roughly 25 of AGENTS.md's ~150 lines).
- The one duplicated table that risks drift is Model Selection (CLAUDE.md "Model Selection" section vs AGENTS.md lines 11-23); both restate Opus/Sonnet/Haiku tiers.

Clean area overall: the agent-doc set is well factored. Only the Model Selection table is duplicated and could drift.

Recommendation: Optional, collapse the Model Selection table to live in one file and have the other link to it.

---

## Other areas checked, no issues

- mkdocs.yml nav: all 12 referenced targets exist (index, guides/overview|configuration|usage, api-reference, development/architecture|testing|code-quality|contributing, project/roadmap|changelog|license). No broken nav links.
- docs/guides/configuration.md: accurate, audio-specific (real Deepgram env vars, nova-2 defaults). Good.
- docs/guides/usage.md: CLI section correctly documents the real `hello`/`config` commands and `--debug` (matches cli.py). Library section uses the real `__version__` import.
- SECURITY.md, known-vulnerabilities.md, OPENSSF_COMPLIANCE.md: present per OpenSSF requirement.

---

## Summary Table

| ID | Title | Severity | Effort | Files | Evidence | Recommendation | CVE |
|----|-------|----------|--------|-------|----------|----------------|-----|
| DOCS-01 | README describes nonexistent API and CLI | High | M | README.md | README.md:96-104, 110-116, 478-483 | Rewrite Overview/Usage/Structure from real modules; port from docs/guides | n/a |
| DOCS-02 | Invalid uv extras install syntax in README | High | S | README.md | README.md:87-88 | Delete line 88 or use `uv sync --extra ml` | n/a |
| DOCS-03 | draft_*.md duplicate finalized planning docs | Medium | S | docs/draft_*.md, docs/architecture/index.md, docs/planning/PROJECT-PLAN.md | draft files vs planning/adr; index.md:39; PROJECT-PLAN.md:361 | Delete 4 drafts, repoint 2 references to adr/ | n/a |
| DOCS-04 | planning/README "Awaiting Generation" stale | Medium | S | docs/planning/README.md | planning/README.md:37-40 | Update status cells to Generated/Accepted | n/a |
| DOCS-05 | api-reference omits all audio modules | Medium | M | docs/api-reference.md | api-reference.md (only core.config, utils.logging, cli) | Add mkdocstrings blocks for services/preprocessing/jobs/api/models | n/a |
| DOCS-06 | No ADR for ARQ jobs / module split | Low | S | docs/planning/adr/ | grep arq -> none; adr-001:30 | Add ADR-003 or note in ADR-001 | n/a |
| DOCS-07 | CHANGELOG says Poetry; duplicate Fixed header | Low | S | CHANGELOG.md | [0.1.0] Poetry lines; two `### Fixed` in Unreleased | Replace Poetry with UV; merge Fixed sections | n/a |
| DOCS-08 | Conflicting Python version statements | Low | S | README.md, docs/PYTHON_COMPATIBILITY.md, CONTRIBUTING.md, docs/development/*, docs/guides/overview.md, docs/index.md | pyproject:12 (>=3.11,<3.14) vs README:60 (3.10+) vs PYTHON_COMPATIBILITY:13 (3.10-3.14) vs CONTRIBUTING:27 (3.12+) | Standardize on "3.11-3.13, primary 3.12" everywhere | n/a |
| DOCS-09 | Generic Payment/Financial guidance retained | Low | S | CLAUDE.md, src/audio_processor/utils/financial.py | CLAUDE.md:79,97,445 | Replace payment RAD category with audio-relevant one; flag dead financial.py | n/a |
| DOCS-10 | Model Selection table duplicated across agent docs | Low | S | CLAUDE.md, AGENTS.md | AGENTS.md:11-23 vs CLAUDE.md Model Selection | Optional: single-source the table | n/a |
