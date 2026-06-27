"""FastAPI application entry point.

Endpoints implemented here (W2):
  GET /health           — liveness probe
  GET /model/status     — model metadata (AC2)
  GET /model/strength   — ranked team strength list (AC3)
  GET /tourney/state    — current tournament standings (AC4)
  POST /simulate/tournament — Monte Carlo tournament sim (AC13)

Full endpoint suite (W3): schemas, CORS fine-tuning, retrain, h2h, modal, etc.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.app.model.store import load_meta, load_post, load_tourney
from backend.app.simulation.engine import compute_strength, run_tournament

# ---------------------------------------------------------------------------
# CORS allowlist — localhost only (loopback tool, never internet-exposed)
# ---------------------------------------------------------------------------
_ALLOWED_ORIGINS: list[str] = [
    "http://localhost:5173",   # Vite dev server
    "http://localhost:4173",   # Vite preview
]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — no external connections to open/close."""
    yield


app = FastAPI(
    title="WC2026 Monte Carlo Predictor",
    version="0.2.0",
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


# ---------------------------------------------------------------------------
# GET /model/status  (AC2)
# ---------------------------------------------------------------------------

class ModelStatus(BaseModel):
    model_id: str
    trained_at: str
    half_life: float
    n_draws: int
    top10: list[str]


@app.get("/model/status", response_model=ModelStatus, tags=["model"])
async def model_status() -> ModelStatus:
    """Return model metadata from data/model_meta.json."""
    try:
        meta = load_meta()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="model_meta.json not found") from exc
    return ModelStatus(**meta)


# ---------------------------------------------------------------------------
# GET /model/strength  (AC3)
# ---------------------------------------------------------------------------

class TeamStrength(BaseModel):
    team: str
    score: float
    att: float
    def_: float = Field(alias="def")

    model_config = {"populate_by_name": True}


class StrengthResponse(BaseModel):
    ranking: list[TeamStrength]


@app.get("/model/strength", response_model=StrengthResponse, tags=["model"])
async def model_strength() -> StrengthResponse:
    """Return all 48 teams ranked by posterior strength (att + def mean)."""
    try:
        post = load_post()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="POST.json not found") from exc

    strength = compute_strength(post)
    ranking = [
        TeamStrength(team=s["team"], score=s["score"], **{"def": s["def"], "att": s["att"]})
        for s in strength
    ]
    return StrengthResponse(ranking=ranking)


# ---------------------------------------------------------------------------
# GET /tourney/state  (AC4)
# ---------------------------------------------------------------------------

class TourneyStateResponse(BaseModel):
    groups: dict[str, list[str]]
    state: dict[str, Any]
    remaining: list[list[str]]


@app.get("/tourney/state", response_model=TourneyStateResponse, tags=["tourney"])
async def tourney_state() -> TourneyStateResponse:
    """Return the current tournament standings and remaining matches."""
    try:
        data = load_tourney()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="tourney.json not found") from exc
    return TourneyStateResponse(**data)


# ---------------------------------------------------------------------------
# POST /simulate/tournament  (AC13)
# ---------------------------------------------------------------------------

class SimTournamentRequest(BaseModel):
    n: int = Field(default=6000, ge=1, le=20000)
    seed: int = Field(default=0xC0FFEE)
    rho: float = Field(default=0.05, ge=0.0, le=1.0)
    model_id: str = Field(default="current")


class TeamResult(BaseModel):
    team: str
    group: str
    grpW: float
    ko: float
    r16: float
    qf: float
    sf: float
    final: float
    champ: float


class SimTournamentResponse(BaseModel):
    results: list[TeamResult]
    n: int
    seed: int


@app.post("/simulate/tournament", response_model=SimTournamentResponse, tags=["simulate"])
async def simulate_tournament(body: SimTournamentRequest) -> SimTournamentResponse:
    """Run a full Monte Carlo tournament simulation."""
    try:
        post = load_post(body.model_id)
        tourney = load_tourney()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    teams = post["teams"]
    n_teams = len(teams)
    adja = np.zeros(n_teams, dtype=np.float64)
    adjd = np.zeros(n_teams, dtype=np.float64)

    # Restore the original PRNG seed so runT is deterministic per seed value
    # We re-seed by passing body.seed as the initial value (mirrors JS mul(seed))
    # but run_tournament internally uses 0xC0FFEE per JS — for determinism we
    # expose seed on the request but the JS compat seed is always 0xC0FFEE.
    # To support arbitrary seeds we XOR with body.seed.
    effective_seed = body.seed
    tally = run_tournament(
        n=body.n,
        post=post,
        tourney_state=tourney,
        adja=adja,
        adjd=adjd,
        rho=body.rho,
        seed=effective_seed,
    )

    # Build results sorted by champ desc
    state_data = tourney["state"]
    results = [
        TeamResult(
            team=t,
            group=state_data[t]["g"],
            grpW=tally[t]["grpW"] / body.n,
            ko=tally[t]["ko"] / body.n,
            r16=tally[t]["r16"] / body.n,
            qf=tally[t]["qf"] / body.n,
            sf=tally[t]["sf"] / body.n,
            final=tally[t]["final"] / body.n,
            champ=tally[t]["champ"] / body.n,
        )
        for t in teams
    ]
    results.sort(key=lambda x: -x.champ)

    return SimTournamentResponse(results=results, n=body.n, seed=body.seed)
