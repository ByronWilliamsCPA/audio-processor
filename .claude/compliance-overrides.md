# Compliance Overrides

This file documents cases where a standards check is satisfied by an equivalent
mechanism rather than the canonical implementation.

## CI-037: PR Title Conventional Commit Enforcement

**Check**: Require a dedicated `pr-title.yml` using `amannn/action-semantic-pull-request`.

**Disposition**: Implemented as `pr-title.yml` (created 2026-05-16). The org-level
`python-pr-validation.yml` reusable workflow exposes `require-conventional-commits`
input, but `pr-validation.yml` in this repo delegates to `python-ci.yml` (not
`python-pr-validation.yml`) and does not pass that parameter. Therefore, the
standalone `pr-title.yml` was created to provide this enforcement.

**Related file**: `.github/workflows/pr-validation.yml` (core validation via python-ci.yml)

**Implementation note**: `pr-title.yml` uses harden-runner with
`egress-policy: block` and an explicit `allowed-endpoints` list covering
`api.github.com:443`, `github.com:443`, and `objects.githubusercontent.com:443`.
A prior version omitted the allow-list and self-bricked the workflow; the
allow-list was added after the first run failed.
