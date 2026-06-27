"""Pydantic v2 request / response schemas for W3 endpoints.

All input schemas use ``extra="forbid"`` to reject unknown fields (OWASP API3).
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Common error envelope — {error: {code, detail}}
# ---------------------------------------------------------------------------


class ErrorDetail(BaseModel):
    code: str
    detail: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Simulation request schemas
# ---------------------------------------------------------------------------


class SimMatchRequest(BaseModel):
    home: str
    away: str
    n_per_draw: Annotated[int, Field(default=30, ge=1, le=200)] = 30
    rho: Annotated[float, Field(default=0.05, ge=0.0, le=1.0)] = 0.05
    model_id: str = "current"

    model_config = {"extra": "forbid"}


class SimModalRequest(BaseModel):
    home: str
    away: str
    top_k: Annotated[int, Field(default=10, ge=1, le=50)] = 10
    model_id: str = "current"

    model_config = {"extra": "forbid"}


class SimH2HRequest(BaseModel):
    home: str
    away: str
    knockout: bool = False
    top_k: Annotated[int, Field(default=6, ge=1, le=50)] = 6
    model_id: str = "current"

    model_config = {"extra": "forbid"}


class SimTournamentRequest(BaseModel):
    n: Annotated[int, Field(default=2500, ge=1, le=20000)] = 2500
    seed: int | None = None
    rho: Annotated[float, Field(default=0.05, ge=0.0, le=1.0)] = 0.05
    model_id: str = "current"

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Tournament state write schema
# ---------------------------------------------------------------------------


class TourneyStateBody(BaseModel):
    state: dict[str, Any]
    remaining: list[list[str]]
    groups: dict[str, list[str]]

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Model retrain request
# ---------------------------------------------------------------------------


class RetrainRequest(BaseModel):
    half_life: float
    n_draws: Annotated[int, Field(default=400, ge=100, le=2000)] = 400

    model_config = {"extra": "forbid"}

    @field_validator("half_life")
    @classmethod
    def validate_half_life(cls, v: float) -> float:
        """half_life must be in [0.5, 10.0) — strictly less than 10.0."""
        if v < 0.5 or v >= 10.0:
            raise ValueError("half_life must be in range [0.5, 10.0)")
        return v
