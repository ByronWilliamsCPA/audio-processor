# Security and Secrets Audit: audio-processor

Date: 2026-05-29
Scope: Hardcoded secrets, dependency CVEs, insecure code patterns, GitHub Actions posture, FastAPI input validation, Dockerfile security.
Method: Read-only review. No tracked files modified. pip-audit binary not installed in the environment; dependency versions cross-checked against `uv.lock`, suppression configs, and `docs/known-vulnerabilities.md`.

Overall posture is strong. Suppressions are well-justified and current, secrets hygiene is clean, subprocess usage is shell-free, the Dockerfile is SHA-pinned and non-root, and GitHub Actions are SHA-pinned with scoped permissions. The material gaps are at the application layer: the public API has no authentication and the upload size limit is bypassable.

---

## SEC-01: Audio processing API has no authentication or authorization

Severity: High
Effort: M (few days: pick auth scheme, add dependency, wire into routes, tests)

Evidence:
- `src/audio_processor/api/routes.py` defines `POST /api/v1/process`, `GET /status/{job_id}`, `GET /results/{job_id}`, `GET /artifacts/{job_id}/{artifact_name}` with zero auth dependencies. `grep -cE "Depends|Security|Bearer" src/audio_processor/api/routes.py` returns 0.
- `src/audio_processor/api/__init__.py:43` creates the FastAPI app with no auth middleware.
- Any caller can upload files (each call invokes ffmpeg/ffprobe subprocesses and consumes disk under `audio_temp_dir`) and read any job's results given a UUID.

Recommendation: Add an authentication dependency (API key header or OAuth2/JWT bearer) applied at the router level, and authorize results/artifact reads against the caller's identity rather than job-id-only.

---

## SEC-02: Upload size limit is bypassable; full body read into memory

Severity: High
Effort: S (under a day: enforce a streamed byte cap during read)

Evidence:
- `src/audio_processor/api/routes.py:117-127` checks size from the `content-length` request header only. A client can omit or understate `content-length`; the check is then skipped (`if content_length:`), or passes with a false value.
- `src/audio_processor/api/routes.py:156` then does `content = await file.read()`, loading the entire upload into memory with no cap, before any size enforcement. `validate_file` checks size only after the file is already fully written to disk (`audio_converter.py:517-521`).
- A `audio_max_file_size_mb` default of 500 (`core/config.py:91`) means a single unauthenticated request (see SEC-01) can drive a memory/disk DoS well past intended limits.
- Minor: the 413 message at line 126 reports `settings.audio_max_file_size_mb` while the comparison at line 123 uses `settings.max_file_size_bytes`; consistent but worth noting the message unit.

Recommendation: Stream the upload in chunks and abort once cumulative bytes exceed `settings.max_file_size_bytes`, rather than trusting `content-length` or buffering the whole body.

---

## SEC-03: torch 2.9.1 unpatched local-code-execution CVE present in optional extras

Severity: Medium
Effort: S (monitor upstream; bump constraint when fix ships)
CVE: CVE-2026-4538 (PYSEC-2026-139), CVSS 7.8 (AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H)

