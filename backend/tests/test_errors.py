"""Unit tests for backend/app/errors.py — covers all handler branches."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from backend.app.errors import (
    generic_exception_handler,
    pydantic_validation_error_handler,
    rate_limit_exceeded_handler,
)
from pydantic import BaseModel, ValidationError


class _M(BaseModel):
    x: int


def _make_validation_error() -> ValidationError:
    try:
        _M(x="not-an-int")  # type: ignore[arg-type]
    except ValidationError as exc:
        return exc
    raise AssertionError("expected ValidationError")  # pragma: no cover


@pytest.mark.anyio
async def test_pydantic_validation_error_handler() -> None:
    """pydantic_validation_error_handler returns 422 with VALIDATION_ERROR envelope."""
    exc = _make_validation_error()
    response = await pydantic_validation_error_handler(MagicMock(), exc)
    assert response.status_code == 422
    body = json.loads(response.body)
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "x" in body["error"]["detail"]


@pytest.mark.anyio
async def test_generic_exception_handler_returns_500() -> None:
    """generic_exception_handler always returns 500 INTERNAL_ERROR."""
    response = await generic_exception_handler(MagicMock(), RuntimeError("boom"))
    assert response.status_code == 500
    body = json.loads(response.body)
    assert body["error"]["code"] == "INTERNAL_ERROR"


@pytest.mark.anyio
async def test_rate_limit_handler_fallback_on_bad_reset_at() -> None:
    """rate_limit_exceeded_handler falls back to Retry-After: 600 when reset_at is invalid."""
    mock_exc = MagicMock()
    mock_exc.limit.reset_at = "not-a-timestamp"
    response = await rate_limit_exceeded_handler(MagicMock(), mock_exc)
    assert response.status_code == 429
    body = json.loads(response.body)
    assert body["error"]["code"] == "RATE_LIMITED"
    assert response.headers.get("retry-after") == "600"
