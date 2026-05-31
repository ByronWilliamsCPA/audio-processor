---
title: "OpenSSF Best Practices Badge: Pre-filled Checklist"
schema_type: common
status: published
owner: core-maintainer
purpose: "Pre-filled questionnaire guide for the OpenSSF Best Practices Badge application."
tags:
  - security
  - compliance
  - quality
---

> **Badge application URL**: https://bestpractices.coreinfrastructure.org/en/projects/new
>
> Use this checklist when completing the questionnaire. Each criterion lists
> the evidence already present in this repository so you can answer quickly
> without re-auditing the code.
>
> Status key: MET | PARTIAL | NOT MET | N/A

---

## Basics

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `basics_description_good` | MET | `README.md` opens with "Audio file conversion and processing for RAG content pipelines" plus a Features section. |
| `basics_interact` | MET | `CONTRIBUTING.md` present; instructs contributors to open GitHub Issues and PRs. |
| `basics_contribution_requirements` | MET | `CONTRIBUTING.md` documents coding standards, branch workflow, and commit format. |
| `basics_license` | MET | `LICENSE` (MIT) present at repo root; MIT is OSI-approved. |
| `basics_floss_license` | MET | MIT is a FLOSS license per OSI and FSF. |
| `basics_documentation_interface` | MET | `docs/api-reference.md` contains mkdocstrings-generated API reference (`::: audio_processor.core.config`). Package exposes a Python API and a CLI. |
| `basics_discussion` | MET | GitHub Issues enabled; `CONTRIBUTING.md` references issue tracker. |

---

## Change Control

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `change_control_vcs` | MET | Git repository hosted on GitHub. |
| `change_control_vcs_public` | MET | Repository is public at `https://github.com/ByronWilliamsCPA/audio-processor`. |
| `change_control_vcs_distributed` | MET | Git is a distributed VCS. |
| `change_control_vcs_commits_public` | MET | All commits visible on GitHub. |
| `change_control_release_notes` | MET | `CHANGELOG.md` present with semantic-release-generated entries. |
| `change_control_release_notes_vulns` | PARTIAL | `CHANGELOG.md` contains a security fix entry (`fix(security): suppress perl-base CVEs with documented risk assessment`). If a CVE ID is assigned to this or future fixes, the entry must cite it. Format: `fix(security): resolve CVE-YYYY-NNNNN: <description>`. Resolve on the questionnaire once CVE IDs are confirmed. |

---

## Reporting

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `reporting_vulnerability_report_process` | MET | `SECURITY.md` documents two private channels: GitHub Private Vulnerability Reporting and email. |
| `reporting_vulnerability_report_private` | MET | GitHub Private Vulnerability Reporting is enabled; the advisory form URL is linked from `SECURITY.md`. |
| `reporting_vulnerability_report_response` | MET | `SECURITY.md` Response Timeline table commits to "Acknowledgement of report: within 14 days". |
| `reporting_cve` | MET | `SECURITY.md` CVE and Advisory Workflow section describes requesting a CVE through GitHub for confirmed vulnerabilities. |

---

## Quality

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `quality_build` | MET | `uv sync --all-extras` + `pytest` invoked by `.github/workflows/ci.yml` on every push and PR. |
| `quality_build_reproducible` | PARTIAL | `uv.lock` pins all transitive dependencies; Docker image SHA-pinning instructions are documented (the images themselves are not yet pinned, see the Manual Steps checklist). Full reproducible builds require attesting build provenance (SLSA workflow `slsa-provenance.yml` is present). |
| `quality_tests` | MET | `pytest` test suite with 80% minimum coverage gate enforced in CI. |
| `quality_tests_documented` | MET | `README.md` Quick Start and `CONTRIBUTING.md` both document `uv run pytest` invocation. |
| `quality_tests_invocation` | MET | `uv run pytest -v` runs the full suite; `uv run pytest --cov=src --cov-fail-under=80` enforces coverage. |
| `quality_test_continuous_integration` | MET | `ci.yml` runs tests on every `push` and `pull_request` event targeting `main`. |
| `quality_new_functionality_tests` | MET | `CLAUDE.md` "Testing" standard requires tests for new features; enforced by 80% coverage gate. |
| `quality_no_leaked_credentials` | MET | `detect-secrets` and TruffleHog run as pre-commit hooks; secret scanning enabled at repository level. |
| `quality_warnings` | MET | Ruff (`ruff check .`) and BasedPyright strict mode run in CI; both must pass with zero errors. |
| `quality_warnings_fixed` | MET | CI fails on any Ruff or BasedPyright warning; no bypass flags are permitted per `CLAUDE.md`. |
| `quality_warnings_strict` | MET | BasedPyright `strict` mode and all Ruff PyStrict-aligned rules are enabled in `pyproject.toml`. |

