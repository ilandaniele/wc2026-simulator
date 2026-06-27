"""Pytest fixtures — stub.

Full fixtures (DB session, seed data, etc.) added in W2/W3.
"""

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
