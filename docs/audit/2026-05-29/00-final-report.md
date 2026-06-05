# Holistic Legacy and Architecture Audit: Final Report

Repo: ByronWilliamsCPA/audio-processor
Commit: 6f93411
Generated: 2026-05-29T20:50:49Z (UTC)
Method: read-only, seven parallel domain investigations synthesized here. No tracked code was modified.

---

## 1. Repo map

- Language and build: Python, uv package manager. `requires-python = ">=3.11,<3.14"` (pyproject.toml:12); ruff `target-version = "py312"`; basedpyright `pythonVersion = "3.12"`. Single source of truth is pyproject.toml + uv.lock; no requirements.txt, setup.py, setup.cfg, poetry.lock, or Pipfile (no prior-tooling residue).
- Lockfile state: `uv lock --check` exits 0, 303 packages resolved, requires-python matches pyproject. uv.lock last touched 2026-05-28.
- Runtime support: 3.11 (security to ~2027-10), 3.12 (~2028-10), 3.13 (~2029-10) all in window. Production image runs 3.12.
- Size: 233 tracked files. ~7,450 src LOC, ~7,722 test LOC (test-to-code ratio ~1.04). 86 markdown, 67 py, 34 yml. 458 test functions, 731 assert statements.
- Largest modules: core/exceptions.py (545), services/audio_converter.py (544), services/deepgram_client.py (519), api/routes.py (479), core/cache.py (469).
- Most-churned (git log): CI workflows dominate (sonarcloud.yml, pr-validation.yml, dependency-review.yml at 8 each), pyproject.toml (7), jobs/worker.py (6). 38 commits, 2025-12-04 to 2026-05-28.
- Tooling configured: pytest + coverage (--cov-fail-under=80), ruff, basedpyright (strict), bandit, vulture (declared in docs but missing from deps), interrogate, darglint, pre-commit (24 hooks), 24 GitHub Actions workflows, CodeQL, Semgrep, SonarCloud, Qlty, Scorecard, Trivy, OSV, SBOM, SLSA provenance, mutation testing, ClusterFuzzLite.
- Origin: generated from cookiecutter-python-template via cruft (.cruft.json). Heavy scaffolding; some template residue remains unspecialized.

Team run: 7 subagents (dependencies, legacy-code, code-quality, architecture, security, cicd, docs), one report each (01 through 07). Architecture subagent was warranted: this is a multi-package library, not a script.

---

## 2. Code quality: critical analysis

The metrics are good and the structure is the problem. Cyclomatic complexity passes at max-complexity 10 (ruff C901 clean), radon average grade A (3.69), all 20 src files maintainability grade A, worst function is `deepgram_client._parse_utterances_and_speakers` at C(15). Zero TODO/FIXME in src and tests. The source idioms are modern: builtin generics, `X | None`, `datetime.now(UTC)`, pathlib throughout, no pydantic v1 patterns, no `os.path`, no `pkg_resources`. By the usual surface measures this code is clean.

Three things undercut that. First, the strict-mode claim does not hold: `basedpyright src/` reports 626 warnings (555 are `reportUnknown*` from untyped redis, librosa, numpy, sentry boundaries), against a CLAUDE.md that states strict-mode is a passing gate and "address ALL type checker warnings." That is the single largest stated-versus-actual gap in the repo (QUAL-01). Second, the 109 inline `type: ignore`/`pyright: ignore` are all rule-coded (good) but none carries the inline reason the project's own standard requires, and 60 of them cluster on two libraries (redis in cache.py, sentry_sdk in sentry.py) that one typed wrapper each would collapse (QUAL-03). Third, the same soundfile-then-librosa audio-load block is copy-pasted across three services and preprocessing/loader.py while a loader module already exists, against the project's "Reuse First" principle (QUAL-02).