Evidence:
- `uv.lock` pins `torch` 2.9.1. No upstream fix exists (PyTorch PR #176791 open/unmerged; OSV last_affected 2.10.0, no fixed version).
- Suppressed in `osv-scanner.toml` and `pyproject.toml:648-653` (`[tool.pip-audit] ignore-vuln`).
- Suppression is valid: vector is local-only, torch enters via `[ml]` (direct) and `[audio]` (transitive via silero-vad) extras, and the production Dockerfile runs `uv sync --frozen --no-dev` with no `--extra` flags (`Dockerfile:31,37`), so torch is absent from the runtime image. Documented in `docs/known-vulnerabilities.md` with reassess-by 2026-07-26.

Recommendation: Keep the suppression; on reassess (2026-07-26) bump `torch>=` once a fixed release lands and drop the suppression. No action needed for the production image.

---

## SEC-04: py 1.11.0 unmaintained ReDoS CVE in dev-only transitive dependency

Severity: Low
Effort: S (drop when dev tool removes the dependency)
CVE: CVE-2022-42969 (PYSEC-2022-42969, GHSA-w596-4wvx-j9j6), CVSS 7.5, DISPUTED

Evidence:
- `uv.lock` pins `py` 1.11.0 (transitive via dev tooling). Vulnerable code is `py.path.svnwc`, not imported anywhere (`grep` confirms). Suppressed in `osv-scanner.toml` and `pyproject.toml:647`. Documented in `docs/known-vulnerabilities.md`, reassess-by 2026-07-16.

Recommendation: Keep the suppression; revisit at the next dependency review and remove once the dev tool drops `py`.

---

## SEC-05: PYSEC-2026-161 (fastapi/starlette) suppression note is stale; already patched

Severity: Low
Effort: S (documentation cleanup only)
CVE: PYSEC-2026-161

Evidence:
- `pyproject.toml:152-154` carries a comment referencing PYSEC-2026-161 and constrains `fastapi>=0.133.0`. The installed versions in `uv.lock` are fastapi 0.136.3 and starlette 1.1.0, which contain the fix. The vulnerability is resolved, not suppressed; no active `ignore-vuln` entry exists for it (only the explanatory comment).

Recommendation: No security risk. Optionally simplify the comment to note the issue is fixed by the pinned versions to avoid future confusion. No live suppression hides this issue.

---

## SEC-06: Sentry before_send scrubbing is shallow and key-list-limited

Severity: Medium
Effort: S (deepen redaction, add query-string and nested scrubbing)

Evidence:
- `src/audio_processor/core/sentry.py:198-208` redacts only top-level keys in `request["data"]` and only for the fixed set `{"password", "token", "api_key", "secret"}`. Nested dicts, list bodies, headers (e.g. `Authorization`), and the URL query string are not scrubbed. Deepgram/Modal/HuggingFace tokens or `?token=` query values (see the redis URL `redis://:password@` pattern in `.env.example:206`) would not be caught.
- Mitigations present: `send_default_pii=False` (`sentry.py:122`) and the global exception handler returns a generic message (`api/__init__.py:112-120`), so internal details are not leaked to HTTP clients.

Recommendation: Recurse into nested structures, scrub request headers and the URL query string, and match key names case-insensitively with substring matching (e.g. any key containing "token"/"secret"/"key"/"auth").

---

## SEC-07: One reusable-workflow reference in docs uses a moving `@main` ref (not in active workflows)

Severity: Low
Effort: S (doc edit)

Evidence:
- `.github/workflows/README.md:162` shows `uses: ByronWilliamsCPA/.github/.github/workflows/python-ci.yml@main` (documentation example, not an executed workflow).
- All 16 active reusable-workflow references are commit-SHA pinned (e.g. `@799ebd63...`, `@a81c5c7d...`), and every third-party action across workflows is 40-hex SHA pinned (`step-security/harden-runner`, `actions/checkout`, `sigstore/cosign-installer`, etc.). No SHA-unpinned action runs in CI.

Recommendation: Update the README example to a pinned SHA to model the correct pattern. No runtime exposure.

---

## Clean areas (no findings)

- Hardcoded secrets in source: clean. `.secrets.baseline` (v1.5.0, generated 2026-05-28) lists only placeholders/test fixtures in `.cruft.json`, two workflows, `.qlty/qlty.toml`, `.standards/env.example.baseline`, and `tests/unit/test_sentry.py`; all baselined entries still exist and no un-baselined live secret was found. Source uses `SecretStr` (`core/config.py:47`) and `get_secret_value()` only at the SDK boundary (`deepgram_client.py:87`); test keys carry `# pragma: allowlist secret`.
- Shell injection: clean. Every subprocess call uses an argv list with `shell=False` (default): `preprocessing/ffmpeg.py:88`, `audio_converter.py:162,382,463`, `core/sentry.py:147`. No `shell=True`, `os.system`, `eval`, or `exec` in `src/`.
- Unsafe deserialization: clean. No `pickle`, no `yaml.load`, no `torch.load` on untrusted input. Cache and job stores use `json.loads` only (`core/cache.py:169,260`, `jobs/audio_tasks.py:337,339`).
- Exception swallowing: clean. No bare `except:` or silent `except Exception: pass` in `src/`. The two broad catches in `core/sentry.py:155,164` are tagged `# noqa: BLE001` with intent and log at debug; `audio_converter.py:251,268` catch narrow domain exceptions.
- Path traversal on artifact download: not exploitable. `api/routes.py:443` validates `artifact_name` against the `ARTIFACT_CONTENT_TYPES` whitelist before use, and content is served from an in-memory dict, not the filesystem. Upload temp names come from `tempfile.mkstemp` with only the suffix derived from the user filename (`routes.py:148-153`).
- Dockerfile: strong. SHA-digest-pinned base `python:3.12-slim@sha256:090ba77e...` and UV `0.11.16@sha256:440fd647...` (`Dockerfile:7,24,42`), non-root `appuser` UID 1000 (`Dockerfile:75,101`), multi-stage build, `apt-get upgrade` for libpng CVEs, no secrets baked into layers (compose injects `DEEPGRAM_API_KEY` via env, `docker-compose.yml:28,112`).
- GitHub Actions permissions: every workflow declares a top-level `permissions:` block; write scopes are minimal and purpose-commented (`id-token: write` only for OIDC publish/sign/scorecard, `contents: write` only for release/docs/slsa).
- Untrusted input into `run:` steps: safe. `github.event.*` appears only in concurrency groups, `if:` conditions, and as env-var indirection (`RELEASE_TAG: ${{ github.event.release.tag_name }}` then `"$RELEASE_TAG"` in `release-sign.yml:34-82`); no direct interpolation of attacker-controlled data into shell bodies.
- Trivy base-image CVE suppressions: all entries in `.trivyignore` carry justification, review date, and a 60-day reassess cap; cross-referenced in `docs/known-vulnerabilities.md`. These are OS-package CVEs in transitive C libraries (curl/ffmpeg/dpkg deps) not exercised by the request path; no stale suppression found hiding a now-fixed Python issue.

---

## Summary table

| ID | Title | Severity | Effort | Files | Evidence | Recommendation | CVE |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SEC-01 | API has no authentication/authorization | High | M | src/audio_processor/api/routes.py, api/__init__.py | 0 auth deps; all routes public | Add router-level auth dependency; authorize result/artifact reads per-caller | - |
| SEC-02 | Upload size limit bypassable, full body read into memory | High | S | src/audio_processor/api/routes.py:117-127,156; audio_converter.py:517 | Size check trusts content-length header then `await file.read()` unbounded | Stream and cap bytes during read against max_file_size_bytes | - |
| SEC-03 | torch 2.9.1 unpatched local-CE CVE in optional extras | Medium | S | uv.lock, osv-scanner.toml, pyproject.toml:648-653 | No upstream fix; absent from prod image via no-extra build | Keep suppression; bump torch when fix ships (reassess 2026-07-26) | CVE-2026-4538 / PYSEC-2026-139 |
| SEC-04 | py 1.11.0 ReDoS in dev-only transitive dep | Low | S | uv.lock, osv-scanner.toml, pyproject.toml:647 | svnwc unused; dev-only, excluded from wheels | Keep suppression; remove when dev tool drops py | CVE-2022-42969 / PYSEC-2022-42969 |
| SEC-05 | PYSEC-2026-161 suppression note stale (already patched) | Low | S | pyproject.toml:152-154; uv.lock | fastapi 0.136.3 / starlette 1.1.0 contain the fix | Clarify comment; no live suppression | PYSEC-2026-161 |
| SEC-06 | Sentry scrubbing shallow and key-list-limited | Medium | S | src/audio_processor/core/sentry.py:198-208 | Top-level keys only; headers/query/nested not scrubbed | Recurse, scrub headers+query, case-insensitive substring match | - |
| SEC-07 | README example uses moving @main reusable-workflow ref | Low | S | .github/workflows/README.md:162 | Doc example unpinned; all active refs SHA-pinned | Pin the README example to a SHA | - |
