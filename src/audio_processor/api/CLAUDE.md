# API Layer: Folder-Level Guidelines

> Scope: `src/audio_processor/api/` only. Root `CLAUDE.md` rules apply everywhere else.

## Route conventions

- Every route must declare `summary`, `description`, `response_model`, `status_code`, and `responses` in the decorator.
- Use `status.HTTP_*` constants from `fastapi`, never bare integers.
- All request bodies must be typed Pydantic models; no `dict` or `Any` parameters.

## Exception-to-HTTP mapping

Use the centralized exception hierarchy from `audio_processor.core.exceptions`:

| Exception | HTTP status |
|---|---|
| `ValidationError` | 422 Unprocessable Entity |
| `ResourceNotFoundError` | 404 Not Found |
| `AuthenticationError` | 401 Unauthorized |
| `AuthorizationError` | 403 Forbidden |
| `ExternalServiceError` | 502 Bad Gateway |
| `BusinessLogicError` | 409 Conflict |

The global exception handler in `__init__.py` maps these automatically. Do not return raw dicts for errors; raise the appropriate exception.

## Async conventions

- Route handlers must be `async def`; do not block the event loop with synchronous I/O.
- Background tasks go via ARQ (`enqueue_job`), not `BackgroundTasks`, for durability.

## Adding a new endpoint

1. Add the route to `routes.py` with full decorator metadata.
2. Add a Pydantic request/response model to `models.py` (or create it if absent).
3. Register the router in `__init__.py` if adding a new router file.
4. Update `docs/api-reference.md` nav and mkdocstrings directives.
