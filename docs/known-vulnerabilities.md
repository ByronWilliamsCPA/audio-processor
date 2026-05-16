---
schema_type: common
title: "Known Vulnerabilities"
status: published
owner: core-maintainer
purpose: "Tracks CVEs that cannot be immediately resolved. Review quarterly; no entry may age past 60 days without reassessment."
tags:
  - security
  - dependencies
---

> Tracks CVEs that cannot be immediately resolved. Review quarterly.
> No entry may age past 60 days without reassessment; escalate or resolve.
> See `docs/known-vulnerabilities-template.md` in the global `.claude/docs/` directory
> for the entry schema to follow when adding new CVEs.

## Status

No known unfixed vulnerabilities at this time.

Last reviewed: 2026-05-16

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
