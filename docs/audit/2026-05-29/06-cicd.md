# CI/CD and Tooling Audit - audio-processor

Date: 2026-05-29
Scope: `.github/workflows/` (24 workflows), pre-commit, pyproject tool configs, SAST/coverage tooling.
Mode: READ-ONLY. No tracked files changed.

Headline: Action hygiene is strong (all SHA-pinned, no deprecated majors, no `set-output`). The real
problems are workflow fan-out (tests run twice per PR, coverage uploaded to Qlty twice), an orphaned
Semgrep config, tool-version and threshold drift between pre-commit / pyproject / Qlty, and a
reusable-workflow SHA skew across the 24 callers.

---

## CICD-01: Test + coverage suite runs twice on every PR

Severity: Medium
Effort: S (gate one caller, <1 day)

Evidence:
- `ci.yml:33` calls `python-ci.yml@799ebd6` on `pull_request` to main/master/develop.
- `pr-validation.yml:36` calls the same `python-ci.yml@799ebd6` on `pull_request` to the same branches, plus extra dead-code/link jobs.
- Both fire on identical PR triggers (`opened, synchronize, reopened`), so the full pytest + coverage run executes twice per PR push.

Recommendation: Have `pr-validation.yml` depend on `ci.yml` (or `workflow_run`) instead of re-invoking `python-ci.yml`, or move the dead-code/link jobs into `ci.yml` and delete the duplicate `core-validation` caller.

---

## CICD-02: Coverage uploaded to Qlty twice (coverage.yml and qlty.yml are duplicates)

Severity: Low
Effort: S (delete one file, <1 day)

Evidence:
- `coverage.yml:26` calls `python-qlty-coverage.yml@799ebd6` on `workflow_run` after CI, uploading `coverage.xml` artifact `coverage-reports`.
- `qlty.yml:18` calls the same `python-qlty-coverage.yml@799ebd6` on `workflow_run` after CI, uploading the same `coverage.xml` artifact `coverage-reports`.
- Both gate on `workflow_run.conclusion == 'success'`. Two identical Qlty uploads of one coverage file.

Recommendation: Delete one of `coverage.yml` / `qlty.yml`; keep the one with the `workflow_dispatch` manual re-run input (`coverage.yml`).

---

## CICD-03: Six overlapping SAST/quality tools with partial config ownership

Severity: Low
Effort: M (decide tool ownership matrix, few days)

Evidence:
- Distinct workflows running Python tests: 2 (`ci.yml`, `pr-validation.yml`), both via `python-ci.yml`. The compatibility matrix (`python-compatibility.yml`) adds a 3rd test path.
- SAST/quality stack: CodeQL (`codeql.yml`, also in `security-analysis.yml:42`), Bandit (`security-analysis.yml:44`), SonarCloud (`sonarcloud.yml`), Qlty (`qlty.yml`/`coverage.yml`), Scorecard (`scorecard.yml`), plus pre-commit Bandit. Six tools with overlapping issue classes (Bandit findings also surface in Sonar and Qlty).
- CodeQL runs in two places: standalone `codeql.yml:60` and inside `security-analysis.yml` (`run-codeql: true`), risking double SARIF uploads.

Recommendation: Pick one owner per finding class (CodeQL for SAST, Bandit for Python security, Sonar for maintainability) and disable CodeQL in either `codeql.yml` or `security-analysis.yml`.

---

## CICD-04: Orphaned Semgrep config (.semgrep.yml not run anywhere)

Severity: Low
Effort: S (wire a job or remove the file, <1 day)

Evidence:
- `.semgrep.yml` exists (740 bytes).
- `grep -rln semgrep .github/workflows/ .pre-commit-config.yaml noxfile.py` returns nothing. No workflow, pre-commit hook, or nox session invokes Semgrep.

Recommendation: Either add a Semgrep CI job / pre-commit hook that consumes `.semgrep.yml`, or remove the dead config so it does not imply coverage that does not exist.

---

## CICD-05: Reusable-workflow SHA skew across callers

Severity: Medium
Effort: S (bump two callers to one SHA, <1 day)

Evidence:
- 12 callers pin `ByronWilliamsCPA/.github/...@799ebd63e16aba0236ceded915f5c1cac20823b3`.
- `container-security.yml:43` and `mutation-testing.yml:36` pin a different SHA `@a81c5c7d06a27f27a7d6d965934100f9b80139d6` (comment: "PR #142 merged 2026-05-19").
- Two different versions of the org reusable-workflow set are live in the same repo, so shared inputs/behavior can diverge.

Recommendation: Pin all org reusable-workflow callers to a single reviewed SHA (or a Dependabot-managed tag) and update them together.

---

