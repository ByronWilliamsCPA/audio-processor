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

### PYSEC-2022-42969: py 1.11.0 (transitive dependency)

| Field | Value |
| --- | --- |
| **ID** | PYSEC-2022-42969 |
| **Package** | py 1.11.0 (transitive via interrogate, dev-only) |
| **CVE** | PYSEC-2022-42969 (no CVE assigned) |
| **Severity** | Medium (CVSS 7.5 disputed) |
| **CVSS Score** | 7.5 |
| **Patched version** | None; the `py` library has been unmaintained since 2022 |
| **Status** | Deferred (vulnerable code path unused in this project) |
| **Discovered** | 2026-05-17 |
| **Reassess-by** | 2026-07-16 (60 days max) |

**Exploitation scenario**: The vulnerability is a regular-expression denial-of-service
in `py.path.svnwc.InfoSvnWCCommand`, reached only when parsing untrusted output of
the `svn info` command. This project does not invoke Subversion, does not use
`py.path.svnwc`, and `py` is pulled in solely as a transitive dependency of
`interrogate` (the docstring-coverage tool used in development).

**Why deferred**: Upstream is unmaintained; no fix version exists or is expected.
Removing `py` requires replacing `interrogate` with a different docstring-coverage
tool, which is out of scope for a security cleanup pass.

**Compensating control**: The vulnerable code path is never reached in this
project's runtime or test suite. `py` is dev-only and not shipped with the
package; production deployments do not include it.

**Planned resolution**: Track upstream interrogate's roadmap for removing the
`py` dependency. If `interrogate` does not drop `py` by the next reassessment,
evaluate replacements (e.g., `docstr-coverage`, `darglint` already used here).
The pip-audit ignore entry in `pyproject.toml` documents the deferral.

Last reviewed: 2026-05-17

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
