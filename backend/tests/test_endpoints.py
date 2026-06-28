"""Integration tests for W3 API endpoints.

Covers AC1, AC5, AC6, AC7, AC8, AC9, AC10, AC11, AC12, AC14, AC15.
Uses the ASGI test transport so no server needs to run.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from backend.app.main import app
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client() -> AsyncClient:
    """Async HTTP client wired to the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# AC1 — GET /teams
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_teams(client: AsyncClient) -> None:
    """AC1: GET /teams → 200, body.teams is a list of 48 strings."""
    resp = await client.get("/teams")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "teams" in data
    teams = data["teams"]
    assert isinstance(teams, list)
    assert len(teams) == 48
    # Spot-check a few required teams
    for required in ("Argentina", "Portugal", "Brazil"):
        assert required in teams, f"Expected {required} in teams"
    # All elements are strings
    assert all(isinstance(t, str) for t in teams)


# ---------------------------------------------------------------------------
# AC5 — PUT /tourney/state then GET returns new data
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_put_tourney(client: AsyncClient) -> None:
    """AC5: PUT /tourney/state updates state; subsequent GET returns new document."""
    # First read current state so we can restore it after
    get_resp = await client.get("/tourney/state")
    assert get_resp.status_code == 200
    original = get_resp.json()

    # Build a modified state — just change one points value
    modified = {
        "state": dict(original["state"]),
        "remaining": original["remaining"],
        "groups": original["groups"],
    }
    first_team = list(modified["state"].keys())[0]
    modified["state"][first_team] = dict(modified["state"][first_team])
    modified["state"][first_team]["pts"] = 999  # sentinel

    put_resp = await client.put("/tourney/state", json=modified)
    assert put_resp.status_code == 200, put_resp.text
    assert put_resp.json()["ok"] is True

    # Verify GET returns the updated value
    get_resp2 = await client.get("/tourney/state")
    assert get_resp2.status_code == 200
    new_data = get_resp2.json()
    assert new_data["state"][first_team]["pts"] == 999

    # Restore original state
    await client.put("/tourney/state", json=original)


