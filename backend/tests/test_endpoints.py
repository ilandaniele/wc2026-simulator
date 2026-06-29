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


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_health(client: AsyncClient) -> None:
    """GET /health → 200 {status: ok}."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# FileNotFoundError → 503 for various endpoints
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_teams_file_not_found(client: AsyncClient) -> None:
    """GET /teams when POST.json missing → 503."""
    with patch("backend.app.main.load_post", side_effect=FileNotFoundError("POST.json")):
        resp = await client.get("/teams")
    assert resp.status_code == 503


@pytest.mark.anyio
async def test_model_status_file_not_found(client: AsyncClient) -> None:
    """GET /model/status when model_meta.json missing → 503."""
    with patch("backend.app.main.load_meta", side_effect=FileNotFoundError("meta")):
        resp = await client.get("/model/status")
    assert resp.status_code == 503


@pytest.mark.anyio
async def test_model_strength_file_not_found(client: AsyncClient) -> None:
    """GET /model/strength when POST.json missing → 503."""
    with patch("backend.app.main.load_post", side_effect=FileNotFoundError("POST.json")):
        resp = await client.get("/model/strength")
    assert resp.status_code == 503


@pytest.mark.anyio
async def test_tourney_state_file_not_found(client: AsyncClient) -> None:
    """GET /tourney/state when tourney.json missing → 503."""
    with patch("backend.app.main.load_tourney", side_effect=FileNotFoundError("tourney")):
        resp = await client.get("/tourney/state")
    assert resp.status_code == 503


@pytest.mark.anyio
async def test_simulate_tournament_file_not_found(client: AsyncClient) -> None:
    """POST /simulate/tournament when POST.json missing → 503."""
    with patch("backend.app.main.load_post", side_effect=FileNotFoundError("POST.json")):
        resp = await client.post(
            "/simulate/tournament",
            json={"n": 10, "rho": 0.05, "model_id": "current"},
        )
    assert resp.status_code == 503


@pytest.mark.anyio
async def test_simulate_match_file_not_found(client: AsyncClient) -> None:
    """POST /simulate/match when POST.json missing → 503."""
    with patch("backend.app.main.load_post", side_effect=FileNotFoundError("POST.json")):
        resp = await client.post(
            "/simulate/match",
            json={"home": "Argentina", "away": "Jordan"},
        )
    assert resp.status_code == 503


@pytest.mark.anyio
async def test_simulate_modal_file_not_found(client: AsyncClient) -> None:
    """POST /simulate/modal when POST.json missing → 503."""
    with patch("backend.app.main.load_post", side_effect=FileNotFoundError("POST.json")):
        resp = await client.post(
            "/simulate/modal",
            json={"home": "Argentina", "away": "Jordan"},
        )
    assert resp.status_code == 503


@pytest.mark.anyio
async def test_simulate_modal_unknown_team(client: AsyncClient) -> None:
    """POST /simulate/modal with unknown team → 400 UNKNOWN_TEAM."""
    resp = await client.post(
        "/simulate/modal",
        json={"home": "Atlantis", "away": "Argentina"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "UNKNOWN_TEAM"


@pytest.mark.anyio
async def test_simulate_h2h_file_not_found(client: AsyncClient) -> None:
    """POST /simulate/h2h when POST.json missing → 503."""
    with patch("backend.app.main.load_post", side_effect=FileNotFoundError("POST.json")):
        resp = await client.post(
            "/simulate/h2h",
            json={"home": "Argentina", "away": "Jordan"},
        )
    assert resp.status_code == 503


@pytest.mark.anyio
async def test_simulate_h2h_unknown_team(client: AsyncClient) -> None:
    """POST /simulate/h2h with unknown team → 400 UNKNOWN_TEAM."""
    resp = await client.post(
        "/simulate/h2h",
        json={"home": "Atlantis", "away": "Argentina"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "UNKNOWN_TEAM"


@pytest.mark.anyio
async def test_simulate_match_rho_zero(client: AsyncClient) -> None:
    """POST /simulate/match with rho=0 exercises the independent Poisson branch."""
    resp = await client.post(
        "/simulate/match",
        json={"home": "Argentina", "away": "Jordan", "n_per_draw": 30, "rho": 0.0},
    )
    assert resp.status_code == 200
    data = resp.json()
    total = data["pH"] + data["pD"] + data["pA"]
    assert abs(total - 1.0) < 0.01


# ---------------------------------------------------------------------------
# OSError in write operations → 500
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_put_tourney_state_write_error(client: AsyncClient) -> None:
    """PUT /tourney/state OSError during save → 500."""
    get_resp = await client.get("/tourney/state")
    assert get_resp.status_code == 200
    body = get_resp.json()
    with patch("backend.app.main.save_tourney", side_effect=OSError("disk full")):
        resp = await client.put("/tourney/state", json=body)
    assert resp.status_code == 500


@pytest.mark.anyio
async def test_put_market_odds_write_error(client: AsyncClient) -> None:
    """PUT /market/odds OSError during save → 500."""
    with patch("backend.app.main.save_market", side_effect=OSError("disk full")):
        resp = await client.put("/market/odds", json={"odds": {"A|B": {"h": 200, "a": 180}}})
    assert resp.status_code == 500


@pytest.mark.anyio
async def test_put_r32_result_write_error(client: AsyncClient) -> None:
    """PUT /tourney/r32/{match_id} OSError during save → 500."""
    with patch("backend.app.main.save_r32", side_effect=OSError("disk full")):
        resp = await client.put("/tourney/r32/73", json={"score_h": 1, "score_a": 0})
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /market/odds — FileNotFoundError and malformed key
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_market_odds_file_not_found(client: AsyncClient) -> None:
    """GET /market/odds when market.json missing → 503."""
    with patch("backend.app.main.load_market", side_effect=FileNotFoundError("market.json")):
        resp = await client.get("/market/odds")
    assert resp.status_code == 503


@pytest.mark.anyio
async def test_market_odds_malformed_key(client: AsyncClient) -> None:
    """GET /market/odds skips entries whose key has no | separator."""
    with patch(
        "backend.app.main.load_market",
        return_value={"INVALID_KEY": {"h": 200, "d": 300, "a": 180}},
    ):
        resp = await client.get("/market/odds")
    assert resp.status_code == 200
    assert resp.json()["odds"] == []


# ---------------------------------------------------------------------------
# GET /tourney/r32 — fallback bracket and unknown team in static bracket
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_get_r32_fallback_computed_bracket(client: AsyncClient) -> None:
    """GET /tourney/r32 without static bracket falls back to _derive_r32_bracket()."""
    with patch("backend.app.main.load_r32_bracket", return_value=None):
        resp = await client.get("/tourney/r32")
    assert resp.status_code == 200
    matches = resp.json()["matches"]
    assert len(matches) == 16
    for m in matches:
        assert "pH" in m and "pD" in m and "pA" in m


@pytest.mark.anyio
async def test_get_r32_fallback_assign_thirds_none(client: AsyncClient) -> None:
    """GET /tourney/r32 with assign_thirds returning None exercises t_slot/slot_label fallback."""
    with (
        patch("backend.app.main.load_r32_bracket", return_value=None),
        patch("backend.app.main.assign_thirds", return_value=None),
    ):
        resp = await client.get("/tourney/r32")
    assert resp.status_code == 200
    matches = resp.json()["matches"]
    assert len(matches) == 16
    for m in matches:
        assert "pH" in m and "pD" in m and "pA" in m


@pytest.mark.anyio
async def test_get_r32_fallback_unknown_team_in_bracket(client: AsyncClient) -> None:
    """GET /tourney/r32: group winner unknown in post → pH/pD/pA=0.0 (main.py line 789)."""
    import copy

    from backend.app.model.store import load_tourney

    base = load_tourney()
    fake = copy.deepcopy(base)
    # Replace group-A index-0 member with "Ghost FC" (not in post["teams"])
    # Give Ghost FC 9 pts so it wins the group → wn["A"] = "Ghost FC"
    fake["groups"]["A"][0] = "Ghost FC"
    fake["state"]["Ghost FC"] = {"pts": 9, "gf": 10, "ga": 0, "gd": 10, "g": "A"}

    with (
        patch("backend.app.main.load_r32_bracket", return_value=None),
        patch("backend.app.main.load_tourney", return_value=fake),
    ):
        resp = await client.get("/tourney/r32")

    assert resp.status_code == 200
    matches = resp.json()["matches"]
    # Match 79 uses wn["A"] (= Ghost FC) — not in model → zeroed probabilities
    match_79 = next((m for m in matches if m["id"] == 79), None)
    assert match_79 is not None
    assert match_79["pH"] == 0.0 and match_79["pD"] == 0.0 and match_79["pA"] == 0.0


@pytest.mark.anyio
async def test_get_r32_static_bracket_unknown_team(client: AsyncClient) -> None:
    """GET /tourney/r32 static bracket with unknown team → pH/pD/pA all 0.0."""
    fake_bracket = [
        {
            "id": 73,
            "home": "UNKNOWN_TEAM_X",
            "home_slot": "2B",
            "away": "UNKNOWN_TEAM_Y",
            "away_slot": "2A",
        }
    ]
    with patch("backend.app.main.load_r32_bracket", return_value=fake_bracket):
        resp = await client.get("/tourney/r32")
    assert resp.status_code == 200
    m = resp.json()["matches"][0]
    assert m["pH"] == 0.0 and m["pD"] == 0.0 and m["pA"] == 0.0


# ---------------------------------------------------------------------------
# _h2h_ci unit test — line 279 (p_h < 1e-8 early continue)
# ---------------------------------------------------------------------------


def test_h2h_ci_low_lambda_triggers_continue() -> None:
    """_h2h_ci with near-zero lambda hits the p_h < 1e-8 early continue (main.py 279).

    With base=-5, att=-5 → lh = exp(-10) ≈ 4.5e-5.
    For h_g >= 2: p_h ≈ 1e-9 < 1e-8, so the continue branch executes.
    """
    from backend.app.main import _h2h_ci

    n_draws = 3
    post_tiny = {
        "teams": ["WeakTeam", "StrongTeam"],
        "att": [[-5.0] * n_draws, [0.0] * n_draws],
        "deff": [[0.0] * n_draws, [0.0] * n_draws],
        "base": [-5.0] * n_draws,
        "home_adv": [0.0] * n_draws,
    }
    ph, pd, pa, ci_lo, ci_med, ci_hi = _h2h_ci(0, 1, post_tiny, 0.0)
    assert abs(ph + pd + pa - 1.0) < 1e-6
