# Dependencies and Supply Chain Audit

Repo: ByronWilliamsCPA/audio-processor
Date: 2026-05-29
Domain: dependencies and supply chain (read-only review)
Auditor scope: direct/transitive dependency freshness, lockfile health, language targets, migration residue, SBOM coverage, base images, suppression accuracy.

## Summary of posture

Lockfile is internally consistent (`uv lock --check` passes, 303 packages). No prior-tooling migration residue. Suppressions in `.trivyignore`, `osv-scanner.toml`, and `[tool.pip-audit]` are documented and, where checked against live advisories (PYSEC-2026-161, PYSEC-2026-139 / CVE-2026-4538, PYSEC-2022-42969), accurate. The real dependency debt is two abandoned direct audio packages (ffmpeg-python, pydub) and one deprecated transitive dev package (py).

Note: only the 8 core runtime deps are installed in the active `.venv` (`uv pip list` shows 19 packages total). Dev and all optional extras are not installed locally, so direct vulnerability scanning of extras was done from `uv.lock` plus PyPI metadata, not from a live `pip-audit` run (pip-audit binary is not present in the current venv).

---

## DEP-01: ffmpeg-python is abandoned (last release 2019-07-06)

Severity: High
Effort: M (a few days; needs a maintained replacement and call-site rewrite, basis: it is invoked from the audio pipeline path)

Evidence:
- pyproject.toml:161 `"ffmpeg-python>=0.2.0"` in the `audio` extra.
- uv.lock pins `ffmpeg-python 0.2.0`.
- PyPI: latest and only-current release is 0.2.0, uploaded 2019-07-06. No release in ~6 years 10 months (far past the 18-month threshold).

Recommendation: Plan migration to a maintained wrapper (for example `python-ffmpeg` / `ffmpeg-python` forks that are active, or call `ffmpeg` via `subprocess` directly with validated args). Until then, pin and document; treat as frozen.

---

## DEP-02: pydub is effectively unmaintained (last release 2021-03-10)

Severity: Medium
Effort: M (a few days; pydub leans on audioop, removed in Python 3.13, basis: requires-python allows up to 3.13)

Evidence:
- pyproject.toml:160 `"pydub>=0.25.1"` in the `audio` extra.
- uv.lock pins `pydub 0.25.1`.
- PyPI: latest release 0.25.1, uploaded 2021-03-10. No release in ~5 years 2 months.
- pydub imports `audioop`, which PEP 594 removed from the stdlib in Python 3.13 (deprecated since 3.11). `requires-python = ">=3.11,<3.14"` (pyproject.toml:12) admits 3.13, where pydub will fail to import without the `audioop-lts` backport (not in the lock).

Recommendation: Either drop pydub in favor of librosa/soundfile (already direct deps) for the same operations, or, if kept, add `audioop-lts; python_version >= '3.13'` and test on 3.13. Verify whether pydub is actually imported before investing.

---

## DEP-03: py 1.11.0 deprecated transitive (dev-only), no upstream fix

Severity: Low
Effort: S (under a day; remove by dropping or replacing interrogate, or accept documented risk)

Evidence:
- uv.lock: `py 1.11.0` pulled in by `interrogate 1.7.0` (only dependent in the lock).
- PyPI: py 1.11.0 uploaded 2021-11-04; package self-describes as "maintenance mode... should not be used in new code." No release in ~4 years 6 months.
- Carries PYSEC-2022-42969 / CVE-2022-42969 / GHSA-w596-4wvx-j9j6 (ReDoS in `py.path.svnwc`), suppressed in osv-scanner.toml and `[tool.pip-audit].ignore-vuln` (pyproject.toml:647) with reassess-by 2026-07-16. Suppression reasoning is accurate: dev-only, SVN code path unreachable, excluded from production wheels (Dockerfile runs `uv sync --frozen --no-dev`, Dockerfile:37).

Recommendation: Keep the documented suppression; at the 2026-07-16 reassess, check whether interrogate has dropped `py` (or swap interrogate for `docstr-coverage`/`pydoclint`) to remove the transitive entirely.

---

## DEP-04: Base image digest pin goes stale (no auto security refresh)

Severity: Medium
Effort: S (under a day; bump the digest and re-scan, recurring)

