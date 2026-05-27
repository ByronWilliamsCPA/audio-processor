---
schema_type: common
title: "Known Vulnerabilities"
status: published
owner: core-maintainer
purpose: >-
  Tracks CVEs that cannot be immediately resolved. No entry may age past
  60 days without reassessment; escalate or resolve.
tags:
  - security
  - dependencies
---

> Tracks CVEs that cannot be immediately resolved. No entry may age past 60 days
> without reassessment; escalate or resolve. See
> `docs/known-vulnerabilities-template.md` for the entry schema.

## Status

One Python-dependency CVE (`py` 1.11.0) and a documented baseline of
base-image transitive C library CVEs (catalogued in the section
"Base-image transitive library CVEs" below and suppressed in
`.trivyignore`).

Last reviewed: 2026-05-18

---

## PYSEC-2022-42969: py 1.11.0 (ReDoS in svnwc)

| Field | Value |
| --- | --- |
| **ID** | PYSEC-2022-42969 |
| **Package** | `py` == 1.11.0 (transitive, dev only) |
| **CVE** | CVE-2022-42969 |
| **GHSA** | GHSA-w596-4wvx-j9j6 |
| **Aliases** | PYSEC-2022-42969, CVE-2022-42969, GHSA-w596-4wvx-j9j6 (all three suppressed in `osv-scanner.toml`) |
| **Severity** | High |
| **CVSS Score** | 7.5 (CVSS 3.1 AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H) |
| **Patched version** | None. The `py` library is deprecated and no longer maintained; affected `svnwc` module will not be fixed. |
| **Status** | Deferred (compensating control in place) |
| **Discovered** | 2026-05-17 (during compliance audit PR #28) |
| **Reassess-by** | 2026-07-16 (60-day cap) |

**Exploitation scenario**: The vulnerable code is in `py.path.svnwc.InfoSvnWCCommand`,
a parser for Subversion working-copy metadata. To exploit the ReDoS, an attacker
must control the input to `py.path.svnwc`'s SVN info parsing routine. This
project does not use Subversion, does not import `py.path.svnwc`, and does not
parse untrusted SVN output. The vulnerable code path is unreachable.

**Why deferred**: The `py` package is a transitive dependency pulled in by dev
tooling (mutation testing and related plugins). It is not in the runtime
dependency tree of the published `audio-processor` package; users installing
`pip install audio-processor` never see it. Upstream `py` is unmaintained and
will not receive a fix. Removing the transitive requires waiting for the
dependent dev tools to drop their `py` dependency or replacing them.

**Compensating control**: (1) `py.path.svnwc` is not imported anywhere in this
codebase (verified by `grep -r "svnwc\|py\.path" src/ tests/`). (2) The
vulnerable code path requires SVN integration which this project does not have.
(3) The `py` package is excluded from production wheels (it only appears in
the `dev` extra).

**Planned resolution**: Re-audit at next quarterly dependency review
(2026-07-16). If a transitive source has dropped `py` by then, refresh the
lockfile and remove this entry. If not, request the upstream tool to migrate
away from `py` (raise an issue on the dependent package).

---

## CVE-2026-40393: libgbm1 / mesa-libgallium (Mesa GBM and Gallium driver)

| Field | Value |
| --- | --- |
| **ID** | CVE-2026-40393 |
| **Package** | `libgbm1`, `mesa-libgallium` (base image OS package, transitive via `libavcodec-extra`) |
| **CVE** | CVE-2026-40393 |
| **Severity** | Critical |
| **Patched version** | None. Debian classifies as `will_not_fix`. |
| **Status** | Deferred (compensating control in place) |
| **Discovered** | 2026-05-18 (Trivy scan on PR #29, audio-processor issue #33) |
| **Reassess-by** | 2026-07-17 (60-day cap) |
| **Suppressed in** | `.trivyignore` |

**Exploitation scenario**: The vulnerability is in Mesa's Generic Buffer
Management (GBM) and Gallium driver layer, which provides
hardware-accelerated graphics buffer allocation for GPU rendering. To
exploit it, an attacker would need a local process with access to a DRI
device node (`/dev/dri/*`) capable of submitting crafted graphics buffer
operations.

**Why deferred**: This is a headless server-side audio processing container.
It has no display server, no GPU access, no graphics rendering, and no
`/dev/dri` device mounts. The Mesa libraries are pulled in only as a
transitive dependency of `libavcodec-extra` (the ffmpeg codec extras
package) to support hardware video acceleration codepaths that this audio
service never exercises. The container runs as a non-root user (`appuser`,
UID 1000) without device access. Debian upstream has classified the CVE as
`will_not_fix` because the practical exposure surface is hardware-graphics
clients.

**Compensating control**: (1) Container has no `/dev/dri` access; runs in a
headless server context. (2) No graphics rendering paths are invoked from
application code. (3) Non-root user with no device-node permissions. (4)
The libavcodec-extra dependency is required for audio codec coverage but
the GPU codepaths in ffmpeg are never reached.

**Planned resolution**: Reassess at 2026-07-17. If `libavcodec-extra` ever
becomes droppable (audio codec needs covered by a slimmer ffmpeg package),
remove the transitive Mesa dependency and this entry.

---

## CVE-2026-5673: libtheoradec1 (Theora video decoder)

| Field | Value |
| --- | --- |
| **ID** | CVE-2026-5673 |
| **Package** | `libtheoradec1` (base image OS package, transitive via `libavcodec-extra`) |
| **CVE** | CVE-2026-5673 |
| **Severity** | High |
| **Patched version** | None. Debian classifies as `fix_deferred`. |
| **Status** | Deferred (compensating control in place) |
| **Discovered** | 2026-05-18 (Trivy scan on PR #29, audio-processor issue #33) |
| **Reassess-by** | 2026-07-17 (60-day cap) |
| **Suppressed in** | `.trivyignore` |

**Exploitation scenario**: `libtheoradec1` decodes Ogg Theora video
streams. To exploit it, an attacker must control a Theora-encoded video
stream that the application or its dependencies feed into a Theora decoder.

**Why deferred**: This is an audio processing service. It does not decode
video. `libtheoradec1` is pulled in transitively by `libavcodec-extra`
(ffmpeg's codec extras package) for completeness of codec coverage, but
the application never invokes Theora decoding via ffmpeg. Debian has
classified the CVE as `fix_deferred`, indicating low impact in typical
Debian deployments.

**Compensating control**: (1) The application's ffmpeg invocations are
audio-only (`-vn` flag where applicable, audio-only extraction paths). (2)
No Theora-encoded input is processed by design. (3) The container does not
expose ffmpeg as a service; it is invoked only on trusted local files.

**Planned resolution**: Reassess at 2026-07-17. If Debian backports a fix,
refresh the base image apt layer and remove this entry. If
`libavcodec-extra` becomes droppable in favor of a smaller ffmpeg variant,
removing it would also drop this dependency.

---

## Base-image transitive library CVEs

The remaining suppressions in `.trivyignore` cover CVEs in C libraries that
ship in the `python:3.12-slim` base image (Debian 13 trixie) as transitive
dependencies of build tools (`curl`, `git`), the `libavcodec-extra` ffmpeg
codec extras, and standard glibc-adjacent system libraries. Trivy reported
this set on the PR #29 scan (audio-processor issue #33). None of these
libraries are exercised by the application's request path:

- All outbound TLS in Python code goes through OpenSSL via the
  `cryptography` and `urllib3` packages, **not** GnuTLS, mbedTLS, libssh-4,
  or libssh2-1t64. The C-level TLS libraries are present only because
  `curl` and `ffmpeg` link them.
- `curl` is used only for image-build operations (downloading UV in the
  builder stage) and runtime healthchecks against `localhost`. It does not
  handle untrusted remote endpoints in the request path.
- `libexpat1` and `libxml2` are not invoked anywhere in `src/` (verified
  by `grep -rn "xml\|lxml\|expat" src/ --include="*.py"`). No Python code
  uses `xml.etree`, `lxml`, or any other XML parser.
- The ncurses family (`libncursesw6`, `libtinfo6`, `ncurses-base`) is a
  terminal capability library; this is a headless server with no TTY
  rendering.
- `libsndfile1` is declared as a Python dependency (via `soundfile>=0.12.1`)
  for future audio I/O, but no application code currently invokes it
  (verified by `grep -rn "soundfile\|librosa" src/ --include="*.py"`).
  CVE-2026-37555 is in the IMA ADPCM reader path; even when audio I/O is
  wired up, the application will not process untrusted IMA-encoded WAV
  inputs.

The container also runs as a non-root user (`appuser`, UID 1000) with no
privileged operations or device access. Each CVE family is listed below
with severity, status, and a CVE inventory. All entries share:

- **Discovered**: 2026-05-18 (Trivy scan on PR #29, issue #33)
- **Reassess-by**: 2026-07-17 (60-day cap per CLAUDE.md unfixed-CVE policy)
- **Status**: Deferred (compensating control in place)
- **Suppressed in**: `.trivyignore`
- **Compensating control**: package not invoked in the application request
  path; non-root, no-device container.
- **Planned resolution**: refresh base image apt layer when Debian backports
  fixes; reassess at the 60-day mark. If `libavcodec-extra` becomes droppable
  in favor of a smaller ffmpeg variant, several of these transitive deps
  fall out automatically.

### curl / libcurl4t64

| CVE | Severity | Status | Title |
| --- | --- | --- | --- |
| CVE-2026-5773 | HIGH | affected | wrong SMB file transfer |
| CVE-2026-6276 | HIGH | (Debian-flagged) | cookie information disclosure |

`curl` and `libcurl4t64` ship in the runtime image for build operations and
healthchecks. Application HTTP traffic goes through `urllib3` / `httpx` /
`aiohttp` (Python OpenSSL stack), not libcurl. SMB protocol support is
disabled in Debian's curl build; CVE-2026-5773 is not reachable.

### libexpat1

| CVE | Severity | Title |
| --- | --- | --- |
| CVE-2026-25210 | HIGH | information disclosure / data corruption |
| CVE-2026-45186 | HIGH | computational complexity DoS |

No XML parsing in `src/`. `libexpat1` is present only because system tools
link it. Python's standard library `xml.etree` is not imported anywhere in
the application.

### libgnutls30t64

| CVE | Severity | Status | Title |
| --- | --- | --- | --- |
| CVE-2026-33845 | CRITICAL | (Debian-flagged) | DTLS zero-length DoS |
| CVE-2026-33846 | HIGH | affected | heap buffer overflow DoS |
| CVE-2026-42009 | HIGH | affected | DoS via DTLS packet reordering (added 2026-05-19, surfaced on PR #27 Trivy scan) |
| CVE-2026-42010 | HIGH | (Debian-flagged) | authentication bypass via NUL character |
| CVE-2026-3833 | HIGH | (Debian-flagged) | policy bypass due to case-sensitive comparison |
| CVE-2026-42011 | HIGH | (Debian-flagged) | security bypass via incorrect name validation |

GnuTLS is transitive via curl and ffmpeg. Application Python TLS uses
OpenSSL through `cryptography` / `urllib3`. No untrusted TLS endpoints
are processed via GnuTLS in the application request path.

### libmbedcrypto16

| CVE | Severity | Title |
| --- | --- | --- |
| CVE-2026-34873 | CRITICAL | client impersonation during TLS 1.3 |
| CVE-2026-34875 | HIGH | arbitrary code execution |
| CVE-2026-25835 | HIGH | improper API misuse |
| CVE-2026-34872 | HIGH | shared secret leak |

Mbed TLS is transitive via ffmpeg's TLS-capable codec backends. Application
code does not invoke any ffmpeg codepaths that perform TLS handshakes;
ffmpeg here operates on trusted on-disk audio inputs only.

### ncurses family

| CVE | Severity | Packages | Title |
| --- | --- | --- | --- |
| CVE-2025-69720 | HIGH | libncursesw6, libtinfo6, ncurses-base | buffer overflow in terminal capability parsing |

Terminal library; headless service, no TTY rendering. Not reachable from
application code.

### libsndfile1

| CVE | Severity | Status | Title |
| --- | --- | --- | --- |
| CVE-2026-37555 | HIGH | fix_deferred (Debian) | integer overflow in `ima_reader_init()` |

`libsndfile1` (via Python `soundfile`) is a declared dependency for future
audio I/O. No application code currently invokes it. CVE is specific to the
IMA ADPCM WAV decoder; the application's planned audio pipeline does not
ingest untrusted IMA-encoded inputs. Reassess once audio I/O is implemented.

### libssh-4 / libssh2-1t64

| CVE | Severity | Status | Package | Title |
| --- | --- | --- | --- | --- |
| CVE-2026-0966 | HIGH | affected | libssh-4 | DoS via zero-length input |
| CVE-2026-3731 | HIGH | (Debian-flagged) | libssh-4 | DoS via out-of-bounds read |
| CVE-2026-7598 | CRITICAL | affected | libssh2-1t64 | integer overflow via large username/password |

SSH client libraries pulled in transitively by `curl` (SSH protocol support
in libcurl) and `git`. The application does not initiate SSH connections.

### libxml2

| CVE | Severity | Title |
| --- | --- | --- |
| CVE-2026-6732 | HIGH | DoS via crafted XML input |

Same reachability story as `libexpat1`: no XML parsing in `src/`.

---

## PYSEC-2026-139 / CVE-2026-4538: torch 2.9.1

| Field | Value |
| --- | --- |
| **ID** | PYSEC-2026-139 |
| **Package** | `torch` >= 2.9.0 (direct, optional `[ml]` extra) |
| **CVE** | CVE-2026-4538 |
| **Severity** | High |
| **CVSS Score** | 7.8 (CVSS:3.1 AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H) |
| **Patched version** | None. PyTorch PR #176791 is open but unmerged; OSV marks `last_affected` as 2.10.0 with no fixed version identified. |
| **Status** | Deferred (compensating control in place) |
| **Discovered** | 2026-05-27 (OSV scanner failure on PRs #39, #40, #41) |
| **Reassess-by** | 2026-07-26 (60-day cap) |
| **Suppressed in** | `osv-scanner.toml`, `[tool.pip-audit] ignore-vuln` in `pyproject.toml` |

**Exploitation scenario**: The vulnerability requires a local attacker with a valid
user account on the same host to supply crafted input to the torch runtime. The
attack vector is local (AV:L), meaning remote exploitation is not possible.

**Why deferred**: `torch` is declared in the optional `[ml]` extra group and is not
installed in the production Docker container (which installs only the `audio` extra).
The deployed audio processing service uses `librosa`, `pydub`, and `silero-vad` for
audio work; `torch` is never imported by any code path that runs in production. No
patched release exists at time of writing.

**Compensating control**: (1) `torch` is absent from the production container image.
(2) The attack vector is local-only (AV:L); the service runs in a containerised, non-root
environment with no local user accounts accessible to external parties. (3) No production
code path imports `torch` (verified by `grep -rn "import torch" src/`).

**Planned resolution**: Reassess 2026-07-26. Check PyTorch PR #176791 and the OSV
advisory for a patched release. If a fix ships before the reassessment date, upgrade
the `torch>=` constraint in `pyproject.toml`, regenerate `uv.lock`, and remove this
entry and its `osv-scanner.toml` suppression.

---

## OSSF Scorecard Approved Deviations

This section tracks Scorecard check results where an approved deviation is in
place. Each entry names the compensating controls and the reassessment trigger.

### SCORECARD:Branch-Protection

Solo-dev exception. Required approving review count is 0 by org policy
(single maintainer). Compensating controls: require_code_owner_review=true,
required_signatures=true, copilot_code_review=true, dismiss_stale_reviews=true.
Reassess: when team size grows to 2+ active maintainers.

<!-- To add a new entry, copy the schema below and fill in the fields. -->
<!--
## CVE-YYYY-XXXXX: Package Name vX.Y

| Field | Value |
| --- | --- |
| **ID** | CVE-YYYY-XXXXX |
| **Package** | package-name >= X.Y, < X.Z |
| **CVE** | CVE-YYYY-XXXXX |
| **Severity** | Critical / High / Medium |
| **CVSS Score** | X.X |
| **Patched version** | X.Z (not yet released / available but breaks X) |
| **Status** | Deferred / In Progress / Resolved |
| **Discovered** | YYYY-MM-DD |
| **Reassess-by** | YYYY-MM-DD (60 days max) |

**Exploitation scenario**: Describe what an attacker needs to exploit this in your context.

**Why deferred**: Specific reason: upstream unpatched, breaking API change required, etc.

**Compensating control**: What reduces the risk while the CVE remains open.

**Planned resolution**: Target version, migration path, or timeline.
-->
