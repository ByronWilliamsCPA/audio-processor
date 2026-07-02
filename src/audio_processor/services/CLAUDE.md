# Services Layer: Folder-Level Guidelines

> Scope: `src/audio_processor/services/` only. Root `CLAUDE.md` rules apply everywhere else.

## Service initialization pattern

Services are instantiated once and injected via FastAPI dependency injection or direct import.
Constructor parameters come from `settings` (Pydantic Settings); do not accept raw env-var strings.

```python
class MyService:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.my_service_api_key.get_secret_value()
```

## Method conventions

- Synchronous CPU-bound methods: plain `def`.
- I/O-bound methods that call external APIs or read files: `def` wrapping a sync SDK (current pattern) or `async def` if the SDK supports it.
- Raise `ExternalServiceError` (from `core.exceptions`) on network failures; never let SDK exceptions propagate raw to the caller.

## Caller-side rule for async contexts (binding — see ADR-003)

Any `async def` (route handler, ARQ task, lifespan hook) calling a service method
that shells out, does CPU-bound audio work, or performs blocking I/O MUST dispatch
it via `anyio.to_thread.run_sync(..., abandon_on_cancel=True, limiter=<the module's
CapacityLimiter>)` and MUST pass an explicit timeout that the service enforces
internally. Calling these methods bare in async code is a review-blocking defect.
Full contract (placement table, deadline budget, cancellation guarantees):
`docs/planning/adr/adr-003-async-execution-model.md`.

## RAD tagging (mandatory for this layer)

All methods that call external APIs or read files must carry `#CRITICAL: ExternalResources` tags.
See `deepgram_client.py` for the established pattern.

## Adding a new service

1. Create `my_service.py` in this directory.
2. Add `#CRITICAL` RAD tags at every external call site.
3. Add the service to `src/audio_processor/services/__init__.py` exports.
4. Write unit tests under `tests/unit/services/` with all external calls mocked.
