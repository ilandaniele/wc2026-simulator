"""Centralised error helpers for the WC2026 API.

All error responses follow the envelope: {error: {code, detail}}.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from slowapi.errors import RateLimitExceeded


def unknown_team_response(team: str) -> JSONResponse:
    """Return a 400 JSON response for an unrecognised team name."""
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "UNKNOWN_TEAM",
                "detail": f"Team '{team}' is not in the model. Check spelling.",
            }
        },
    )


def _format_validation_errors(errors: list[dict]) -> str:  # type: ignore[type-arg]
    """Format a list of Pydantic error dicts into a human-readable string."""
    field_msgs = []
    for e in errors:
        loc_parts = e.get("loc", ())
        # Skip the top-level "body" prefix for cleaner messages
        loc_parts = [p for p in loc_parts if p != "body"]
        loc = " → ".join(str(x) for x in loc_parts) if loc_parts else "body"
        field_msgs.append(f"{loc}: {e['msg']}")
    return "; ".join(field_msgs) if field_msgs else "Validation failed"


def validation_error_response(exc: ValidationError) -> JSONResponse:
    """Return a 422 JSON response for a raw Pydantic ValidationError."""
    detail = _format_validation_errors(exc.errors(include_url=False))
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "detail": detail,
            }
        },
    )


async def pydantic_validation_error_handler(
    request: Request,  # noqa: ARG001
    exc: ValidationError,
) -> JSONResponse:
    """FastAPI exception handler — maps Pydantic ValidationError to 422 envelope."""
    return validation_error_response(exc)


async def request_validation_error_handler(
    request: Request,  # noqa: ARG001
    exc: RequestValidationError,
) -> JSONResponse:
    """FastAPI exception handler — maps FastAPI RequestValidationError to 422 envelope.

    FastAPI wraps Pydantic v2 ValidationError in RequestValidationError before
    calling exception handlers, so we must handle both types.
    """
    detail = _format_validation_errors(exc.errors())
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "detail": detail,
            }
        },
    )


async def rate_limit_exceeded_handler(
    request: Request,  # noqa: ARG001
    exc: RateLimitExceeded,
) -> JSONResponse:
    """Custom 429 handler that adds Retry-After header (required by AC11)."""
    # Extract retry seconds from the limit string e.g. "1 per 600 second"
    import time  # noqa: PLC0415

    retry_after = 600
    try:
        if hasattr(exc, "limit") and hasattr(exc.limit, "reset_at"):
            retry_after = max(0, int(exc.limit.reset_at - time.time()))
    except Exception as _e:  # noqa: BLE001
        _ = _e  # intentional fallback to default 600s

    return JSONResponse(
        status_code=429,
        content={"error": {"code": "RATE_LIMITED", "detail": "Too many requests."}},
        headers={"Retry-After": str(retry_after)},
    )


async def generic_exception_handler(
    request: Request,  # noqa: ARG001
    exc: Exception,
) -> JSONResponse:
    """Catch-all 500 handler — never exposes stack traces to clients."""
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "detail": "An unexpected error occurred.",
            }
        },
    )
