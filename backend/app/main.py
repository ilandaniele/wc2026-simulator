"""FastAPI application entry point â€" full endpoint suite (W2 + W3).

W2 endpoints (unchanged):
  GET  /health                â€" liveness probe
  GET  /model/status          â€" model metadata (AC2)
  GET  /model/strength        â€" ranked team strength list (AC3)
  GET  /tourney/state         â€" current tournament standings (AC4)
  POST /simulate/tournament   â€" Monte Carlo tournament sim (AC6, AC13)

W3 endpoints (new):
  GET  /teams                 â€" list 48 team names (AC1)
  PUT  /tourney/state         â€" update tournament standings (AC5)
  POST /simulate/match        â€" single-match prob (AC7, AC15)
  POST /simulate/modal        â€" score distribution (AC8)
  POST /simulate/h2h          â€" head-to-head CI (AC9)
  GET  /market/odds           â€" today's bookmaker odds (AC10)
  POST /model/retrain         â€" retrain model, rate-limited 1/600s (AC11, AC12)
"""

from __future__ import annotations

import asyncio
import collections
import math
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import numpy as np
from backend.app.errors import (
    generic_exception_handler,
    pydantic_validation_error_handler,
    rate_limit_exceeded_handler,
    request_validation_error_handler,
    unknown_team_response,
)
from backend.app.model.store import (
    load_market,
    load_meta,
    load_post,
    load_tourney,
    save_market,
    save_tourney,
)
from backend.app.schemas import (
    RetrainRequest,
    SimH2HRequest,
    SimMatchRequest,
    SimModalRequest,
    SimTournamentRequest,
    TourneyStateBody,
)
from backend.app.simulation.engine import (
    compute_strength,
    lams,
    mul,
    pois,
    run_tournament,
)
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# ---------------------------------------------------------------------------
# CORS allowlist - configurable via ALLOWED_ORIGINS env var (comma-separated).
# Default: localhost only for local development.
# ---------------------------------------------------------------------------

_raw = os.environ.get("ALLOWED_ORIGINS", "")
_ALLOWED_ORIGINS: list[str] = list(
    dict.fromkeys(
        [o.strip() for o in _raw.split(",") if o.strip()]
        + [
            "http://localhost:5173",
            "http://localhost:4173",
            "https://wc2026-frontend-owmd.onrender.com",
        ]
    )
)

# ---------------------------------------------------------------------------
# Rate limiter (slowapi)
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan â€" no external connections to open/close."""
    yield


# ---------------------------------------------------------------------------
# App construction
# ---------------------------------------------------------------------------

