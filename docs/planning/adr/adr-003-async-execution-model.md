---
title: "ADR-003: Async Execution Model — Blocking Work, Timeouts, and Cancellation"
schema_type: planning
status: published
owner: core-maintainer
purpose: "Define the binding contract for where blocking work runs, how timeouts are enforced, and what cancellation guarantees, so the event loop is never blocked in the API or the worker."
tags:
  - adr
  - architecture
  - concurrency
component: Development-Tools
source: "Systems design review 2026-07-02"
---

> **Status**: Accepted
> **Date**: 2026-07-02
> **Supersedes**: None
> **Relates to**: ADR-001 (Deepgram-centric pipeline), systems design review findings 3, 5, 6

## Context

Both processes in this system run a single asyncio event loop, and both currently
execute long blocking calls directly on it:

- The API route `process_audio` calls `AudioConverter.validate_file` inline, which
  runs `subprocess.run(ffprobe, timeout=30)`. One slow upload stalls every
  concurrent request, including `/health` — the container health check
  (10 s timeout, 3 retries) can then kill a healthy container.
- The ARQ task `process_audio_job` runs ffmpeg (`subprocess.run`, up to 600 s),
  librosa/numpy quality assessment, and the synchronous Deepgram HTTP call
  directly in the async task. `max_jobs = 10` is therefore fiction: jobs
  serialize behind each other, the worker's health-check heartbeat starves, and
  ARQ's `job_timeout` — enforced by *cancelling the task* — cannot fire, because
  a coroutine blocked inside a sync call never reaches an `await` where
  `CancelledError` can be delivered.

"Wrap it in a thread" alone is not a fix. `anyio.to_thread.run_sync` unblocks
the loop, but threads cannot be cancelled: with the default
`abandon_on_cancel=False`, ARQ's timeout cancellation *waits for the thread to
finish* (timeout still unenforced); with `abandon_on_cancel=True`, the
coroutine returns but the thread — and its ffmpeg child — keeps running
unbounded. Timeout enforcement must therefore live **inside** each blocking
primitive, with cancellation reduced to "stop waiting" plus a bounded
self-termination guarantee.

Pinned versions this contract is written against: `anyio 4.13`
(`abandon_on_cancel` parameter), `arq 0.28` (timeout via task cancellation).

## Decision

Services stay synchronous (per `services/CLAUDE.md`). Async callers dispatch
them to threads. Every blocking primitive carries its own hard deadline, so an
abandoned stage always self-terminates. The orchestrator alone touches shared
state.

### 1. Execution placement table (binding)

| Call site | Work | Runs on | Timeout enforced by | Behavior when the awaiting task is cancelled |
|---|---|---|---|---|
| API `process_audio` | `validate_file` (ffprobe) | thread: `anyio.to_thread.run_sync(..., abandon_on_cancel=True, limiter=API_PROBE_LIMITER)` | existing 30 s `subprocess.run` timeout (kills the child) | thread abandoned; ffprobe self-terminates ≤ 30 s |
| API `process_audio` | `mkstemp`, upload streaming | thread / native async (already correct) | n/a | unchanged |
| Worker stage: convert/extract | ffmpeg via `AudioConverter` | thread: `anyio.to_thread.run_sync(..., abandon_on_cancel=True, limiter=WORKER_STAGE_LIMITER)` | `deadline.remaining()` passed as the `subprocess.run` timeout (`subprocess.run` kills the child on expiry) | abandoned; ffmpeg killed by its own timeout ≤ remaining budget |
| Worker stage: quality assessment | librosa/numpy over decoded audio | thread (same dispatch) | not interruptible — bounded only by input size; see §4 duration cap | abandoned; completes on local data, result discarded |
| Worker stage: transcription | Deepgram sync SDK | thread (same dispatch) | `min(settings.deepgram_timeout_seconds, deadline.remaining())` passed to the SDK's HTTP client per request (closes design-review Finding 5 — the setting is currently never applied) | abandoned; HTTP timeout bounds the thread |
| Worker stage: artifact generation | string building over words/utterances | thread (same dispatch) | bounded by input size (duration cap) | abandoned; result discarded |
| Worker orchestrator | job-store updates, unlink, progress | event loop (async), as today | n/a | cleanup runs in a shielded scope (§5) |

**Loop-blocking rule (invariant I-1):** no synchronous section on the event
loop may exceed 100 ms. Concretely forbidden on the loop: any `subprocess.*`
call, any librosa/soundfile/numpy operation over audio arrays, any Deepgram SDK
call, any file read/write larger than 1 MiB.

### 2. Deadline budget contract

A single per-job wall-clock budget replaces the current pattern of reusing
`settings.job_timeout_seconds` as every individual subprocess timeout (which
lets one stage consume the entire job budget and the job still run to 3× it).