## CICD-06: basedpyright declared twice in pyproject with conflicting floors

Severity: Medium
Effort: S (delete one line, <1 day)

Evidence:
- `pyproject.toml:92` `"basedpyright>=1.18.0"`.
- `pyproject.toml:835` `"basedpyright>=1.35.0"`.
- Two dependency declarations with different minimums; resolution depends on which extra/group wins, so local vs CI may install different type-checker versions and report different strict-mode errors.

Recommendation: Keep a single `basedpyright>=1.35.0` declaration and remove the stale `>=1.18.0` line.

---

## CICD-07: Tool versions float in pyproject but are SHA-pinned in pre-commit (drift risk)

Severity: Medium
Effort: M (align versions, few days)

Evidence:
- Ruff: pre-commit `ruff-pre-commit` rev `v0.15.13` (`.pre-commit-config.yaml:58`) vs pyproject `"ruff>=0.9.0"` (`pyproject.toml:91`). A `uv sync` can install a different Ruff than pre-commit, so `uv run ruff check` and the hook can disagree.
- Bandit: pre-commit `1.7.10` (`.pre-commit-config.yaml:106`) vs pyproject `"bandit>=1.7.0"` (`pyproject.toml:93`).
- Interrogate: pre-commit `1.7.0` (`.pre-commit-config.yaml:241`) vs pyproject `"interrogate>=1.7.0"`.

Recommendation: Pin floors in pyproject to match the pre-commit revs (e.g. `ruff>=0.15.13`) so CI, local `uv run`, and pre-commit run identical linter versions.

---

## CICD-08: Qlty complexity thresholds looser than house standard

Severity: Low
Effort: S (align one number, <1 day)

Evidence:
- `.qlty/qlty.toml:86` global `function_complexity.threshold = 10` (comment cites Google/Pylint standard), but the Python override `.qlty/qlty.toml:96` raises it to `12`, `boolean_logic` to `6` (`:99`), `file_complexity` to `750` (`:102`).
- CLAUDE.md mandates strict standards; the Python override silently relaxes the documented complexity gate that Qlty otherwise enforces.

Recommendation: Drop the Python `function_complexity` override back to 10 (or document why audio code needs 12) to keep Qlty aligned with the stated standard.

---

## CICD-09: Coverage gate authority is split and partly soft

Severity: Medium
Effort: S (consolidate the gate, <1 day)

Evidence:
- Hard gate: `pyproject.toml:548` `"--cov-fail-under=80"` (pytest addopts) and `ci.yml:36` `coverage-threshold: 80` passed to the reusable workflow.
- Codecov status checks use `threshold` tolerances: project `target: 80% / threshold: 2%` (`.codecov.yml:20-21`) and patch `threshold: 5%` (`.codecov.yml:28`), so a PR can drop new-code coverage up to 5% below target and still pass the Codecov check.
- Codecov `range: 70..95` (`.codecov.yml:14`) and per-flag targets of 70% (`.codecov.yml:90,94`) sit below the documented 80% floor.
- The binding pass/fail enforcement lives in the org reusable `python-ci.yml`, which is not in this repo and cannot be inspected here, so the actual gate is unverifiable from the repo.

Recommendation: Treat `--cov-fail-under=80` as the single source of truth, tighten the Codecov patch threshold toward 0-2%, and verify the reusable workflow does not run coverage with `continue-on-error`.

---

## CICD-10: Core CI only exercises Python 3.12

Severity: Low
Effort: S (confirm 3.13 support or trim, <1 day)

Evidence:
- `pyproject.toml:12` `requires-python = ">=3.11,<3.14"`.
- `python-compatibility.yml:41` matrix `["3.11", "3.12", "3.13"]` (within range, correct).
- Every other workflow hard-codes only `3.12` (`ci.yml:35`, `codeql.yml:49`, `sonarcloud.yml:96,143`, `slsa-provenance.yml:70`, etc.). Primary CI, type-check, and SAST never exercise 3.11 or 3.13; a 3.11/3.13-only regression only surfaces in the matrix job, which is `paths`-filtered and weekly.

Recommendation: Either narrow `requires-python` to `>=3.12` if 3.11/3.13 are not truly supported, or run core CI lint/type/test across the full supported range.

---

## CICD-11: pre-commit hooks not mirrored in CI (local-only quality gates)

Severity: Low
Effort: M (add CI parity or document, few days)

Evidence:
- pre-commit runs local hooks `darglint` (`.pre-commit-config.yaml:256`), `interrogate` (`:243`), `no-em-dash` (`:275`), `validate-front-matter` (`:222`), `qlty-full` (`:207`), `bandit-full` (`:117`).
- In CI, only `vulture` appears as an inline job (`pr-validation.yml:78`); `grep -rln "darglint\|interrogate\|vulture"` matches only `pr-validation.yml`. Darglint, interrogate, no-em-dash and front-matter checks run only if a contributor has pre-commit installed and can be bypassed.

