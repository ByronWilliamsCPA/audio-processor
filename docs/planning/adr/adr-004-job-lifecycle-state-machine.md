---
title: "ADR-004: Job Lifecycle State Machine — Transitions, Retries, Idempotency, and File Ownership"
schema_type: planning
status: published
owner: core-maintainer
purpose: "Define the canonical job state machine, who may write which transition, what actually retries and why, how redelivery stays idempotent, and which process owns each temp file at every point in a job's life."
tags:
  - adr
  - architecture
  - reliability
component: Development-Tools
source: "Systems design review 2026-07-02"
---

> **Status**: Accepted
> **Date**: 2026-07-02
> **Supersedes**: None
> **Relates to**: ADR-003 (async execution model — this ADR consumes its
> `StageDeadline`/`JobTimeoutError` and the deadline+grace window), systems
> design review findings 1, 2, 4, 8

## Context

Job state currently lives in a shared store (`core/job_store.py`) written by
three uncoordinated writers — the API (`QUEUED`, enqueue-failure `FAILED`), the
worker orchestrator (`PREPROCESSING` → … → `COMPLETED`/`FAILED`), and Redis TTL
expiry (silent deletion). Nothing validates transitions: `store.update` merges
blindly, so a late writer can move a job *out of* a terminal state. The
lifecycle has real holes today:

- **Stranded non-terminal records.** ARQ enforces `job_timeout` by cancelling
  the task; `asyncio.CancelledError` is a `BaseException`, so the
  `except Exception` handlers in `process_audio_job` never run on timeout and
  no `FAILED` is written. With `retry_jobs = True`, ARQ re-runs the job up to
  `max_tries`, then gives up **without executing the task again** — the record
  is left in `PREPROCESSING`/`TRANSCRIBING` forever (until TTL deletion turns
  it into a 404). Clients polling `/status` see a job that is "processing"
  and never finishes.
- **Retry semantics are misdescribed.** `worker.py` promises "job retries with
  exponential backoff" and `job_max_retries` is documented as "maximum retry
  attempts for failed jobs". In arq 0.28, `retry_jobs=True` re-queues a job
  only on **cancellation** (timeout, worker shutdown) or an explicit
  `arq.worker.Retry` raise. Ordinary exceptions — every `ValidationError`,
  `TranscriptionError`, unexpected error in the pipeline — fail permanently on
  the first attempt. The configured retry budget currently applies *only* to
  the timeout path, which is the one path where re-running is least useful.
- **No enqueue dedup, no addressability.** `enqueue_task` calls
  `redis.enqueue_job(task_name, ...)` without `_job_id=`, so ARQ assigns its
  own random id. ARQ's built-in same-id dedup is unused, and the application
  `job_id` cannot be used to look up, abort, or reason about the ARQ job.
- **File ownership is asserted, not implemented.** `routes.py` deletes the
  uploaded temp file only on failure, with a comment claiming "the worker
  takes ownership of the temp file and deletes it when done" — but the worker
  never deletes `file_path`. It unlinks only `converted_path`, and only on the
  happy path. Every successful job leaks its input file; every failed or
  timed-out job leaks both files. ADR-003's startup sweep bounds the damage
  but is a backstop, not an ownership policy.
- **Redelivery is not idempotent.** A worker that dies after the Deepgram call
  but before the `COMPLETED` write causes a full re-run on redelivery —
  including a second billed Deepgram request — and a worker that dies *after*
  the `COMPLETED` write causes a re-run that drags a finished job back to
  `PREPROCESSING`.

This ADR fixes the lifecycle at the contract level. ADR-003 governs *how*
stages execute; this ADR governs *what a job is allowed to be* at any moment,
observed from the store.

## Decision

One state machine, guarded at the store. Retries are reserved for redelivery
after worker death and explicitly-declared transient external failures —
never for validation or deadline failures. Terminal states are absorbing.
Every temp file has exactly one owner at any instant, and the owner that
writes a terminal state deletes the files.

### 1. Canonical state machine (binding)

States are the existing `JobStatus` values. `COMPLETED` and `FAILED` are
**terminal (absorbing)**: no writer may transition out of them, ever.