Evidence:
- Dockerfile:7 and Dockerfile:42 both pin `python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203` (builder and runtime).
- `.trivyignore` enumerates ~30 base-image OS-package CVEs (glib, libpng, mesa, gnutls, mbedtls, ncurses, curl, expat, libxml2, libssh, libssh2, perl-base, etc.) all dated Review 2026-05-18 / 2026-05-28 with "no fix available" status. A digest pin means the image will never pick up Debian point-release security updates until the digest is manually bumped, so this CVE list grows until someone re-pins.

Recommendation: Add a scheduled job (or Dependabot/Renovate Docker support) to bump the base-image digest on a cadence and re-run Trivy, so fixed Debian packages land without manual tracking. The digest pin itself is correct for reproducibility; the gap is the refresh cadence.

---

## DEP-05: ClusterFuzzLite Dockerfile uses a floating, unpinned base tag

Severity: Low
Effort: S (under a day; pin to a digest)

Evidence:
- .clusterfuzzlite/Dockerfile:6 `FROM gcr.io/oss-fuzz-base/base-builder-python:v1` (mutable tag, no digest).
- Same file uses `pip3 install --upgrade pip && pip3 install atheris && pip3 install -e .` with no version constraints, so fuzz builds are not reproducible.

Recommendation: Pin the base image by digest and constrain `atheris` to a known version for reproducible fuzz runs. Low severity because this is CI fuzzing infrastructure, not a production or release artifact.

---

## DEP-06: Lockfile health is good (clean area)

Severity: Low (informational)
Effort: n/a

Evidence: `uv lock --check` -> `Resolved 303 packages in 2ms`, exit 0; uv.lock revision 3, `requires-python = ">=3.11, <3.14"` matches pyproject.toml:12. uv.lock last committed 2026-05-28 (one day old). Lock is consistent with pyproject; reproducibility holds.

---

## DEP-07: Migration residue is absent (clean area)

Severity: Low (informational)

Evidence: No `requirements*.txt`, `setup.py`, `setup.cfg`, `poetry.lock`, or `Pipfile*` present (verified by `ls`). Single source of truth is pyproject.toml + uv.lock.

---

## DEP-08: Python version targets are inside support windows (clean area)

Severity: Low (informational)

Evidence: Runtime targets 3.12 (Dockerfile, `[tool.basedpyright].pythonVersion = "3.12"` pyproject.toml:464, ruff `target-version = "py312"` pyproject.toml:210). `requires-python` allows 3.11 to 3.13. As of 2026-05-29: 3.11 security support ends ~2027-10, 3.12 ~2028-10, 3.13 ~2029-10. All in window. One caveat: 3.13 admitted by `requires-python` collides with pydub's removed-`audioop` dependency (see DEP-02); the runtime image uses 3.12 so production is unaffected.

---

## DEP-09: SBOM and suppression accuracy (mostly clean, one stale-comment nuance)

Severity: Low
Effort: S (under a day; tighten one comment)

Evidence:
- SBOM is generated by .github/workflows/sbom.yml calling the org reusable workflow `ByronWilliamsCPA/.github/.github/workflows/python-sbom.yml@799ebd6` (pinned by SHA), CycloneDX format, `fail-on-vulnerabilities: true`, severity threshold CRITICAL,HIGH, triggered on pyproject.toml / uv.lock changes plus weekly cron. `no-build: false` so the editable project is built and included. Coverage is adequate.
- Live cross-checks of suppressions:
  - PYSEC-2026-161 (starlette BadHost, CVE-2026-48710, published 2026-05-22): affected range is all versions through 1.0.0, fixed in 1.0.1 (OSV). The lock pins `starlette 1.1.0` via `fastapi 0.136.3` (constraint `fastapi>=0.133.0`, pyproject.toml:154). The dependency is patched. The inline comment at pyproject.toml:152-153 says "fastapi>=0.133.0 allows starlette>=1.1.0, which contains the fix"; correct in outcome, but the precise fix version is 1.0.1, not 1.1.0. Minor doc imprecision, not a live exposure.
  - PYSEC-2026-139 / CVE-2026-4538 (torch 2.9.1, local-only AV:L, CVSS 7.8): no upstream fixed version exists (OSV shows no fix; the suppression notes the open, unmerged PyTorch PR). torch enters via `[ml]` (direct, pyproject.toml:127) and `[audio]` transitively via silero-vad; the production container installs neither extra (`uv sync --frozen --no-dev`, no `--extra`, Dockerfile:37). Suppression reasoning is accurate.
  - PYSEC-2022-42969 (py): accurate, see DEP-03.