Recommendation: Add a CI job (or confirm the org `python-ci.yml` runs `pre-commit run --all-files`) so darglint/interrogate/no-em-dash are enforced server-side.

---

## Clean areas (one line each)

- Action version hygiene: clean. No `actions/checkout@v3-`, no `setup-python@v4-`, no `upload-artifact@v3`; checkout v6.0.2, setup-python v6.2.0, upload-artifact v7.0.1 throughout.
- Deprecated runtime/commands: clean. No `set-output`, no `save-state`, no `node12`/`node16` references.
- SHA pinning: clean. Every third-party action is pinned to a full commit SHA with a version comment (e.g. `harden-runner@ab7a940 # v2.19.3`).
- Caching: clean. `setup-uv` uses `enable-cache: true` with `cache-dependency-glob: uv.lock` (`pr-validation.yml:67-70`).
- Non-blocking gates in local workflows: limited and justified. `|| true` only on vulture report (`pr-validation.yml:78`) and a FIPS report capture (`fips-compatibility.yml:99`); `continue-on-error` only on Sonar's analysis-input step (`sonarcloud.yml:121`), with the quality gate enforced separately.
- Codecov chaining: clean. `codecov.yml` runs on `workflow_run` after CI success, downloads artifacts only, no source checkout.
- python-version string config: consistent at 3.12 across Sonar (`sonar.python.version=3.12`), basedpyright (`pythonVersion = "3.12"`), ruff (`target-version = "py312"`).
- Ruff line-length 88 (`pyproject.toml:209`) matches CLAUDE.md; no conflicting line-length in Sonar/Qlty.

---

## Summary Table

| ID | Title | Severity | Effort | Files | Evidence | Recommendation | CVE |
|----|-------|----------|--------|-------|----------|----------------|-----|
| CICD-01 | Tests run twice per PR | Medium | S | ci.yml, pr-validation.yml | ci.yml:33 + pr-validation.yml:36 both call python-ci.yml on same PR triggers | Chain pr-validation off ci instead of re-invoking python-ci | - |
| CICD-02 | Coverage uploaded to Qlty twice | Low | S | coverage.yml, qlty.yml | coverage.yml:26 + qlty.yml:18 both call python-qlty-coverage on CI workflow_run | Delete one; keep the manual-dispatch variant | - |
| CICD-03 | Six overlapping SAST/quality tools | Low | M | codeql.yml, security-analysis.yml, sonarcloud.yml, qlty.yml, scorecard.yml | CodeQL run in codeql.yml:60 and security-analysis.yml:42 | One owner per finding class; disable duplicate CodeQL | - |
| CICD-04 | Orphaned .semgrep.yml | Low | S | .semgrep.yml | file present, zero references in workflows/precommit/nox | Wire a Semgrep job or remove the config | - |
| CICD-05 | Reusable-workflow SHA skew | Medium | S | container-security.yml, mutation-testing.yml | @a81c5c7 vs @799ebd6 (12 callers) | Pin all org callers to one reviewed SHA | - |
| CICD-06 | basedpyright declared twice | Medium | S | pyproject.toml | :92 >=1.18.0 vs :835 >=1.35.0 | Keep single >=1.35.0 declaration | - |
| CICD-07 | Tool versions float vs pre-commit pins | Medium | M | pyproject.toml, .pre-commit-config.yaml | ruff hook v0.15.13 vs pyproject >=0.9.0; bandit 1.7.10 vs >=1.7.0 | Align pyproject floors to pre-commit revs | - |
| CICD-08 | Qlty complexity looser than standard | Low | S | .qlty/qlty.toml | :86 threshold 10 overridden to 12 at :96 | Restore 10 or document the override | - |
| CICD-09 | Coverage gate split / soft thresholds | Medium | S | pyproject.toml, .codecov.yml, ci.yml | --cov-fail-under=80 (548) vs codecov patch threshold 5% (.codecov.yml:28) | Make cov-fail-under source of truth; tighten Codecov; verify reusable not soft | - |
| CICD-10 | Core CI only tests 3.12 | Low | S | python-compatibility.yml, ci.yml, pyproject.toml | requires-python 3.11-3.13 but core jobs hard-code 3.12 | Run core CI on full range or narrow requires-python | - |
| CICD-11 | pre-commit hooks not enforced in CI | Low | M | .pre-commit-config.yaml, pr-validation.yml | darglint/interrogate/no-em-dash local-only; only vulture in CI | Run pre-commit in CI or confirm org workflow does | - |