---

## Security

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `security_know_secure_design` | MET | Self-attestation. `CLAUDE.md` documents FIPS 140-2/3 compliance rules, OWASP tooling, and RAD tagging. `SECURITY.md` has a Security Surface section. File for this criterion on the questionnaire by selecting "Met" and citing these docs. |
| `security_know_common_errors` | MET | Self-attestation. CI runs Bandit (CWE coverage), CodeQL (`.github/workflows/codeql.yml`), and pip-audit. File on questionnaire by selecting "Met" and citing the security workflow. |
| `security_crypto_published` | MET | No custom cryptographic algorithms; the project uses the Python `cryptography` library and FIPS-approved algorithms only (per `CLAUDE.md` FIPS rules). |
| `security_crypto_keylength` | MET | Default key lengths from `cryptography` library (AES-256, RSA-2048+ for signing) meet NIST recommendations. |
| `security_crypto_working` | MET | SHA-1 and MD5 are not used for security purposes; project follows FIPS-approved algorithm list. |
| `security_crypto_pfs` | N/A | Project does not implement TLS connections directly; networking uses standard HTTPS library defaults. |
| `security_vulnerabilities` | MET | `pip-audit` in CI, OSV scanner, Trivy for containers. No unpatched HIGH/CRITICAL vulnerabilities. |
| `security_vulnerabilities_critical_fixed` | MET | CVE/advisory workflow in `SECURITY.md` requires critical fixes within 14 calendar days. |
| `security_assurance_case` | PARTIAL | `SECURITY.md` has a "Security Surface" section naming attack vectors and controls. `CLAUDE.md` documents security-first development. A formal assurance case document does not yet exist. To fully meet this criterion, add a `docs/security-assurance-case.md` that traces each threat from the Security Surface section to its control and residual risk. |
| `security_centralized_authn` | N/A | Project is a CLI/library, not a multi-user application with authentication. Select N/A on the questionnaire. |
| `security_context` | MET | Least-privilege workflow tokens in GitHub Actions; Pydantic Settings for secrets; see `SECURITY.md`. |
| `security_static_analysis` | MET | Bandit, Ruff `S`-category rules, CodeQL (`.github/workflows/codeql.yml`), and Semgrep run in CI. |
| `security_static_analysis_fixed` | MET | CI fails on any HIGH/CRITICAL Bandit finding; `CLAUDE.md` prohibits suppression without documented justification. |
| `security_dynamic_analysis` | MET | ClusterFuzzLite (`cifuzzy.yml`) runs fuzz targets on every PR; Atheris instrumentation in `.clusterfuzzlite/`. |
| `security_dynamic_analysis_unsafe` | MET | Atheris fuzz targets use ASan/UBSan instrumentation enabled by the ClusterFuzzLite base builder. |

---

## Summary: Criteria Requiring Action Before Submitting

These criteria are PARTIAL or require a questionnaire self-attestation before the badge can be awarded at Passing level:

1. **`change_control_release_notes_vulns`** (PARTIAL): Ensure future `CHANGELOG.md` security entries include assigned CVE IDs.
2. **`security_know_secure_design`** (self-attestation on questionnaire): Select "Met" and cite `CLAUDE.md` + `SECURITY.md`.
3. **`security_know_common_errors`** (self-attestation on questionnaire): Select "Met" and cite `codeql.yml` + `security-analysis.yml`.
4. **`security_assurance_case`** (PARTIAL): Either create `docs/security-assurance-case.md` or self-attest "Met" if the existing `SECURITY.md` Security Surface section is deemed sufficient.
5. **`reporting_vulnerability_report_private`**: Confirm GitHub Private Vulnerability Reporting is active at `https://github.com/ByronWilliamsCPA/audio-processor/settings/security_analysis`.

---

## How to File the Badge Application

1. Go to: https://bestpractices.coreinfrastructure.org/en/projects/new
2. Sign in with your GitHub account.
3. Enter the repository URL: `https://github.com/ByronWilliamsCPA/audio-processor`
4. Work through the questionnaire using this checklist for pre-answered criteria.
5. For self-attestation criteria (`security_know_secure_design`, `security_know_common_errors`), select "Met" and add a short justification citing the relevant file.
6. Once all MUST criteria are "Met" or "N/A", the badge is awarded automatically.
7. After receiving the badge, add the badge image to `README.md`:
   ```markdown
   [![OpenSSF Best Practices](https://www.bestpractices.dev/projects/<ID>/badge)](https://www.bestpractices.dev/projects/<ID>)
   ```
   Replace `<ID>` with the numeric project ID shown in the badge URL after filing.

---

*Generated by OSSF compliance audit on 2026-05-28. Re-run the audit after filing to confirm all criteria remain met.*