```python
class StageDeadline:
    """Monotonic per-job budget. Created once at job start."""
    def __init__(self, total_seconds: float) -> None:
        self._deadline = time.monotonic() + total_seconds

    def remaining(self) -> float:
        """Seconds left. Raises JobTimeoutError (AudioProcessorError subclass)
        when the budget is exhausted, so a stage is never started with <= 0."""
```

- Created in `process_audio_job` with `settings.job_timeout_seconds`.
- Every stage dispatch passes `deadline.remaining()` into the primitive that
  enforces it (ffmpeg subprocess timeout; Deepgram HTTP timeout).
- `AudioConverter.extract_audio` / `convert_for_asr` gain a required
  `timeout_seconds: float` parameter (replacing the internal read of
  `settings.job_timeout_seconds`). `probe` keeps its fixed 30 s.
- `DeepgramTranscriptionClient.transcribe` gains `timeout_seconds: float`,
  wired to the SDK's per-request HTTP timeout — not merely stored on `self`.
- ARQ `WorkerSettings.job_timeout` becomes
  `settings.job_timeout_seconds + JOB_TIMEOUT_GRACE` with
  `JOB_TIMEOUT_GRACE = 60`. It is a **backstop only** (catches a stage that
  ignores its budget); the `StageDeadline` is the primary enforcement. A job
  must terminate — success or `FAILED` — within budget + grace (invariant I-2).

### 3. Concurrency bounds

- `WORKER_STAGE_LIMITER = anyio.CapacityLimiter(settings.worker_max_jobs)`
  (module-level in `jobs/audio_tasks.py`): at most one stage thread per
  running job, so thread count can never exceed job concurrency.
- `API_PROBE_LIMITER = anyio.CapacityLimiter(8)` (module-level in
  `api/routes.py`): bounds concurrent ffprobe processes regardless of request
  volume; requests beyond it queue on the limiter, not on the loop.
- New setting `worker_max_jobs: int = 2` (ge=1, le=32);
  `WorkerSettings.max_jobs` reads it instead of the hardcoded 10.

### 4. Memory sizing (why `worker_max_jobs = 2` and the duration cap)

Converted audio is 16 kHz mono s16le WAV: **32 000 bytes/s ≈ 115 MB per hour**.
With the current whole-file buffering, per-job peak memory is dominated by:

- quality assessment: `soundfile.read` decodes to float64 → **4 × WAV bytes**
- Deepgram upload: `file.read()` into memory → 2 × WAV bytes

Stages run sequentially within a job, so **peak/job ≈ 4 × WAV bytes**. The
binding constraint for the worker container:

```
worker_max_jobs × 4 × (115 MB × audio_max_duration_hours) + 300 MB baseline ≤ container memory limit
```

The current defaults are infeasible: 4 h audio → 461 MB WAV → ~1.8 GB peak per
job, against a 512 MB limit in `docker-compose.prod.yml` — an OOM kill even at
concurrency 1. Interim posture (until streaming per design-review Finding 6
removes the 4× and 2× factors):

- `audio_max_duration_hours` default: **4.0 → 1.0**
- `worker_max_jobs`: **2**
- worker container memory limit: **2 GiB** (2 × 4 × 115 MB + 300 MB ≈ 1.2 GiB,
  ~40 % headroom)

Any change to duration limit, concurrency, or container memory must re-satisfy
the inequality above (invariant I-3). Both the quality-assessment decode and
the Deepgram read must move to streaming/chunked forms before the 4× factor may
be dropped from the formula.

### 5. Cancellation and cleanup contract

- **Orchestrator-only state (invariant I-4):** stage functions dispatched to
  threads are pure with respect to shared state — they take paths/data in and
  return values; they never write the job store. Only `process_audio_job`
  (on the loop) updates the store. An abandoned thread therefore cannot race a
  status write.
- **Shielded cleanup:** `process_audio_job` wraps the pipeline so that on any
  exit — including `CancelledError` from ARQ timeout or worker shutdown — a
  cleanup block runs inside `with anyio.CancelScope(shield=True):` and (a)
  writes the terminal store status, (b) unlinks this job's temp files
  (`os.unlink` on the loop is acceptable: < 100 ms). Cleanup must be
  idempotent. *Which* files and statuses are written in each terminal state is
  the job-lifecycle ADR's decision (design-review item 2); this ADR fixes the
  mechanism.
- **Orphan bound:** an abandoned stage may still create its output temp file
  after abandonment (ffmpeg finishing within its own timeout). Bound this with
  a sweep in the worker `startup` hook: delete files in
  `settings.audio_temp_dir` older than
  `job_timeout_seconds + JOB_TIMEOUT_GRACE`. Orphan lifetime is therefore
  ≤ one budget+grace window (invariant I-5).

