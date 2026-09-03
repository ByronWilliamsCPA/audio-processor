---
title: "Test Plan: Closing the Suite Gaps Behind the 2026-07-02 Review Findings"
schema_type: planning
status: published
owner: core-maintainer
purpose: "Diagnose why the existing test suite missed review findings 1-4, and specify the tiers, fixtures, and concrete tests that catch each failure class — not just each instance."
tags:
  - testing
  - reliability
  - planning
component: Development-Tools
source: "Systems design review 2026-07-02"
---

> **Status**: Accepted
> **Date**: 2026-07-02
> **Relates to**: ADR-003 (async execution model), ADR-004 (job lifecycle),
> systems design review findings 1–4

## Purpose

The suite has ~20 unit test modules, an 80% coverage gate, and green CI — and
it shipped a system in which **every enqueue-enabled submission crashes**
(Finding 1) and **the shipped compose deployment cannot process a job
end-to-end** (Finding 2). Coverage measured the wrong thing: lines executed,
not behavior exercised. This plan names the four structural gaps that let
findings 1–4 through, then specifies the tests that close each *class*. The
per-feature acceptance tests in ADR-003 §Acceptance and ADR-004 §Acceptance
are incorporated by reference, not duplicated.

## Part 1 — Why the suite missed the failures

### G1. Self-masking mocks: patching the subject's own logger

`tests/unit/test_worker.py:58,75,90` wrap every `enqueue_task` test in
`patch("audio_processor.jobs.worker.logger")`. The bug in Finding 1 **is a
logging call**: `worker.py` binds a stdlib logger (`logging.getLogger`) but
invokes it structlog-style (`logger.info("task_enqueued", task=..., job_id=...)`),
which raises `TypeError` on every real call — after the job is already
enqueued. The patch replaced the exact statement under test with a
`MagicMock` that accepts anything, so the test asserted the code works while
deleting the code. The `# type: ignore[call-arg]` on that line was the type
checker reporting the same bug; the suppression plus the mock closed both
detection channels.

The irony: `tests/conftest.py` already ships an autouse `setup_logging`
fixture, so real logging *works* in every test. Simply not patching would
have surfaced the `TypeError` in three existing tests.

### G2. Tautological configuration tests; the queue path never executes

`test_worker.py:104-113` asserts `WorkerSettings.job_timeout == 600` — a
value copied from `settings.job_timeout_seconds`, compared against itself.
Every worker test calls hooks or `enqueue_task` with an `AsyncMock` Redis; no
test anywhere runs an ARQ worker, so nothing verifies that an enqueued job is
*picked up, executed, and lands in a terminal state*. That unexecuted seam is
where Finding 1 lived, and it is also why Finding 3's headline consequence —
`job_timeout` is configured but physically unenforceable while a coroutine is
blocked in sync code — was invisible: the timeout was asserted as a number,
never observed as a behavior. `tests/unit/_fake_redis.py` models only the
hash commands the job store uses; it cannot back ARQ (sorted sets, blocking
pops), so the queue path needs the integration tier (Part 2).

### G3. Deployment descriptors are outside the test boundary

`docker-compose.yml` and `docker-compose.prod.yml` are the *actual shipped
configuration* — and no test reads them. Finding 2 is three consistency
violations between those files and `config.py` defaults (enqueue disabled by
default, memory store with `replicas: 2`, unshared `audio_temp_dir`), all
statically checkable in milliseconds, none checked. `tests/integration/`
contains only `__init__.py`; the `integration` and `smoke` markers registered
in `conftest.py` have zero tests behind them.

### G4. No invariant assertions: leaks and loop stalls are unobserved

Tests assert return values, never *system invariants*. Nothing asserts "the
temp directory is empty after the job finishes" — so Finding 4 (input file
leaked on every successful job, converted file leaked on every failure) was
undetectable by construction. Nothing asserts "the event loop stayed
responsive while work was in flight" — so Finding 3's health-check starvation
was likewise unobservable. Invariants must be fixtures that *fail teardown*,
not assertions a test author has to remember.

## Part 2 — Test architecture

Three tiers, using the markers `conftest.py` already registers:

| Tier | Marker | Infra | Runs |
|---|---|---|---|
| Unit | `unit` | none; external I/O mocked at the `services/` boundary (existing convention) | every push (existing CI job) |
| Integration | `integration` | real Redis (CI service container), real ARQ worker in burst mode, real ffmpeg on a checked-in <5 s fixture; Deepgram mocked at the client boundary | every push, separate CI job |
| Deployment smoke | `smoke` | `docker compose up` of the real compose files | on changes to `docker-compose*`, `Dockerfile*`, `config.py`; plus nightly |

