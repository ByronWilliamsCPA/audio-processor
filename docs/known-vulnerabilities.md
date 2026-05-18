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

One known unfixed vulnerability at this time.

Last reviewed: 2026-05-17

---

## PYSEC-2022-42969: py 1.11.0 (ReDoS in svnwc)

| Field | Value |
| --- | --- |
| **ID** | PYSEC-2022-42969 |
| **Package** | `py` == 1.11.0 (transitive, dev only) |
| **CVE** | (none assigned; tracked as PYSEC-2022-42969) |
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