| Transition | Writer | Trigger |
|---|---|---|
| ∅ → `QUEUED` | API | `store.create` on accepted upload |
| `QUEUED` → `PREPROCESSING` | worker | task entry, attempt 1 |
| any non-terminal → `PREPROCESSING` | worker | task entry, attempt > 1 (redelivery re-runs from the top) |
| `PREPROCESSING` → `TRANSCRIBING` | worker | conversion + quality stages done |
| `TRANSCRIBING` → `POSTPROCESSING` | worker | Deepgram call returned |
| `POSTPROCESSING` → `COMPLETED` | worker | result + artifacts persisted |
| any non-terminal → `FAILED` | worker | pipeline exception or `JobTimeoutError` |
| `QUEUED` → `FAILED` | API | enqueue failure (existing path) |
| any non-terminal → `FAILED` | API (lazy reaper, §4) | record stale beyond deadline + grace |
| any → *(deleted)* | Redis TTL | `job_result_ttl_seconds` since last write — the implicit `EXPIRED` state; observed as 404 |

`CANCELLED` is a **reserved** state name for a future user-facing abort
endpoint (arq supports `Job.abort()` once `_job_id` is wired, §3). It is not
added now; nothing else may reuse the name.

**Enforcement — guarded transitions (invariant L-1).** Status may only change
via a new store method:

```python
async def transition(
    self, job_id: str, *, from_statuses: frozenset[str], to_status: str,
    **fields: object,
) -> bool:
    """Atomically set status (and merge fields) iff the current status is in
    from_statuses. Returns False — writing nothing — otherwise."""
```

- `RedisJobStore.transition` MUST be atomic: a short Lua script (`EVAL`) that
  `HGET`s `status`, checks membership, and applies `HSET` + `EXPIRE` in one
  server-side step. A `WATCH`-based CAS is acceptable but the Lua form is
  preferred (no retry loop).
- `InMemoryJobStore.transition` is a plain check-then-merge (single process,
  single loop — already atomic between awaits).
- Terminal absorption follows for free: no transition lists `COMPLETED` or
  `FAILED` in `from_statuses`. Progress-only updates (`percent_complete`,
  stage messages, no status change) keep using `update`, but MUST NOT include
  a `status` field; the orchestrator is the only status writer inside the
  worker (ADR-003 invariant I-4 already requires this).
- A `transition(...) == False` at task entry means the record is already
  terminal or missing: the task MUST return immediately without running any
  stage (see §3).

### 2. Retry contract (binding)

What arq 0.28 actually does, and how each failure class maps onto it:

| Failure class | Example | Mechanism | Outcome |
|---|---|---|---|
| Permanent input/domain error | `ValidationError`, unreadable file, corrupt media | ordinary raise (as today) | `FAILED` on attempt 1; no retry. Correct — re-running cannot fix the input. |
| Deadline exhausted | `JobTimeoutError` from ADR-003's `StageDeadline` | ordinary raise, caught, `FAILED` written | **No retry.** The budget is sized to the audio; a re-run repeats the same work against the same budget and re-bills Deepgram. This is why ADR-003 raises *inside* the job instead of letting ARQ's cancellation fire: it converts timeout into a handleable, terminal failure. |
| Transient external failure | Deepgram 429 / 5xx / connection reset | raise `arq.worker.Retry(defer=...)` from the orchestrator with exponential defer (`min(2 ** (attempt - 1) * 10, 300)` seconds — `attempt` from `job_try` is 1-based, so the first retry defers 10 s) | re-queued; `max_tries` caps total attempts. This is the **only** place `Retry` may be raised. |
| Worker death / shutdown | SIGTERM, OOM-kill, ARQ backstop cancellation (`job_timeout = budget + grace`, ADR-003 §2) | ARQ cancellation + `retry_jobs = True` | redelivered to a live worker; task entry re-runs from the top (§3). This — not "failed jobs" — is what `retry_jobs` is for. |

Consequences to codify:

- `retry_jobs = True` stays, **documented as worker-death redelivery**, not
  error retry. Fix the lying docs: `worker.py` module docstring ("job retries
  with exponential backoff") and the `job_max_retries` field description in
  `config.py` ("maximum retry attempts for failed jobs" → "maximum delivery
  attempts per job; consumed by worker-death redelivery and declared-transient
  external failures, never by validation or deadline failures").
- Only the orchestrator classifies errors. Services keep raising domain
  exceptions (`services/CLAUDE.md`); `_transcribe`'s caller inspects
  `ExternalServiceError` for the transient subset (HTTP status ≥ 500, 429,
  connection errors) and converts *those alone* into `Retry`. Everything else
  falls through to the existing `FAILED` handlers.
- **Attempt visibility (invariant L-2):** at task entry the worker stamps
  `attempt = ctx["job_try"]` and `max_attempts = settings.job_max_retries`
  onto the record. `/status` exposes them. A record on attempt 3 of 3 is
  diagnosable; today attempts are invisible.
- When ARQ exhausts `max_tries` on the cancellation path it never runs the
  task again, so the worker cannot write the final `FAILED` — the lazy reaper
  (§4) is the designated writer for that case.

### 3. Idempotency and dedup (binding)

- **Tie the ARQ job id to the application job id (invariant L-3):**
  `enqueue_task` MUST pass `_job_id=job_id`. Effects: a double `POST`-side
  enqueue of the same job id is refused by ARQ (`enqueue_job` returns `None` —
  the existing `RuntimeError` path already handles it); the ARQ job becomes
  addressable (`arq.jobs.Job(job_id, redis)`) for the future abort endpoint;
  operators can correlate ARQ internals with API job ids. `keep_result` makes
  a completed id un-reenqueueable until its result TTL expires — harmless
  here because job ids are fresh UUIDs per upload, and it is the correct
  guard against accidental re-submission of a finished id.
- **Terminal check at task entry (invariant L-4):** the first act of
  `process_audio_job` is
  `transition(job_id, from_statuses=NON_TERMINAL, to_status=PREPROCESSING, attempt=..., ...)`.
  If it returns `False`, log and return — the record is terminal (the
  worst-case redelivery: prior attempt finished but the ack was lost) or gone
  (TTL). This closes the "redelivery drags a `COMPLETED` job back to
  `PREPROCESSING`" hole and skips a second Deepgram bill in the
  finished-but-unacked case.
- **Stages must tolerate re-runs.** Conversion output paths become
  deterministic per job (§5 naming), created with overwrite semantics, so a
  re-run replaces a half-written file from a dead attempt instead of leaking a
  new one. Quality assessment and artifact generation are pure. The Deepgram
  call is the one non-idempotent, billed side effect; after L-4 the residual
  double-billing window is [Deepgram returns → `COMPLETED` written], a few
  store round-trips wide. **Accepted risk**, bounded by `max_tries`; not worth
  a distributed transaction. `# #CRITICAL: Payment/Financial:` tag this at the
  call site.

### 4. Stranded-record reaping (binding)

The reaper is **lazy, on read** — it needs no extra process and works even
when the worker fleet is gone (which is exactly when records strand):

- `GET /status/{id}` (and `/results`), after fetching a record that is
  **non-terminal**, computes staleness from `progress.updated_at` (fallback
  `created_at`). If older than `job_timeout_seconds + JOB_TIMEOUT_GRACE`
  (ADR-003's window — beyond it, ADR-003 invariant I-2 guarantees no live
  attempt can still be running), the handler performs
  `transition(from_statuses=NON_TERMINAL, to_status=FAILED, error="job lost: no worker progress within the deadline window")`
  and serves the result of that transition. The guard makes concurrent
  reads/worker writes race-safe: whoever wins, the record ends valid.
- `QUEUED` records are covered by the same rule. This also puts a floor under
  the `enqueue_enabled=False` misconfiguration (review Finding 2): a job that
  nothing will ever process stops lying to pollers after one deadline window.
- Records nobody polls die by TTL, as today. That is acceptable: reaping
  exists for observers, and TTL already bounds storage.
- The worker startup sweep from ADR-003 §5 handles the **files**; the lazy
  reaper handles the **records**. Neither depends on the other.

### 5. File ownership contract (binding)

Precondition (invariant L-5): the API and worker MUST resolve the same
`audio_temp_dir` — this is a real filesystem coupling and both compose files
MUST set `AUDIO_TEMP_DIR=/app/temp` explicitly (review Finding 2). The
`platformdirs` default is per-container and silently breaks handoff.

Deterministic naming, keyed to the job: input `{job_id}.input{suffix}`,
converted `{job_id}.converted.wav`, both under `audio_temp_dir`. Retries
overwrite rather than accumulate, and any sweep can map file → job record.

| File | Created by | Owner… | …until | Then deleted by |
|---|---|---|---|---|
| input temp file | API (`mkstemp` → renamed to `{job_id}.input{suffix}`) | API | successful return of `POST /process` (record stored, enqueue done or disabled) | **worker**, in a `finally` on every exit of `process_audio_job` — success, failure, `JobTimeoutError`, and the L-4 already-terminal early return |
| input temp file (failure before handoff) | API | API | any exception in the route | API `finally` (existing path, unchanged) |
| converted file | worker conversion stage | worker | task exit | same worker `finally` (today it is unlinked only on the happy path) |
| orphans (dead attempt, `abandon_on_cancel` stragglers) | either | nobody | file mtime older than deadline + grace | worker startup sweep (ADR-003 §5), which with deterministic names now also deletes files whose job record is terminal or absent |

Rules:

- The `finally` cleanup runs in the shielded scope required by ADR-003 §5, so
  cancellation cannot skip it.
- The route's misleading comment is replaced by a pointer to this table.
- Ownership transfers exactly once, at successful route return. Between
  enqueue and task start the worker owns a file it has not seen yet — that is
  fine; the sweep covers the crash window.

## Acceptance criteria

1. **Terminal absorption**: seed a `COMPLETED` record; run `process_audio_job`
   for that id; assert the task returns without invoking any stage (mock
   converter/assessor assert-not-called) and status is still `COMPLETED`.
2. **Guarded transition atomicity**: two concurrent `transition` calls on the
   same record (worker→`COMPLETED` vs reaper→`FAILED`) — exactly one wins;
   the record never holds a mixed state. Redis-backed test via the Lua path.
3. **No stranded timeout**: force `JobTimeoutError` in a stage; assert the
   record ends `FAILED` with the deadline error, and ARQ did **not** re-queue.
4. **Transient retry**: make the transcription stage raise a transient
   `ExternalServiceError`; assert `Retry` is raised with the expected defer
   and the record is non-terminal with `attempt` stamped.
5. **Lazy reaper**: seed a non-terminal record with `updated_at` older than
   deadline + grace; `GET /status` returns `FAILED` with the "job lost" error
   and the store reflects it; a second `GET` is a pure read.
6. **File lifecycle**: run a job to success and to failure; assert both the
   input and converted files are gone in both cases; assert the API failure
   path still cleans its own upload.
7. **Enqueue dedup**: enqueue the same job id twice; the second attempt
   surfaces the existing `RuntimeError` path, and exactly one ARQ job exists.

## Implementation tasks (ordered)

1. Add `transition(...)` to `JobStore`/`InMemoryJobStore`/`RedisJobStore`
   (Lua script for Redis), plus `NON_TERMINAL`/`TERMINAL` frozensets exported
   next to `JobStatus`.
2. Wire `_job_id=job_id` through `enqueue_task` (worker.py).
3. Rework `process_audio_job`: L-4 terminal check + attempt stamping at entry;
   all status writes via `transition`; transient-`ExternalServiceError` →
   `Retry(defer=...)` classification; `finally` deleting input and converted
   files (shielded per ADR-003).
4. Rename API temp files to the deterministic `{job_id}.input{suffix}` scheme;
   replace the ownership comment with a reference to ADR-004 §5.
5. Add the lazy reaper to `/status` and `/results` handlers.
6. Extend the ADR-003 startup sweep to also delete files whose job record is
   terminal or absent (deterministic names make the lookup trivial).
7. Fix the misdocumented retry semantics (`worker.py` docstring, `config.py`
   `job_max_retries` description).
8. Set `AUDIO_TEMP_DIR=/app/temp` in both compose files (app and worker
   services) — may land with the review Finding 2 fix if that ships first.
9. Tests for acceptance criteria 1–7.

## Alternatives considered

- **A dedicated `RETRYING` state.** Rejected: attempt metadata (`attempt`/
  `max_attempts` fields) carries the same information without doubling the
  transition table; pollers care whether the job is done, not which delivery
  is running.
- **Periodic reaper via ARQ `cron_jobs`.** Rejected as the primary mechanism:
  it runs only while a worker is alive — precisely the condition under which
  records strand least — and requires `SCAN`ning the keyspace. Lazy
  reap-on-read covers every observed job with zero extra infrastructure; TTL
  covers the unobserved. A cron sweep can be added later without contract
  changes.
- **Exactly-once transcription via a Deepgram-call ledger.** Rejected: the
  residual double-bill window after L-4 is a few milliseconds wide and only
  reachable through worker death at that instant; a ledger adds a second
  consistency domain to protect against a bounded, rare, non-corrupting cost.
- **Dropping `retry_jobs` entirely.** Rejected: it is the only redelivery
  mechanism for worker death; without it an OOM-killed worker strands every
  in-flight job with no recovery path but the reaper.