New shared fixtures (in `tests/conftest.py` / `tests/integration/conftest.py`):

- **`temp_audio_dir` (autouse in integration tier)** — points
  `settings.audio_temp_dir` at `tmp_path` and, on teardown, **fails the test
  if any file remains** after the job under test reached a terminal state.
  This is the G4 leak invariant as infrastructure: every integration test
  checks it for free.
- **`arq_burst_worker`** — builds `arq.worker.Worker` from the real
  `WorkerSettings.functions` against the test Redis and runs it with
  `burst=True`, so "enqueue → execute → terminal state" is one awaited call.
- **`loop_watchdog`** — background task ticking every 25 ms and recording the
  maximum inter-tick gap; teardown fails if the gap exceeded 100 ms
  (ADR-003 invariant I-1 as a fixture).
- **`tiny_wav`** — 1-second silent WAV generated once per session with ffmpeg
  into `tmp_path` (no binary blob in git; skips cleanly if ffmpeg is absent,
  which only the integration tier requires).

## Part 3 — Test specifications

Each entry names the finding it retro-catches and why it fails against
today's code — the proof it would have caught the bug.

**T-1 · Enqueue logs through real logging — F1 · unit.**
Call `enqueue_task` with a mocked Redis (that part is fine) and **no logger
patch**; assert the returned job id and, via `caplog`, that a `task_enqueued`
record was emitted. Fails today with `TypeError: Logger._log() got an
unexpected keyword argument 'task'`. Companion sweep: remove the logger
patches from the three existing enqueue tests; they become regression tests
for the same class. Broader guard: a unit test that imports every module
under `audio_processor` and asserts each module-level `logger` is a structlog
`BoundLogger` (i.e. produced by `utils.logging.get_logger`) — kills the
stdlib/structlog mixup everywhere at once.

**T-2 · Queue path executes end-to-end — F1, F3 · integration.**
Store a `QUEUED` record via `RedisJobStore`, `enqueue_task(...,
"process_audio_job", job_id, record)`, run `arq_burst_worker`, then assert
the record is `COMPLETED` (Deepgram client mocked; ffmpeg real, `tiny_wav`
input). This single test executes the seam where Finding 1 lived: real ARQ
serialization, real task dispatch, real logging, real store writes. Fails
today on the F1 `TypeError` before the worker even starts.

**T-3 · Compose files are consistent with the config model — F2 · unit.**
Parse both compose files with `yaml.safe_load` (dev + prod overlay merge) and,
for each service running app code, build `Settings(**environment)`; assert:
(a) if the service topology includes a worker, the API's settings have
`enqueue_enabled=True` and `job_store_backend="redis"` — else the worker is
decorative; (b) API and worker resolve the **same** `audio_temp_dir` and both
mount a shared volume at that path (ADR-004 invariant L-5); (c) any service
with `replicas > 1` has `job_store_backend="redis"` — process-local state
with two replicas is split-brain by construction; (d) the prod overlay sets
`AUTH_REQUIRED=true` (review Finding 8, same class: shipped-config drift).
All four assertions fail against today's compose files, which is Finding 2
verbatim. This is milliseconds-cheap and belongs in the unit job: deployment
descriptors are test inputs from now on.

**T-4 · Deployment smoke: one job through the shipped stack — F2 · smoke.**
`docker compose up` the real files (with a `.env.test` supplying dummy
secrets and a mocked-Deepgram flag), wait for `/health`, POST `tiny_wav` to
`/api/v1/process`, poll `/status/{id}` until `COMPLETED` (bounded), fetch
`/results/{id}`, assert `/health` latency stayed < 1 s throughout, and assert
the shared temp volume is empty afterward. This is the only test that
validates image + compose + env + volume wiring as a unit; it catches the
entire Finding-2 class including mistakes T-3's static model cannot see
(missing volume mounts, wrong service names, broken images). Today it cannot
pass — which is the review's point — so it lands together with the Finding-2
compose fix and gates regressions thereafter.

**T-5 · Loop responsiveness under load — F3 · integration.**
Two probes: (a) API — start a `process_audio` upload whose validation ffprobe
is slowed to ~2 s (stub executable on `PATH`), and concurrently assert
`/health` answers in < 100 ms (ADR-003 acceptance test 1); (b) worker — run
T-2's job with `loop_watchdog` active; the fixture fails on any >100 ms
stall. Both fail against today's inline `subprocess.run` calls and pass once
ADR-003 §1 lands.

