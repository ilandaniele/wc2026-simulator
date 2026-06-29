"""Pytest fixtures — stub.

Full fixtures (DB session, seed data, etc.) added in W2/W3.
"""

import os

# Point all store I/O at the test fixtures so local runs match CI.
# Must be set before any backend module is imported (store reads DATA_DIR at
# module level).
os.environ.setdefault("DATA_DIR", "backend/tests/fixtures")

import pytest
from backend.app.main import app
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client() -> AsyncClient:
    """Async HTTP client bound to the FastAPI test app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
