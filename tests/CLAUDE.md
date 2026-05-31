# Tests: Folder-Level Guidelines

> Scope: `tests/` only. Root `CLAUDE.md` rules apply everywhere else.

## Coverage thresholds

Mechanically enforced:

| Metric | Gate | Source |
|---|---|---|
| Line coverage (overall) | 80% minimum | `pyproject.toml` `--cov-fail-under=80`; CI `coverage-threshold: 80` |
| Patch coverage (default) | 80% target | `codecov.yml` `patch.target` |
| Project coverage (`unit` flag) | 85% target | `codecov.yml` `flag_management` unit project |
| Patch coverage (`unit` flag) | 90% target | `codecov.yml` `flag_management` unit patch |

Aspirational (not mechanically gated): 70% branch coverage; 90% on critical paths (auth, data integrity).

## Directory structure

- `tests/unit/`: fast, isolated tests; all external I/O mocked.
- `tests/integration/`: tests that hit real external services or a local Docker stack.
- `tests/conftest.py`: shared fixtures only; no test logic.

## Fixture conventions

- Use `pytest.fixture` with explicit `scope` (`function` default, `session` for expensive setups).
- Mock external services at the boundary (`services/` layer), not inside the service implementation.
- Audio file fixtures live in `tests/fixtures/audio/`: use short (<5s), royalty-free samples.

## Golden file policy

Golden files (expected output snapshots) live in `tests/fixtures/golden/`.
Update them intentionally with `--update-golden` flag; never auto-update in CI.
Regenerating a golden file counts as a test change and requires reviewer sign-off.

## Do not

- Run linters, type checkers, or formatters inside test functions; that belongs in pre-commit.
- Import from `tests/` in production code.
- Use `time.sleep` in tests; use `freezegun` or mock time instead.