**T-6 · Timeout is enforced, not configured — F3 · integration.**
Set a small `job_timeout_seconds`, make the conversion stage block past it
(stub ffmpeg that sleeps), run the burst worker: assert the job reaches
`FAILED` with the deadline error within budget + grace, and was not
re-queued (ADR-003 acceptance test 4, ADR-004 acceptance test 3). Fails
today: the blocked coroutine never receives ARQ's cancellation, the "timed
out" job runs to whatever end ffmpeg finds, and the record strands
non-terminal. This test is the difference between asserting
`job_timeout == 600` (G2) and asserting a timeout *happens*.

**T-7 · No file survives its job — F4 · integration.**
Explicit success-path and failure-path runs of T-2's pipeline asserting the
input file and the converted file are both gone at terminal state (ADR-004
acceptance test 6) — plus the `temp_audio_dir` autouse fixture enforcing the
same invariant on every other integration test as a side effect. Fails today
on the success path: the input file is never deleted (the "worker takes
ownership" comment is aspirational), and on the failure path the converted
file survives.

Coverage note: T-1/T-3 are cheap and run with the existing unit job; T-2,
T-5–T-7 share the Redis service container and the burst-worker fixture; T-4
is the only docker-in-CI cost and is path-gated + nightly.

## Part 4 — Binding suite rules (mirrored into `tests/CLAUDE.md`)

1. **Never patch a logger belonging to the module under test.** Logging
   calls are executable statements; a patched logger deletes them from the
   test (Finding 1's mask). Assert on `caplog` /
   `structlog.testing.capture_logs`. Patching a *collaborator's* logger to
   silence noise is equally disallowed — use log levels.
2. **A configuration value may only be tested through the behavior it
   controls.** `assert WorkerSettings.job_timeout == 600` is comparing a
   variable to itself; the honest test is T-6.
3. **Deployment descriptors are test inputs.** Any file that configures a
   shipped process (`docker-compose*.yml`, `Dockerfile*`, `.env.example`)
   is covered by T-3-style consistency tests; editing one without a test
   run is the Finding-2 failure mode.
4. **Resource invariants are fixtures, not assertions.** Leak checks
   (`temp_audio_dir`) and loop-stall checks (`loop_watchdog`) fail in
   teardown so no test author has to remember them.
5. **A `# type: ignore` / `# pyright: ignore` on a line that then gets
   mocked in tests is a red flag, not a fix.** Finding 1 was visible to the
   type checker and suppressed; the mock hid it at runtime. Suppressions on
   call-argument errors require a comment proving the call is exercised
   un-mocked somewhere.

## Part 5 — CI wiring

- **unit job (existing)**: add T-1, T-3; no new infra.
- **integration job (new)**: `services: redis:7-alpine`; installs ffmpeg;
  runs `-m integration` (T-2, T-5–T-7). Target < 2 min.
- **smoke job (new)**: `docker compose -f docker-compose.yml -f
  docker-compose.prod.yml up` with `.env.test`; runs `-m smoke` (T-4);
  triggered by paths `docker-compose*`, `Dockerfile*`,
  `src/audio_processor/core/config.py`, plus `schedule: nightly`.
- Coverage gate unchanged; integration tier reports under the existing
  `codecov` flags.

## Part 6 — Implementation tasks (ordered)

1. Add rules 1–5 to `tests/CLAUDE.md` (done alongside this plan).
2. T-1 + logger-patch removal sweep + module-logger type test. *Lands with
   the Finding-1 one-line fix (`get_logger(__name__)` in `worker.py`); the
   test must be observed red first.*
3. T-3 compose-consistency tests. *Lands with the Finding-2 compose fix;
   observed red first.*
4. Integration conftest: `temp_audio_dir`, `arq_burst_worker`,
   `loop_watchdog`, `tiny_wav`; CI integration job with Redis service.
5. T-2 queue-path test (first consumer of the fixtures).
6. T-7 file-lifecycle tests — red until ADR-004 task 3 (worker `finally`
   cleanup) lands; implement together.
7. T-5/T-6 — red until ADR-003 tasks land; implement together (they are
   ADR-003 acceptance tests 1 and 4 made concrete).
8. T-4 smoke test + `.env.test` + smoke CI job — lands last, after the
   Finding-2 fix makes the stack processable.

The "observed red first" discipline is the point of the plan: each test is
committed failing against the pre-fix code (locally, or in the fix PR's first
commit), proving it detects the defect it is assigned to.