Test quality is mixed. The assert-per-test ratio (731/458) is healthy and there are zero skip/xfail markers, but six tests assert nothing observable (QUAL-05), and the suite cannot be coverage-measured without all optional extras installed (14 of ~21 modules fail import without them), so the 80% gate is only verifiable in a fully synced CI env (QUAL-04). The audit sandbox could not confirm the real coverage figure; that number must be read from a CI run, not asserted here.

## 3. Architecture: critical analysis

Dependency direction is correct (core <- services <- jobs/api/cli, utils as leaf), with no circular imports and no upward imports. The damage is duplication and dead code, not layering.

The headline structural problem is two parallel solutions to the same problem. `preprocessing/` (vad.py, quality.py, ffmpeg.py, loader.py) is a second implementation of what `services/` already does (vad_processor.py, quality_assessor.py, audio_converter.py, audio_conditioner.py). No production module imports `preprocessing/`; only tests do. The accepted ADR-002 and tech-spec name the `services/` classes as canonical and never mention `preprocessing/` (ARCH-01). The two exception modules track the same fault line: `preprocessing/` imports the orphaned 36-line `exceptions.py` while everything live imports `core/exceptions.py` (ARCH-02).

The second structural problem is that the accepted design is not wired up. ADR-002 mandates VAD silence removal and RMS normalization before ASR, but the live pipeline (jobs/audio_tasks.py) instantiates only the converter and the quality assessor before calling Deepgram. `AudioConditioner`, `VADProcessor`, `DOMBuilder`, and `TranscriptFormatter` have zero production callers (ARCH-03). The code and the accepted decision disagree, and nothing in the repo records that the disagreement is intentional.

Supporting issues: preprocessing hardcodes tuning constants that core/config.py already owns (ARCH-04); REDIS_URL and the Sentry vars are read via os.getenv outside the Settings class (ARCH-05); and heavy scientific libraries (numpy, torch, librosa, scipy, soundfile) are imported at module top level in every services and preprocessing module, so `import audio_processor.services` hard-fails without the optional extras even though the design claims audio lives behind extras (ARCH-06). The deepgram client already shows the lazy-import pattern that would fix this.

## 4. Cross-cutting themes