- No suppression checked was found to hide a live, reachable, fixable vulnerability.

Recommendation: Correct the pyproject.toml:152-153 comment to cite the actual fix version (starlette 1.0.1). No functional change needed.

---

## DEP-10: Minor direct-dependency lag (informational)

Severity: Low
Effort: S (under a day; routine lockfile refresh)

Evidence (lock vs upstream as of 2026-05-29):
- arq: lock 0.25.0, constraint `>=0.25.0`; latest 0.28.0 (2026-04-16). Active upstream, three minor versions behind.
- silero-vad: lock 6.2.0; latest 6.2.1 (2026-02-24). One patch behind.
- deepgram-sdk: lock 5.3.0, constraint `>=3.0.0`; actively maintained. Not stale.
- Core deps (pydantic 2.12.5, urllib3 2.7.0, click 8.3.1, rich 14.2.0, structlog 25.5.0, platformdirs 4.5.0) are current.
None of these crosses the 18-month staleness line; listed for completeness so a routine `uv sync --upgrade` can close the gap.

---

## Findings summary table

| ID | Title | Severity | Effort | Files | Evidence | Recommendation | CVE |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DEP-01 | ffmpeg-python abandoned | High | M | pyproject.toml:161, uv.lock | PyPI last release 0.2.0 on 2019-07-06 (~6y10m) | Migrate to maintained wrapper or direct subprocess ffmpeg | none |
| DEP-02 | pydub unmaintained + audioop removed in 3.13 | Medium | M | pyproject.toml:160, pyproject.toml:12 | PyPI last release 0.25.1 on 2021-03-10 (~5y2m); imports removed stdlib audioop | Drop for librosa/soundfile or add audioop-lts for 3.13 | none |
| DEP-03 | py 1.11.0 deprecated transitive (dev) | Low | S | uv.lock (via interrogate), pyproject.toml:647 | PyPI 1.11.0 on 2021-11-04, maintenance-mode; suppression accurate | Keep documented suppression; replace interrogate at 2026-07-16 reassess | CVE-2022-42969 / PYSEC-2022-42969 / GHSA-w596-4wvx-j9j6 |
| DEP-04 | Base image digest pin goes stale | Medium | S | Dockerfile:7, Dockerfile:42, .trivyignore | Digest-pinned python:3.12-slim; ~30 base-image CVEs accruing in .trivyignore (2026-05) | Schedule automated digest bump + Trivy re-scan | (base-image OS CVEs, multiple) |
| DEP-05 | ClusterFuzzLite base tag unpinned | Low | S | .clusterfuzzlite/Dockerfile:6 | `base-builder-python:v1` mutable tag; unpinned pip installs | Pin base by digest; pin atheris version | none |
| DEP-06 | Lockfile consistent (clean) | Low | n/a | uv.lock, pyproject.toml | `uv lock --check` exit 0, 303 packages; requires-python matches | None; maintain | none |
| DEP-07 | No migration residue (clean) | Low | n/a | repo root | No requirements/setup/poetry/Pipfile files | None | none |
| DEP-08 | Python targets in support window (clean) | Low | n/a | Dockerfile, pyproject.toml:12,210,464 | 3.11/3.12/3.13 all supported; prod on 3.12 | None; watch 3.11 EOL ~2027-10 | none |
| DEP-09 | SBOM coverage good; one stale comment | Low | S | .github/workflows/sbom.yml, pyproject.toml:152, osv-scanner.toml | SBOM SHA-pinned, CycloneDX, fail-on HIGH/CRITICAL; suppressions verified accurate; starlette fix is 1.0.1 not 1.1.0 | Fix comment to cite starlette 1.0.1; no functional change | CVE-2026-48710 / PYSEC-2026-161; CVE-2026-4538 / PYSEC-2026-139 |
| DEP-10 | Minor direct-dep version lag (info) | Low | S | uv.lock, pyproject.toml | arq 0.25.0 vs 0.28.0; silero-vad 6.2.0 vs 6.2.1 | Routine `uv sync --upgrade` | none |