app = FastAPI(
    title="WC2026 Monte Carlo Predictor",
    version="0.3.0",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

# Rate limiter state
app.state.limiter = limiter

# Middleware: CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# Exception handlers â€" ordered from most-specific to least-specific
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, request_validation_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(ValidationError, pydantic_validation_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, generic_exception_handler)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_teams(post: dict[str, Any], *team_names: str) -> None:
    """Raise a JSON 400 error via HTTPException lookalike for unknown team names.

    Instead of raising HTTPException we return a JSONResponse directly from
    endpoints so the error envelope is exactly {error: {code, detail}}.
    """
    known = set(post["teams"])
    for name in team_names:
        if name not in known:
            raise _UnknownTeamError(name)


class _UnknownTeamError(Exception):
    """Raised internally when a team name is not in the model."""

    def __init__(self, team: str) -> None:
        super().__init__(team)
        self.team = team


def _m_prob(
    home_idx: int,
    away_idx: int,
    post: dict[str, Any],
    n_per_draw: int,
    rho: float,
) -> tuple[float, float, float]:
    """Compute marginal win/draw/loss probabilities via Monte Carlo over all draws.

    Mirrors the JS ``mProb()`` function:
    - For each posterior draw, compute (lh, la) and draw ``n_per_draw`` match outcomes.
    - Aggregate to pH, pD, pA fractions.
    """
    adja = np.zeros(len(post["teams"]), dtype=np.float64)
    adjd = np.zeros(len(post["teams"]), dtype=np.float64)

    n_draws = len(post["base"])
    wins_h = 0
    draws = 0
    wins_a = 0
    rng = mul(0xC0FFEE)

    for d in range(n_draws):
        lh, la = lams(home_idx, away_idx, d, post, adja, adjd)
        for _ in range(n_per_draw):
            if rho > 0:
                l3 = rho * min(lh, la)
                c = pois(l3, rng)
                x = pois(lh - l3, rng) + c
                y = pois(la - l3, rng) + c
            else:
                x = pois(lh, rng)
                y = pois(la, rng)
            if x > y:
                wins_h += 1
            elif y > x:
                wins_a += 1
            else:
                draws += 1

    total = n_draws * n_per_draw
    return wins_h / total, draws / total, wins_a / total


def _score_distribution(
    home_idx: int,
    away_idx: int,
    post: dict[str, Any],
    rho: float,
    top_k: int,
) -> list[dict[str, Any]]:
    """Compute score distribution across all draws (exact Poisson convolution).

    For each draw, compute P(h goals, a goals) analytically (Poisson PMF),
    then average across draws.  Returns top-k scorelines by probability.
    """
    adja = np.zeros(len(post["teams"]), dtype=np.float64)
    adjd = np.zeros(len(post["teams"]), dtype=np.float64)

    n_draws = len(post["base"])
    score_counts: dict[tuple[int, int], float] = collections.defaultdict(float)

    max_goals = 8

    for d in range(n_draws):
        lh, la = lams(home_idx, away_idx, d, post, adja, adjd)
        # Independent Poisson PMF (bivariate adjustment small, use expected lh/la)
        for h_g in range(max_goals + 1):
            p_h = math.exp(-lh) * (lh**h_g) / math.factorial(h_g)
            if p_h < 1e-6:
                continue
            for a_g in range(max_goals + 1):
                p_a = math.exp(-la) * (la**a_g) / math.factorial(a_g)
                if p_a < 1e-6:
                    continue
                score_counts[(h_g, a_g)] += p_h * p_a / n_draws

    sorted_scores = sorted(score_counts.items(), key=lambda x: -x[1])
    return [{"h": h, "a": a, "prob": round(prob, 6)} for (h, a), prob in sorted_scores[:top_k]]


def _h2h_ci(
    home_idx: int,
    away_idx: int,
    post: dict[str, Any],
    rho: float,
    n_ci_draws: int = 400,
) -> tuple[float, float, float, float, float, float]:
    """Compute pH, pD, pA plus credible interval (lo, med, hi) on pH.

    Strategy: sample n_ci_draws posterior draws; for each, compute the
    expected pH analytically from lh/la Poisson.  Return (pH, pD, pA) as
    means and the 5th/50th/95th percentile of the per-draw pH distribution.
    """
    adja = np.zeros(len(post["teams"]), dtype=np.float64)
    adjd = np.zeros(len(post["teams"]), dtype=np.float64)

    n_draws = len(post["base"])
    step = max(1, n_draws // n_ci_draws)
    idxs = list(range(0, n_draws, step))

    ph_per_draw: list[float] = []
    pd_per_draw: list[float] = []
    pa_per_draw: list[float] = []

    max_goals = 8

    for d in idxs:
        lh, la = lams(home_idx, away_idx, d, post, adja, adjd)
        ph_d = pd_d = pa_d = 0.0
        for h_g in range(max_goals + 1):
            p_h = math.exp(-lh) * (lh**h_g) / math.factorial(h_g)
            if p_h < 1e-8:
                continue
            for a_g in range(max_goals + 1):
                p_a = math.exp(-la) * (la**a_g) / math.factorial(a_g)
                p = p_h * p_a
                if h_g > a_g:
                    ph_d += p
                elif h_g < a_g:
                    pa_d += p
                else:
                    pd_d += p
        ph_per_draw.append(ph_d)
        pd_per_draw.append(pd_d)
        pa_per_draw.append(pa_d)

    ph_arr = np.array(ph_per_draw)
    pd_arr = np.array(pd_per_draw)
    pa_arr = np.array(pa_per_draw)

    ph = float(ph_arr.mean())
    pd = float(pd_arr.mean())
    pa = float(pa_arr.mean())

    ci_lo = float(np.percentile(ph_arr, 5))
    ci_med = float(np.percentile(ph_arr, 50))
    ci_hi = float(np.percentile(ph_arr, 95))

    return ph, pd, pa, ci_lo, ci_med, ci_hi


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe â€" returns 200 when the process is up."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# GET /teams  (AC1)
# ---------------------------------------------------------------------------


class TeamsResponse(BaseModel):
    teams: list[str]


@app.get("/teams", response_model=TeamsResponse, tags=["model"])
async def get_teams() -> TeamsResponse:
    """Return the ordered list of 48 WC2026 teams from the model."""
    try:
        post = load_post()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="POST.json not found") from exc
    return TeamsResponse(teams=post["teams"])


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
# PUT /tourney/state  (AC5)
# ---------------------------------------------------------------------------


@app.put("/tourney/state", response_model=dict, tags=["tourney"])
async def put_tourney_state(body: TourneyStateBody) -> dict[str, bool]:
    """Replace the current tournament state document atomically."""
    try:
        save_tourney(body.model_dump())
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Write failed: {exc}") from exc
    return {"ok": True}


# ---------------------------------------------------------------------------
# POST /simulate/tournament  (AC6, AC13)
# ---------------------------------------------------------------------------


class TeamResult(BaseModel):
    team: str
    group: str
    grpW: float  # noqa: N815
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

    effective_seed = body.seed if body.seed is not None else 0xC0FFEE
    tally = run_tournament(
        n=body.n,
        post=post,
        tourney_state=tourney,
        adja=adja,
        adjd=adjd,
        rho=body.rho,
        seed=effective_seed,
    )

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

    return SimTournamentResponse(results=results, n=body.n, seed=effective_seed)


# ---------------------------------------------------------------------------
# POST /simulate/match  (AC7, AC15)
# ---------------------------------------------------------------------------


class SimMatchResponse(BaseModel):
    pH: float  # noqa: N815
    pD: float  # noqa: N815
    pA: float  # noqa: N815
    fair_odd_home: float | None = None
    fair_odd_away: float | None = None


@app.post("/simulate/match", response_model=SimMatchResponse, tags=["simulate"])
async def simulate_match(body: SimMatchRequest) -> SimMatchResponse | JSONResponse:
    """Compute home/draw/away probabilities for a single match."""
    try:
        post = load_post(body.model_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        _validate_teams(post, body.home, body.away)
    except _UnknownTeamError as exc:
        return unknown_team_response(exc.team)

    ti = {t: i for i, t in enumerate(post["teams"])}
    hi = ti[body.home]
    ai = ti[body.away]

    ph, pd, pa = _m_prob(hi, ai, post, body.n_per_draw, body.rho)

    fair_odd_home = round(1.0 / ph, 3) if ph > 0 else None
    fair_odd_away = round(1.0 / pa, 3) if pa > 0 else None

    return SimMatchResponse(
        pH=ph, pD=pd, pA=pa, fair_odd_home=fair_odd_home, fair_odd_away=fair_odd_away
    )


# ---------------------------------------------------------------------------
# POST /simulate/modal  (AC8)
# ---------------------------------------------------------------------------


class ScoreLine(BaseModel):
    h: int
    a: int
    prob: float


class SimModalResponse(BaseModel):
    scorelines: list[ScoreLine]


@app.post("/simulate/modal", response_model=SimModalResponse, tags=["simulate"])
async def simulate_modal(body: SimModalRequest) -> SimModalResponse | JSONResponse:
    """Return the top-k most probable scorelines for a match."""
    try:
        post = load_post(body.model_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        _validate_teams(post, body.home, body.away)
    except _UnknownTeamError as exc:
        return unknown_team_response(exc.team)

    ti = {t: i for i, t in enumerate(post["teams"])}
    hi = ti[body.home]
    ai = ti[body.away]

    raw = _score_distribution(hi, ai, post, rho=body.rho, top_k=body.top_k)
    scorelines = [ScoreLine(**s) for s in raw]
    return SimModalResponse(scorelines=scorelines)


# ---------------------------------------------------------------------------
# POST /simulate/h2h  (AC9)
# ---------------------------------------------------------------------------


class SimH2HResponse(BaseModel):
    pH: float  # noqa: N815
    pD: float  # noqa: N815
    pA: float  # noqa: N815
    ci_lower: float
    ci_median: float
    ci_upper: float
    top_scorelines: list[ScoreLine]


@app.post("/simulate/h2h", response_model=SimH2HResponse, tags=["simulate"])
async def simulate_h2h(body: SimH2HRequest) -> SimH2HResponse | JSONResponse:
    """Head-to-head analysis: pH/pD/pA + credible interval + top-k scorelines."""
    try:
        post = load_post(body.model_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        _validate_teams(post, body.home, body.away)
    except _UnknownTeamError as exc:
        return unknown_team_response(exc.team)

    ti = {t: i for i, t in enumerate(post["teams"])}
    hi = ti[body.home]
    ai = ti[body.away]

    ph, pd, pa, ci_lo, ci_med, ci_hi = _h2h_ci(hi, ai, post, rho=body.rho)
    scorelines_raw = _score_distribution(hi, ai, post, rho=body.rho, top_k=body.top_k)
    top_scorelines = [ScoreLine(**s) for s in scorelines_raw]

    return SimH2HResponse(
        pH=ph,
        pD=pd,
        pA=pa,
        ci_lower=ci_lo,
        ci_median=ci_med,
        ci_upper=ci_hi,
        top_scorelines=top_scorelines,
    )


# ---------------------------------------------------------------------------
# GET /market/odds  (AC10)
# ---------------------------------------------------------------------------


class OddsEntry(BaseModel):
    h: int
    d: int | None = None
    a: int


class MarketOddsResponse(BaseModel):
    odds: dict[str, OddsEntry]


@app.get("/market/odds", response_model=MarketOddsResponse, tags=["market"])
async def market_odds() -> MarketOddsResponse:
    """Return today's bookmaker odds from data/market.json."""
    try:
        data = load_market()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="market.json not found") from exc
    odds = {k: OddsEntry(**v) for k, v in data.items()}
    return MarketOddsResponse(odds=odds)


# ---------------------------------------------------------------------------
# PUT /market/odds  (AC10)
# ---------------------------------------------------------------------------


class MarketOddsBody(BaseModel):
    odds: dict[str, OddsEntry]

    model_config = {"extra": "forbid"}


@app.put("/market/odds", response_model=dict, tags=["market"])
async def put_market_odds(body: MarketOddsBody) -> dict[str, bool]:
    """Replace today's bookmaker odds document atomically."""
    try:
        save_market({k: v.model_dump() for k, v in body.odds.items()})
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Write failed: {exc}") from exc
    return {"ok": True}


# ---------------------------------------------------------------------------
# POST /model/retrain  (AC11, AC12)
# Rate-limited: 1 request per 600 seconds (10 minutes)
# ---------------------------------------------------------------------------


class RetrainResponse(BaseModel):
    ok: bool
    model_id: str
    trained_at: str
    top10: list[str]


@app.post("/model/retrain", response_model=RetrainResponse, tags=["model"])
@limiter.limit("1/600 seconds")
async def model_retrain(
    request: Request,  # required by slowapi
    body: RetrainRequest,
) -> RetrainResponse | JSONResponse:
    """Retrain the model.  Rate-limited to 1 call per 10 minutes."""
    from backend.app.model.trainer import retrain as _retrain  # noqa: PLC0415

    meta = await asyncio.to_thread(_retrain, half_life=body.half_life, n_draws=body.n_draws)
    return RetrainResponse(
        ok=True,
        model_id=meta["model_id"],
        trained_at=meta["trained_at"],
        top10=meta["top10"],
    )