Theme 1: a tale of two codebases. The audio domain code (services, core, api, jobs) is recent, specialized, and wired to the specs. A second stratum (preprocessing/, utils/financial.py, empty middleware/, the worker's demo tasks, payment/financial guidance in CLAUDE.md, README/CONTRIBUTING boilerplate) is older or template-derived and never reconciled with the first. Nearly every Low and several Medium findings across four domains (LEG-02/04/05, ARCH-07, DOCS-09) are the same root cause: cookiecutter scaffolding shipped without being specialized or deleted. Removing it would close roughly a dozen findings at once.

Theme 2: built but not connected. preprocessing/ exists but is unused (ARCH-01). AudioConditioner/VADProcessor exist but are not in the pipeline (ARCH-03). DOMBuilder/TranscriptFormatter exist but have no callers (ARCH-03). .semgrep.yml exists but no job runs it (CICD-04). vulture is documented but not installed (LEG-06). The recurring pattern is artifacts created and then left disconnected from the thing that would exercise them.

Theme 3: documentation that describes a different project. The README imports a nonexistent `YourModule`, advertises a `process` CLI command that does not exist (only `hello`/`config` do), and ships an invalid `uv sync --all-extras,ml` install line (DOCS-01, DOCS-02). Four `draft_*.md` files (3,142 lines, titled "Project E") duplicate and contradict the finalized planning docs (DOCS-03). Four mutually inconsistent Python-version claims span the docs (DOCS-08). The accurate material lives in docs/guides/; the root docs were never brought up to it.

Theme 4: tooling breadth over tooling coherence. 24 workflows and six overlapping SAST tools, but tests run twice per PR (CICD-01), coverage uploads to Qlty twice (CICD-02), basedpyright is declared twice with conflicting floors (CICD-06), linter versions float in pyproject while pinned in pre-commit (CICD-07), and the coverage gate authority is split between pyproject, ci.yml, and a soft Codecov threshold (CICD-09). The security posture underneath is genuinely strong (SHA-pinned actions, scoped permissions, non-root pinned Dockerfile, shell-free subprocess, well-justified CVE suppressions); the noise is in orchestration, not in the controls.

Theme 5: stated standards versus enforced standards. CLAUDE.md claims strict-clean type checking (626 warnings say otherwise, QUAL-01), requires inline reasons on ignores (109 have none, QUAL-03), and mandates the future-import on all files (7 of 31 lack it, LEG-07). Qlty quietly relaxes the documented complexity gate from 10 to 12 (CICD-08). The standards are aspirational in several places where the repo presents them as enforced.

## 5. Disagreements and overlaps resolved

- Duplicate exception modules: reported by both legacy-code (LEG-01) and architecture (ARCH-02). Carried once as ARCH-02 (it is a structure decision). The legacy view that exceptions.py is "not a pure shim but the preprocessing exception home" is the more accurate reading; the resolution still folds it into core/exceptions.py because preprocessing/ itself is orphaned (ARCH-01).
- Template residue: legacy-code (LEG-03, financial.py), architecture (ARCH-07, financial.py + middleware/), docs (DOCS-09, payment guidance). Carried as ARCH-07 for the src residue and DOCS-09 for the doc guidance; LEG-03 is subsumed by ARCH-07.
- py 1.11.0 ReDoS: dependencies (DEP-03) and security (SEC-04). Carried once as DEP-03 (a dependency-hygiene item that happens to carry a disputed, suppressed, dev-only CVE). Both agreed the suppression is valid.
- starlette PYSEC-2026-161 stale comment: dependencies (DEP-09) and security (SEC-05). Carried once as SEC-05. Both agreed it is already patched (starlette 1.1.0 in lock, fix landed in 1.0.1) and is a comment-only cleanup, not a live exposure.
- preprocessing duplication: architecture frames it as an orphaned package (ARCH-01); code-quality frames the load-helper copy as independent of that (QUAL-02). Both kept: QUAL-02 (the in-services duplication) stands even if preprocessing/ is deleted.
- Clean/informational dependency rows (DEP-06 lockfile, DEP-07 no residue, DEP-08 version window, DEP-09 SBOM) are recorded in report 01 and excluded from the remediation backlog below, which lists actionable items only.

## 6. Prioritized remediation backlog

Sorted by severity (High to Low), then effort (S to L). 51 actionable findings (7 High, 20 Medium, 24 Low). Clean/informational items live in the per-domain reports, not here.

| ID | Finding | Domain | Severity | Effort | Files |
|----|---------|--------|----------|--------|-------|
| SEC-02 | Upload size limit bypassable; full body read into memory | security | High | S | src/audio_processor/api/routes.py:117-127,156 |
| DOCS-02 | README install uses invalid uv extras syntax | docs | High | S | README.md:87-88 |
| DEP-01 | ffmpeg-python abandoned (last release 2019-07-06) | dependencies | High | M | pyproject.toml:161, uv.lock |
| ARCH-01 | preprocessing/ is a parallel orphaned reimplementation of services/ | architecture | High | M | src/audio_processor/preprocessing/, src/audio_processor/services/ |
| ARCH-03 | Spec-mandated VAD/conditioning not wired into the pipeline | architecture | High | M | src/audio_processor/jobs/audio_tasks.py, services/audio_conditioner.py, services/vad_processor.py |
| SEC-01 | Audio API has no authentication or authorization | security | High | M | src/audio_processor/api/routes.py, api/__init__.py |
| DOCS-01 | README describes nonexistent API and CLI commands | docs | High | M | README.md:96-104,110-116,478-483 |
| DEP-04 | Base image digest pin goes stale, no auto security refresh | dependencies | Medium | S | Dockerfile:7,42, .trivyignore |
| LEG-02 | Cookiecutter demo tasks (incl. fake send_email_task) live in worker | legacy-code | Medium | S | src/audio_processor/jobs/worker.py:71,102,138,246-248 |
| QUAL-02 | Duplicated audio-load helper across 3 services and loader | code-quality | Medium | S | src/audio_processor/services/quality_assessor.py:166, audio_conditioner.py:233, vad_processor.py:177, preprocessing/loader.py:92 |
| QUAL-04 | Tests un-collectable and coverage unmeasurable without extras | code-quality | Medium | S | tests/unit/, pyproject.toml:548 |
| ARCH-02 | Two exception modules; orphaned one used only by preprocessing/ | architecture | Medium | S | src/audio_processor/exceptions.py, core/exceptions.py |
| ARCH-04 | Duplicated config values; preprocessing hardcodes config-owned tuning | architecture | Medium | S | src/audio_processor/core/config.py:103-163, preprocessing/loader.py:21, preprocessing/quality.py:62 |
| SEC-03 | torch 2.9.1 unpatched local-CE CVE present in optional extras | security | Medium | S | uv.lock, osv-scanner.toml, pyproject.toml:648-653 |
| SEC-06 | Sentry before_send scrubbing shallow and key-list-limited | security | Medium | S | src/audio_processor/core/sentry.py:198-208 |
| CICD-01 | Test + coverage suite runs twice on every PR | cicd | Medium | S | .github/workflows/ci.yml:33, pr-validation.yml:36 |
| CICD-05 | Reusable-workflow SHA skew across callers | cicd | Medium | S | .github/workflows/container-security.yml:43, mutation-testing.yml:36 |
| CICD-06 | basedpyright declared twice with conflicting floors | cicd | Medium | S | pyproject.toml:92,835 |
| CICD-09 | Coverage gate authority split and partly soft | cicd | Medium | S | pyproject.toml:548, .codecov.yml:20-28, ci.yml:36 |
| DOCS-03 | draft_*.md files duplicate and contradict finalized planning docs | docs | Medium | S | docs/draft_vision.md, draft_tech_spec.md, draft_ADR.md, draft_audio_preprocessing.md |
| DOCS-04 | planning/README shows "Awaiting Generation" for docs that exist | docs | Medium | S | docs/planning/README.md:37-40 |
| DEP-02 | pydub unmaintained; audioop removed in Python 3.13 | dependencies | Medium | M | pyproject.toml:160,12, uv.lock |
| QUAL-03 | 109 inline ignores on 2 untyped lib boundaries, no prose reason | code-quality | Medium | M | src/audio_processor/core/cache.py, core/sentry.py, jobs/worker.py |
| ARCH-06 | Heavy libs imported at module top; services unimportable without extras | architecture | Medium | M | src/audio_processor/services/, preprocessing/, pyproject.toml:80,127-163 |
| CICD-07 | Tool versions float in pyproject but SHA-pinned in pre-commit | cicd | Medium | M | pyproject.toml:91,93, .pre-commit-config.yaml:58,106 |
| DOCS-05 | api-reference omits all audio modules | docs | Medium | M | docs/api-reference.md |
| QUAL-01 | basedpyright 626 warnings contradict the strict-clean claim | code-quality | Medium | L | src/audio_processor/ |
| DEP-03 | py 1.11.0 deprecated dev-only transitive (suppressed ReDoS) | dependencies | Low | S | uv.lock, pyproject.toml:647 |
| DEP-05 | ClusterFuzzLite base tag unpinned, unpinned pip installs | dependencies | Low | S | .clusterfuzzlite/Dockerfile:6 |
| DEP-10 | Minor direct-dependency version lag | dependencies | Low | S | uv.lock, pyproject.toml |
| LEG-04 | Dead function parameter include_correlation in setup_logging | legacy-code | Low | S | src/audio_processor/utils/logging.py:42 |
| LEG-05 | Commented-out SendGrid integration block | legacy-code | Low | S | src/audio_processor/jobs/worker.py:124-127 |
| LEG-06 | vulture missing from the dev toolchain | legacy-code | Low | S | pyproject.toml |
| LEG-07 | from __future__ import annotations missing in 7 of 31 files | legacy-code | Low | S | src/audio_processor/cli.py, utils/logging.py |
| QUAL-05 | Six tests assert nothing meaningful | code-quality | Low | S | tests/test_example.py:388, tests/unit/test_correlation.py:16, test_cache.py:121, test_sentry.py:394,430 |
| QUAL-06 | Dated CI hardening TODOs near 2026-06-30 | code-quality | Low | S | .github/workflows/fips-compatibility.yml, pr-validation.yml, sonarcloud.yml |
| ARCH-05 | Env reads outside core/config.py | architecture | Low | S | src/audio_processor/core/cache.py:81, core/sentry.py:87,94-97 |
| ARCH-07 | Template residue: financial util, empty middleware, payment docs | architecture | Low | S | src/audio_processor/utils/financial.py, middleware/__init__.py |
| SEC-05 | PYSEC-2026-161 suppression note stale (already patched) | security | Low | S | pyproject.toml:152-154, uv.lock |
| SEC-07 | README example uses moving @main reusable-workflow ref | security | Low | S | .github/workflows/README.md:162 |
| CICD-02 | Coverage uploaded to Qlty twice (coverage.yml and qlty.yml) | cicd | Low | S | .github/workflows/coverage.yml:26, qlty.yml:18 |
| CICD-04 | Orphaned .semgrep.yml not run anywhere | cicd | Low | S | .semgrep.yml |
| CICD-08 | Qlty complexity threshold looser than house standard | cicd | Low | S | .qlty/qlty.toml:86,96 |
| CICD-10 | Core CI only exercises Python 3.12 | cicd | Low | S | .github/workflows/python-compatibility.yml:41, ci.yml:35, pyproject.toml:12 |
| DOCS-06 | No ADR for the ARQ background-job decision | docs | Low | S | docs/planning/adr/ |
| DOCS-07 | CHANGELOG references Poetry; duplicate Fixed header | docs | Low | S | CHANGELOG.md |
| DOCS-08 | Conflicting Python version statements across docs | docs | Low | S | README.md:60, docs/PYTHON_COMPATIBILITY.md:13, CONTRIBUTING.md:27 |
| DOCS-09 | Generic Payment/Financial guidance retained in audio project | docs | Low | S | CLAUDE.md:79,97,445 |
| DOCS-10 | Model Selection table duplicated across agent docs | docs | Low | S | CLAUDE.md, AGENTS.md:11-23 |
| CICD-03 | Six overlapping SAST/quality tools; CodeQL runs twice | cicd | Low | M | .github/workflows/codeql.yml, security-analysis.yml, sonarcloud.yml, qlty.yml |
| CICD-11 | pre-commit hooks not mirrored in CI (local-only gates) | cicd | Low | M | .pre-commit-config.yaml, .github/workflows/pr-validation.yml |

## 7. Verdict

State: drifting, not at-risk. The supply chain, security controls, and core code idioms are sound; there is no critical exposure and no broken build. What drifts is the gap between the repo's declared design (ADR-002, CLAUDE.md standards, README) and what the code actually does, plus a layer of unspecialized template scaffolding that was never removed. None of it is on fire, but the gap widens each time someone trusts a doc or a spec that the code does not honor.

The three changes that move it most:

1. Resolve the preprocessing/ vs services/ split (ARCH-01, ARCH-02, ARCH-04) and wire in or formally defer the spec-mandated VAD/conditioning (ARCH-03). One decision closes the largest structural findings and stops the code and ADR-002 from contradicting each other.
2. Close the two app-layer security gaps: add authentication to the API (SEC-01) and enforce a streamed upload cap (SEC-02). These are the only High findings that touch a running, externally reachable surface.
3. Reconcile stated standards with enforced ones: fix the README so first commands work (DOCS-01, DOCS-02), and make the basedpyright strict-clean claim true or change the claim (QUAL-01). This restores trust in the docs and the quality gate that onboarding depends on.
