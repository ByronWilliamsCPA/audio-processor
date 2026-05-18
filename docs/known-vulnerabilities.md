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

Five known unfixed vulnerabilities at this time: one Python dependency
(`py` 1.11.0), and four base-image OS packages suppressed in `.trivyignore`
(libgbm1/mesa-libgallium, gnutls28, libtheoradec1, libpng16-16t64 group).

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

## CVE-2026-33846: gnutls28 (GnuTLS)

| Field | Value |
| --- | --- |
| **ID** | CVE-2026-33846 |
| **Package** | `gnutls28` (base image OS package, transitive via `curl`, `ffmpeg`) |
| **CVE** | CVE-2026-33846 |
| **Severity** | High |
| **Patched version** | None. No upstream fix has been released. |
| **Status** | Deferred (compensating control in place) |
| **Discovered** | 2026-05-18 (Trivy scan on PR #29, audio-processor issue #33) |
| **Reassess-by** | 2026-07-17 (60-day cap) |
| **Suppressed in** | `.trivyignore` |

**Exploitation scenario**: GnuTLS handles TLS handshake and certificate
processing. To exploit this CVE, an attacker would need to control the
server side of a TLS connection initiated by a GnuTLS-linked client in the
container (i.e. the application would need to make outbound TLS calls
through a GnuTLS-using tool, against an attacker-controlled endpoint).

**Why deferred**: The application's Python code uses OpenSSL for all
outbound TLS, via the `cryptography` and `urllib3` packages. GnuTLS is
present only because it is a transitive dependency of `curl` and parts of
`ffmpeg` in the base image. Neither `curl` (used only as a build tool and
healthcheck) nor `ffmpeg` (used for audio extraction/conversion against
trusted on-disk files) makes outbound TLS calls to untrusted endpoints in
the application's request path. Upstream GnuTLS has not yet published a
fix; Debian's security tracker shows no fix candidate.

**Compensating control**: (1) Outbound TLS in application code goes through
OpenSSL, not GnuTLS. (2) `curl` is not used in the runtime request path;
the runtime image keeps it only for image-build conveniences and container
healthchecks against `localhost`. (3) `ffmpeg` operates on local files
only; no TLS endpoints involved.

**Planned resolution**: Monitor upstream GnuTLS for a release containing
the fix. Reassess at 2026-07-17. If a fix lands earlier, refresh the base
image apt layer and remove this entry.

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