### 6. Caller-side rule (added to `services/CLAUDE.md`)

Services stay sync; the missing rule is for their callers:

> Any `async def` (route handler, ARQ task, lifespan hook) calling a service
> method that shells out, does CPU-bound audio work, or performs blocking I/O
> MUST dispatch it via `anyio.to_thread.run_sync(..., abandon_on_cancel=True,
> limiter=<the module's CapacityLimiter>)` and MUST pass an explicit timeout
> that the service enforces internally. Calling these methods bare in async
> code is a review-blocking defect.

## Acceptance criteria

Implementation is complete only when all of these tests exist and pass:

1. **API responsiveness (I-1):** with `AudioConverter.validate_file`
   monkeypatched to `time.sleep(2)`, a concurrent `GET /health` completes in
   < 500 ms while an upload is in flight.
2. **Worker parallelism:** two jobs whose conversion stage is stubbed to sleep
   1 s in-thread finish in < 1.8 s combined (parallel), not ≥ 2 s (serial).
3. **Deadline propagation:** with total budget `T` and a first stage stubbed to
   consume `t`, the mocked Deepgram transport receives a timeout ≤ `T − t`;
   `subprocess.run` in the converter receives the computed remaining budget,
   not `settings.job_timeout_seconds`.
4. **Timeout termination (I-2):** a job whose stage sleeps past the budget ends
   `FAILED` within budget + grace, the shielded cleanup ran (temp files gone,
   terminal status written), and no child process survives.
5. **Thread bound (§3):** with `worker_max_jobs = N` and > N queued jobs, at
   most N stage threads run concurrently (assert via the limiter's
   `statistics()`).
6. **Loop watchdog:** the pipeline integration test runs with asyncio debug
   mode (`loop.slow_callback_duration = 0.2`) and fails on any "Executing …
   took" warning captured from the `asyncio` logger.
7. **Orphan sweep (I-5):** a pre-seeded stale file in the temp dir older than
   budget + grace is removed by the worker `startup` hook; a fresh file is not.

## Implementation tasks (ordered, mechanical)

1. Add `JobTimeoutError` to `core/exceptions.py`; add `StageDeadline` (new
   `jobs/deadline.py` or in `audio_tasks.py`).
2. Add `worker_max_jobs` setting; change `audio_max_duration_hours` default to
   1.0; set `WorkerSettings.max_jobs = settings.worker_max_jobs` and
   `job_timeout = settings.job_timeout_seconds + 60`.
3. Add `timeout_seconds` parameters to `extract_audio` / `convert_for_asr`
   (drop their internal `settings.job_timeout_seconds` read) and to
   `DeepgramTranscriptionClient.transcribe`, wired to the SDK HTTP timeout.
4. In `api/routes.py`: add `API_PROBE_LIMITER`; dispatch `validate_file` via
   `to_thread.run_sync(abandon_on_cancel=True, limiter=...)`.
5. In `jobs/audio_tasks.py`: add `WORKER_STAGE_LIMITER`; dispatch the four
   stages per §1 with `deadline.remaining()`; restructure the task body around
   the shielded cleanup block (§5).
6. Add the temp-dir sweep to the worker `startup` hook.
7. Add the caller-side rule to `services/CLAUDE.md` (§6).
8. Add acceptance tests 1–7; raise the worker memory limit to 2 GiB in
   `docker-compose.prod.yml` per §4.

## Alternatives considered

- **Rewrite services as async (`asyncio.create_subprocess_exec`)**: cancellable
  subprocesses without abandonment, but a much larger diff, breaks the
  established sync-services convention, and offers no better wall-clock bound
  than `subprocess.run`'s kill-on-timeout. Rejected for scope; the placement
  table localizes a future migration to the dispatch sites.
- **`ProcessPoolExecutor` for CPU stages**: still not cancellable, adds
  pickling constraints on models and duplicates audio buffers across
  processes, worsening §4. Rejected.
- **Separate synchronous worker framework (Celery/RQ prefork)**: real
  SIGKILL-based timeouts, but an infrastructure change that abandons ARQ and
  the shared job-store design. Rejected at current scale; revisit if job
  volume outgrows a single async worker with `worker_max_jobs` threads.

## Consequences

- The event loop in both processes stays responsive under any input; `/health`
  and the ARQ heartbeat reflect real liveness.
- `job_timeout` becomes a real guarantee (budget + grace) instead of
  aspirational config.
- Cancellation never corrupts state: threads are abandoned but side-effect-free
  (I-4), self-terminate within their own deadlines, and orphaned files are
  swept (I-5).
- Throughput is honestly bounded by `worker_max_jobs` and the memory formula —
  raising it is now a sizing calculation, not a hope.
- Cost: abandoned stages can waste up to one stage-timeout of CPU after a
  cancel; accepted as bounded and rare.