# ---------------------------------------------------------------------------
# AC6 — POST /simulate/tournament
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_simulate_tournament(client: AsyncClient) -> None:
    """AC6: POST /simulate/tournament with n=6000, seed=12648430 → 48 results."""
    payload = {
        "n": 6000,
        "seed": 12648430,
        "rho": 0.05,
        "model_id": "current",
    }
    resp = await client.post("/simulate/tournament", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    results = data["results"]
    assert len(results) == 48, f"Expected 48, got {len(results)}"

    # Each entry must have champ in [0,1]
    for r in results:
        assert 0.0 <= r["champ"] <= 1.0, f"champ out of range: {r['champ']}"

    # Check sum of champs ≈ 1.0
    total_champ = sum(r["champ"] for r in results)
    assert abs(total_champ - 1.0) < 0.01, f"champ sum {total_champ:.4f} not near 1.0"

    # At least 32 teams have ko > 0
    ko_positive = sum(1 for r in results if r["ko"] > 0)
    assert ko_positive >= 32, f"Expected ≥32 teams with ko>0, got {ko_positive}"


# ---------------------------------------------------------------------------
# AC7 — POST /simulate/match probabilities sum to 1
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_simulate_match_probs_sum(client: AsyncClient) -> None:
    """AC7: POST /simulate/match Argentina vs Jordan → pH+pD+pA within 0.001 of 1.0."""
    payload = {
        "home": "Argentina",
        "away": "Jordan",
        "n_per_draw": 30,
        "rho": 0.05,
    }
    resp = await client.post("/simulate/match", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    total = data["pH"] + data["pD"] + data["pA"]
    assert abs(total - 1.0) < 0.001, f"pH+pD+pA = {total:.6f}, expected ~1.0"
    # Argentina should be heavy favourite
    assert data["pH"] > data["pA"], "Argentina should win more often than Jordan"


# ---------------------------------------------------------------------------
# AC8 — POST /simulate/modal
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_simulate_modal(client: AsyncClient) -> None:
    """AC8: POST /simulate/modal → ≤10 scorelines with {h, a, prob} integers."""
    payload = {
        "home": "Argentina",
        "away": "Jordan",
        "top_k": 10,
    }
    resp = await client.post("/simulate/modal", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    scorelines = data["scorelines"]
    assert len(scorelines) <= 10
    assert len(scorelines) > 0

    for sl in scorelines:
        assert "h" in sl, "scoreline missing 'h'"
        assert "a" in sl, "scoreline missing 'a'"
        assert "prob" in sl, "scoreline missing 'prob'"
        assert isinstance(sl["h"], int), f"h is not int: {sl['h']!r}"
        assert isinstance(sl["a"], int), f"a is not int: {sl['a']!r}"
        assert isinstance(sl["prob"], float)
        assert 0.0 < sl["prob"] <= 1.0


# ---------------------------------------------------------------------------
# AC9 — POST /simulate/h2h
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_simulate_h2h(client: AsyncClient) -> None:
    """AC9: POST /simulate/h2h → 200 with ci_lower/ci_median/ci_upper/top_scorelines."""
    payload = {
        "home": "Colombia",
        "away": "Portugal",
        "knockout": False,
        "top_k": 6,
    }
    resp = await client.post("/simulate/h2h", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    for field in ("pH", "pD", "pA", "ci_lower", "ci_median", "ci_upper", "top_scorelines"):
        assert field in data, f"Missing field: {field}"

    # CI ordering
    assert data["ci_lower"] <= data["ci_median"] <= data["ci_upper"], (
        f"CI not ordered: lower={data['ci_lower']}, median={data['ci_median']}, "
        f"upper={data['ci_upper']}"
    )

    # Probs sum roughly to 1
    total = data["pH"] + data["pD"] + data["pA"]
    assert abs(total - 1.0) < 0.01, f"pH+pD+pA = {total:.4f}"

    assert len(data["top_scorelines"]) == 6


# ---------------------------------------------------------------------------
# AC10 — GET /market/odds
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_market_odds(client: AsyncClient) -> None:
    """AC10: GET /market/odds → 6 entries as a list with home/away/h/d/a."""
    resp = await client.get("/market/odds")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    odds = data["odds"]
    assert isinstance(odds, list), "odds should be a list"
    assert len(odds) == 6, f"Expected 6 matches, got {len(odds)}"

    for entry in odds:
        assert "home" in entry, f"Missing 'home' in {entry}"
        assert "away" in entry, f"Missing 'away' in {entry}"
        assert "h" in entry, f"Missing 'h' in {entry}"
        assert "a" in entry, f"Missing 'a' in {entry}"
        assert isinstance(entry["h"], int), f"h is not int in {entry}"
        assert isinstance(entry["a"], int), f"a is not int in {entry}"


@pytest.mark.anyio
async def test_put_market_odds(client: AsyncClient) -> None:
    """AC10: PUT /market/odds → 200 and save_market called with the correct payload."""
    # Read current odds (now a list)
    get_resp = await client.get("/market/odds")
    assert get_resp.status_code == 200
    original_list = get_resp.json()["odds"]
    assert len(original_list) > 0

    # Reconstruct dict format expected by PUT ("home|away" → {h,d,a})
    first_entry = original_list[0]
    first_key = f"{first_entry['home']}|{first_entry['away']}"
    modified_odds = {
        f"{e['home']}|{e['away']}": {"h": e["h"], "d": e.get("d"), "a": e["a"]}
        for e in original_list
    }
    modified_odds[first_key]["h"] = 9999  # sentinel

    # Patch save_market to avoid writing to the fixtures directory on disk
    with patch("backend.app.main.save_market") as mock_save:
        put_resp = await client.put("/market/odds", json={"odds": modified_odds})
        assert put_resp.status_code == 200, put_resp.text
        assert put_resp.json()["ok"] is True

        # Verify save_market was called once with the updated odds
        mock_save.assert_called_once()
        saved_arg: dict = mock_save.call_args[0][0]
        assert saved_arg[first_key]["h"] == 9999, (
            f"save_market not called with sentinel h=9999, got {saved_arg[first_key]['h']}"
        )


# ---------------------------------------------------------------------------
# GET /tourney/r32
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_r32(client: AsyncClient) -> None:
    """GET /tourney/r32 → 16 matches with pH/pD/pA and optional coach names."""
    resp = await client.get("/tourney/r32")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    matches = data["matches"]
    assert isinstance(matches, list)
    assert len(matches) == 16, f"Expected 16 R32 matches, got {len(matches)}"

    for m in matches:
        assert "id" in m
        assert 73 <= m["id"] <= 88
        assert "home" in m and "away" in m
        assert "pH" in m and "pD" in m and "pA" in m
        total = m["pH"] + m["pD"] + m["pA"]
        assert abs(total - 1.0) < 0.05, f"Probabilities don't sum to ~1: {total}"
        assert "played" in m
        assert "uncertain" in m


@pytest.mark.anyio
async def test_put_r32_result(client: AsyncClient) -> None:
    """PUT /tourney/r32/{match_id} → 200 with ok=True and saves via save_r32."""
    with patch("backend.app.main.save_r32") as mock_save:
        resp = await client.put("/tourney/r32/73", json={"score_h": 2, "score_a": 1})
        assert resp.status_code == 200, resp.text
        assert resp.json()["ok"] is True
        mock_save.assert_called_once()


@pytest.mark.anyio
async def test_put_r32_result_invalid_id(client: AsyncClient) -> None:
    """PUT /tourney/r32/{match_id} with out-of-range id → 400."""
    resp = await client.put("/tourney/r32/1", json={"score_h": 0, "score_a": 0})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# AC11 — POST /model/retrain rate-limit (429 with Retry-After)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_retrain_rate_limit(client: AsyncClient) -> None:
    """AC11: Second retrain call within 600s → 429 with Retry-After header."""
    # Patch the trainer so no network call is made
    mock_meta = {
        "model_id": "current",
        "trained_at": "2026-06-27T00:00:00+00:00",
        "half_life": 3.0,
        "n_draws": 400,
        "top10": ["Argentina"] * 10,
    }

    with patch(
        "backend.app.main.asyncio.to_thread",
        new_callable=AsyncMock,
        return_value=mock_meta,
    ):
        # First call should succeed
        first = await client.post(
            "/model/retrain",
            json={"half_life": 3.0, "n_draws": 400},
        )
        assert first.status_code == 200, f"First retrain failed: {first.text}"

        # Second call within the rate-limit window should be 429
        second = await client.post(
            "/model/retrain",
            json={"half_life": 3.0, "n_draws": 400},
        )
        assert second.status_code == 429, (
            f"Expected 429 for rate-limited second call, got {second.status_code}"
        )
        assert "Retry-After" in second.headers or "retry-after" in second.headers, (
            "429 response missing Retry-After header"
        )


# ---------------------------------------------------------------------------
# AC12 — POST /model/retrain validation (half_life out of range)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_retrain_validation(client: AsyncClient) -> None:
    """AC12: half_life=0.1 → 422, code=VALIDATION_ERROR."""
    resp = await client.post(
        "/model/retrain",
        json={"half_life": 0.1, "n_draws": 400},
    )
    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "error" in data, f"Missing 'error' key: {data}"
    assert data["error"]["code"] == "VALIDATION_ERROR", (
        f"Expected VALIDATION_ERROR, got {data['error']['code']}"
    )


@pytest.mark.anyio
async def test_retrain_validation_too_high(client: AsyncClient) -> None:
    """AC12: half_life=15.0 (≥10.0) → 422, code=VALIDATION_ERROR."""
    resp = await client.post(
        "/model/retrain",
        json={"half_life": 15.0, "n_draws": 400},
    )
    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# AC14 — CORS: allowed and blocked origins
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_cors_allowed(client: AsyncClient) -> None:
    """AC14: OPTIONS /teams with Origin: http://localhost:5173 → ACAO header present."""
    resp = await client.options(
        "/teams",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    # FastAPI returns 200 for preflight when origin is allowed
    acao = resp.headers.get("access-control-allow-origin", "")
    assert acao == "http://localhost:5173", f"Expected ACAO=http://localhost:5173, got '{acao}'"


@pytest.mark.anyio
async def test_cors_blocked(client: AsyncClient) -> None:
    """AC14: OPTIONS /teams with Origin: http://evil.com → no ACAO header."""
    resp = await client.options(
        "/teams",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    acao = resp.headers.get("access-control-allow-origin", "")
    assert acao == "" or acao is None, f"Expected no ACAO header for evil.com, got '{acao}'"


# ---------------------------------------------------------------------------
# AC15 — POST /simulate/match unknown team → 400 UNKNOWN_TEAM
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_unknown_team(client: AsyncClient) -> None:
    """AC15: home=Atlantis → 400, code=UNKNOWN_TEAM."""
    resp = await client.post(
        "/simulate/match",
        json={"home": "Atlantis", "away": "Argentina"},
    )
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "error" in data, f"Missing 'error' key: {data}"
    assert data["error"]["code"] == "UNKNOWN_TEAM", (
        f"Expected UNKNOWN_TEAM, got {data['error']['code']}"
    )
    assert "Atlantis" in data["error"]["detail"], (
        f"Expected team name in detail: {data['error']['detail']}"
    )
