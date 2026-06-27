"""FastAPI application entry point.

Stub — full endpoints wired in W2 / W3.
Only /health is implemented here.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# CORS allowlist — localhost only (loopback tool, never internet-exposed)
# ---------------------------------------------------------------------------
_ALLOWED_ORIGINS: list[str] = [
    "http://localhost:5173",   # Vite dev server
    "http://localhost:4173",   # Vite preview
]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup / shutdown hooks."""
    # Startup: nothing to initialise in the stub
    yield
    # Shutdown: nothing to dispose in the stub


app = FastAPI(
    title="WC2026 Monte Carlo Predictor",
    version="0.1.0",
    # Disable interactive docs in the stub; re-enabled via env var in W3
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe — returns 200 when the process is up."""
    return {"status": "ok"}
