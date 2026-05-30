---
title: "Known Vulnerability Entry Template"
schema_type: common
status: published
owner: core-maintainer
purpose: "Template for documenting deferred vulnerabilities in known-vulnerabilities.md."
tags:
  - security
  - compliance
---

Use this template to document each deferred vulnerability in `docs/known-vulnerabilities.md`.
Copy the block below, fill in all fields, and remove this header section.

Requirements:
- Every `pip-audit` suppression in `pyproject.toml` must have a matching entry here.
- No entry may go unreviewed for more than 60 days (OpenSSF release gate).
- CVE IDs must be added or updated when assigned.

---

## [PYSEC-YYYY-NNNNN / CVE-YYYY-NNNNN]

**Package**: `package-name`
**Affected versions**: `<X.Y.Z`
**Fixed in**: `X.Y.Z` (or "No upstream fix available as of YYYY-MM-DD")
**Discovered**: YYYY-MM-DD
**Entry added**: YYYY-MM-DD
**Reassess by**: YYYY-MM-DD (max 60 days from entry date)

### Description

Brief description of the vulnerability: what it affects, how it can be triggered,
and the CVSS score if available (e.g., CVSS 7.8 AV:N/AC:L).

### Risk Assessment

Explain why the risk is acceptable in this project:
- Is the vulnerable code path reachable from this codebase?
- Is the package only in a dev/optional extra not installed in production?
- Are there mitigating controls (network isolation, input validation, etc.)?

### Mitigation

Describe any active mitigations in place while the vulnerability is deferred:
- Version pin or constraint applied
- Runtime controls
- Monitoring or alerting

### Resolution Plan

- Target resolution date: YYYY-MM-DD
- Blocking issue or upstream PR: https://github.com/...
- Fallback: remove/replace the package if no fix by YYYY-MM-DD

### Audit Trail

| Date | Action | By |
|------|--------|----|
| YYYY-MM-DD | Entry created | @username |
| YYYY-MM-DD | Reassessed: still deferred (reason) | @username |
