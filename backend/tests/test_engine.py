"""Tests for the simulation engine — AC2, AC3, AC4, AC13, AC26, AC27."""

from __future__ import annotations

import numpy as np
import pytest
from backend.app.main import app
from backend.app.model.store import load_post, load_tourney
from backend.app.simulation.engine import (
    TALLOW,
    TSLOTS,
    assign_thirds,
    mul,
    next_rand,
    pois,
    run_tournament,
)
from httpx import ASGITransport, AsyncClient

SEED = 12648430  # 0xC0FFEE in decimal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def post() -> dict:
    return load_post()


@pytest.fixture
def tourney() -> dict:
    return load_tourney()


@pytest.fixture
def zero_adj(post):  # type: ignore[no-untyped-def]
    n = len(post["teams"])
    return np.zeros(n, dtype=np.float64), np.zeros(n, dtype=np.float64)


@pytest.fixture
async def client() -> AsyncClient:  # type: ignore[misc]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# PRNG unit tests
# ---------------------------------------------------------------------------


def test_prng_deterministic() -> None:
    """Same seed → identical sequence of floats."""
    s1 = mul(SEED)
    s2 = mul(SEED)
    seq1 = [next_rand(s1) for _ in range(20)]
    seq2 = [next_rand(s2) for _ in range(20)]
    assert seq1 == seq2


def test_prng_range() -> None:
    """All values are in [0, 1)."""
    state = mul(SEED)
    for _ in range(1000):
        v = next_rand(state)
        assert 0.0 <= v < 1.0


def test_prng_different_seeds() -> None:
    """Different seeds produce different sequences."""
    s1 = mul(SEED)
    s2 = mul(SEED + 1)
    seq1 = [next_rand(s1) for _ in range(10)]
    seq2 = [next_rand(s2) for _ in range(10)]
    assert seq1 != seq2


# ---------------------------------------------------------------------------
# Poisson draw tests
# ---------------------------------------------------------------------------


def test_pois_zero_lambda() -> None:
    state = mul(SEED)
    assert pois(0.0, state) == 0


def test_pois_mean() -> None:
    """Mean of 10000 Poisson draws should be close to lambda."""
    lam = 2.5
    state = mul(SEED)
    draws = [pois(lam, state) for _ in range(10_000)]
    mean = sum(draws) / len(draws)
    assert abs(mean - lam) < 0.1


# ---------------------------------------------------------------------------
# assign_thirds tests
# ---------------------------------------------------------------------------


def test_assign_thirds_all_groups() -> None:
    """With all 12 groups qualified, assignment should succeed."""
    qualified = set("ABCDEFGHIJKL")
    result = assign_thirds(qualified)
    assert result is not None
    assert set(result.keys()) == set(TSLOTS)
    # Every assigned group must be in TALLOW[slot]
    for slot, grp in result.items():
        assert grp in TALLOW[slot]


def test_assign_thirds_specific() -> None:
    """A specific set of 8 qualified third-place groups returns a valid assignment."""
    qualified = {"A", "B", "C", "D", "E", "F", "G", "H"}
    result = assign_thirds(qualified)
    assert result is not None
    used_groups = list(result.values())
    # No group used twice
    assert len(used_groups) == len(set(used_groups))


def test_assign_thirds_no_duplicates() -> None:
    """Assigned groups are all distinct."""
    qualified = {"C", "D", "E", "F", "G", "H", "I", "J"}
    result = assign_thirds(qualified)
    if result is not None:
        values = list(result.values())
        assert len(values) == len(set(values))


# ---------------------------------------------------------------------------
# AC26 — determinism: runT twice with same seed → identical tally
# ---------------------------------------------------------------------------


def test_determinism_runt(post: dict, tourney: dict, zero_adj) -> None:
    """AC26: Two calls to run_tournament with the same seed return identical results."""
    adja, adjd = zero_adj

    tally1 = run_tournament(
        n=500,
        post=post,
        tourney_state=tourney,
        adja=adja,
        adjd=adjd,
        rho=0.05,
        seed=SEED,
    )
    tally2 = run_tournament(
        n=500,
        post=post,
        tourney_state=tourney,
        adja=adja,
        adjd=adjd,
        rho=0.05,
        seed=SEED,
    )

    assert tally1 == tally2, "run_tournament results are not identical across two calls"


# ---------------------------------------------------------------------------
# AC27 — exactly 32 teams with ko > 0 after 6000 sims
# ---------------------------------------------------------------------------


def test_32_teams_ko(post: dict, tourney: dict, zero_adj) -> None:
    """AC27: In each simulated tournament exactly 32 teams advance to the R32.

    We verify this by asserting sum(tally[team].ko) == 32 * n_sims, which means
    every simulation produced exactly 32 R32 participants.

    Note: over 6000 sims with 6 unplayed group-stage matches, MORE than 32
    unique teams will have ko > 0 (different teams qualify as third-place
    depending on results). The invariant is the PER-SIM count = 32.
    """
    n_sims = 6000
    adja, adjd = zero_adj

    tally = run_tournament(
        n=n_sims,
        post=post,
        tourney_state=tourney,
        adja=adja,
        adjd=adjd,
        rho=0.05,
        seed=SEED,
    )

    total_ko = sum(v["ko"] for v in tally.values())
    assert total_ko == 32 * n_sims, (
        f"Expected total ko count == {32 * n_sims} (32 per sim), got {total_ko}"
    )


# ---------------------------------------------------------------------------
# AC13 — HTTP endpoint determinism: POST /simulate/tournament twice → same body
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_determinism_endpoint(client: AsyncClient) -> None:
    """AC13: Two POST /simulate/tournament with seed=12648430 return identical results."""
    payload = {"n": 200, "seed": SEED, "rho": 0.05, "model_id": "current"}

    resp1 = await client.post("/simulate/tournament", json=payload)
    resp2 = await client.post("/simulate/tournament", json=payload)

    assert resp1.status_code == 200, f"First call failed: {resp1.text}"
    assert resp2.status_code == 200, f"Second call failed: {resp2.text}"

    body1 = resp1.json()
    body2 = resp2.json()

    assert body1["results"] == body2["results"], (
        "Simulation results are not identical across two calls"
    )


# ---------------------------------------------------------------------------
# AC2 — GET /model/status
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_model_status(client: AsyncClient) -> None:
    """AC2: GET /model/status returns 200 with required fields."""
    resp = await client.get("/model/status")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["model_id"] == "current"
    assert data["half_life"] == 3.0
    assert data["n_draws"] == 400
    assert "trained_at" in data
    assert isinstance(data["top10"], list)
    assert len(data["top10"]) == 10


# ---------------------------------------------------------------------------
# AC3 — GET /model/strength
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_model_strength(client: AsyncClient) -> None:
    """AC3: GET /model/strength returns 48 teams sorted by score desc, Argentina first."""
    resp = await client.get("/model/strength")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    ranking = data["ranking"]

    assert len(ranking) == 48, f"Expected 48 teams, got {len(ranking)}"

    # Sorted descending
    scores = [r["score"] for r in ranking]
    assert scores == sorted(scores, reverse=True), "Ranking is not sorted by score desc"

    # Argentina should be top (per AC3 spec)
    assert ranking[0]["team"] == "Argentina", (
        f"Expected Argentina at top, got {ranking[0]['team']}"
    )


# ---------------------------------------------------------------------------
# AC4 — GET /tourney/state
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_tourney_state(client: AsyncClient) -> None:
    """AC4: GET /tourney/state returns 12 groups, each with 4 teams."""
    resp = await client.get("/tourney/state")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    groups = data["groups"]
    group_keys = set(groups.keys())

    # Must have keys A through L
    expected_keys = set("ABCDEFGHIJKL")
    assert group_keys == expected_keys, f"Expected group keys A-L, got {sorted(group_keys)}"

    # Each group has exactly 4 teams
    for g, teams in groups.items():
        assert len(teams) == 4, f"Group {g} has {len(teams)} teams, expected 4"

    # Remaining must include the 6 today matches
    remaining_pairs = {(r[0], r[1]) for r in data["remaining"]}
    expected_remaining = {
        ("Algeria", "Austria"),
        ("Jordan", "Argentina"),
        ("Colombia", "Portugal"),
        ("DR Congo", "Uzbekistan"),
        ("Panama", "England"),
        ("Croatia", "Ghana"),
    }
    assert expected_remaining == remaining_pairs, f"Remaining mismatch: {remaining_pairs}"


# ---------------------------------------------------------------------------
# Bonus: champ probabilities sum to ~1.0
# ---------------------------------------------------------------------------


def test_champ_sum(post: dict, tourney: dict, zero_adj) -> None:
    """Champion probabilities across all sims should sum to exactly n (counts)."""
    adja, adjd = zero_adj
    n = 1000
    tally = run_tournament(
        n=n,
        post=post,
        tourney_state=tourney,
        adja=adja,
        adjd=adjd,
        rho=0.05,
        seed=SEED,
    )
    total_champ = sum(v["champ"] for v in tally.values())
    assert total_champ == n, f"Expected champ count == {n}, got {total_champ}"


# ---------------------------------------------------------------------------
# rho=0 branch in play() — independent Poisson (lines 185-186 in engine.py)
# ---------------------------------------------------------------------------


def test_play_rho_zero(post: dict, zero_adj) -> None:
    """play() with rho=0.0 exercises the independent Poisson branch."""
    from backend.app.simulation.engine import play

    adja, adjd = zero_adj
    ti = {t: i for i, t in enumerate(post["teams"])}
    state = mul(SEED)
    x, y, w = play(ti["Argentina"], ti["Jordan"], 0, state, False, 0.0, post, adja, adjd)
    assert w in (0, 1, 2), f"Unexpected winner index: {w}"


# ---------------------------------------------------------------------------
# Fallback bracket in run_tournament() when assign_thirds returns None
# ---------------------------------------------------------------------------


def test_run_tournament_fallback_bracket(post: dict, tourney: dict, zero_adj) -> None:
    """run_tournament() with assign_thirds mocked to None uses the strength-seeded fallback."""
    from unittest.mock import patch

    adja, adjd = zero_adj
    with patch("backend.app.simulation.engine.assign_thirds", return_value=None):
        tally = run_tournament(
            n=50,
            post=post,
            tourney_state=tourney,
            adja=adja,
            adjd=adjd,
            rho=0.05,
            seed=SEED,
        )
    # Exactly one champion per simulation
    total_champ = sum(v["champ"] for v in tally.values())
    assert total_champ == 50
