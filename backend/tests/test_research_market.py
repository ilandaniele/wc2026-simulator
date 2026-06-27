"""Tests for backend.app.research.market_edge_today (AC25)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from backend.app.research.market_edge_today import (
    TODAY_MATCHES,
    am2prob,
    run_market_edge_research,
    simulate_match,
)

# ---------------------------------------------------------------------------
# Stub fixtures
# ---------------------------------------------------------------------------

_TEAMS = [
    "Algeria", "Argentina", "Austria", "Colombia", "Croatia",
    "DR Congo", "England", "Ghana", "Jordan", "Panama",
    "Portugal", "Uzbekistan",
]
_N = len(_TEAMS)
_N_DRAWS = 4

_MARKET: dict[str, Any] = {
    "Algeria|Austria": {"h": 350, "d": 260, "a": -140},
    "Jordan|Argentina": {"h": 3500, "d": 1400, "a": -2000},
    "Colombia|Portugal": {"h": 250, "d": 300, "a": 115},
    "DR Congo|Uzbekistan": {"h": -125, "d": 260, "a": 340},
    "Panama|England": {"h": 2000, "d": 800, "a": -900},
    "Croatia|Ghana": {"h": -165, "d": 300, "a": 500},
}


def _make_post() -> dict[str, Any]:
    import numpy as np  # noqa: PLC0415

    rng = np.random.default_rng(7)
    return {
        "teams": _TEAMS,
        "att": [[round(float(v), 4) for v in rng.normal(0, 0.3, _N_DRAWS)] for _ in range(_N)],
        "deff": [[round(float(v), 4) for v in rng.normal(0, 0.3, _N_DRAWS)] for _ in range(_N)],
        "base": [round(float(v), 4) for v in rng.normal(0.2, 0.05, _N_DRAWS)],
        "home_adv": [round(float(v), 4) for v in rng.normal(0.15, 0.05, _N_DRAWS)],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAm2Prob:
    def test_negative_american(self) -> None:
        # -110 → 110/210 ≈ 0.5238
        assert math.isclose(am2prob(-110), 110 / 210, rel_tol=1e-6)

    def test_positive_american(self) -> None:
        # +200 → 100/300 ≈ 0.3333
        assert math.isclose(am2prob(200), 100 / 300, rel_tol=1e-6)

    def test_none_returns_zero(self) -> None:
        assert am2prob(None) == 0.0

    def test_plus_100_equals_half(self) -> None:
        assert math.isclose(am2prob(100), 0.5, rel_tol=1e-6)

    def test_minus_100_equals_half(self) -> None:
        assert math.isclose(am2prob(-100), 0.5, rel_tol=1e-6)


class TestSimulateMatchMarket:
    def test_probs_sum_to_one(self) -> None:
        post = _make_post()
        ph, pd, pa = simulate_match("Colombia", "Portugal", post, rho=0.05, n_per_draw=5)
        assert math.isclose(ph + pd + pa, 1.0, abs_tol=0.02)

    def test_probs_non_negative(self) -> None:
        post = _make_post()
        ph, pd, pa = simulate_match("Colombia", "Portugal", post, rho=0.05, n_per_draw=5)
        assert ph >= 0 and pd >= 0 and pa >= 0


class TestRunMarketEdge:
    """AC25: run_market_edge_research returns 6 entries with all required fields."""

    @pytest.fixture()
    def entries(self) -> list[dict[str, Any]]:
        post = _make_post()
        return run_market_edge_research(post=post, market=_MARKET, n_per_draw=2)

    def test_six_entries(self, entries: list[dict[str, Any]]) -> None:
        assert len(entries) == 6

    def test_required_fields(self, entries: list[dict[str, Any]]) -> None:
        required = {
            "match",
            "model_pH", "model_pD", "model_pA",
            "market_pH", "market_pD", "market_pA",
            "edge_H_pp", "edge_D_pp", "edge_A_pp",
            "recommended",
        }
        for e in entries:
            assert required.issubset(e.keys()), f"Missing keys: {required - e.keys()}"

    def test_match_names(self, entries: list[dict[str, Any]]) -> None:
        expected = [f"{h} vs {a}" for h, a in TODAY_MATCHES]
        actual = [e["match"] for e in entries]
        assert actual == expected

    def test_model_probs_sum_to_one(self, entries: list[dict[str, Any]]) -> None:
        for e in entries:
            total = e["model_pH"] + e["model_pD"] + e["model_pA"]
            assert math.isclose(total, 1.0, abs_tol=0.02), \
                f"{e['match']}: model probs sum to {total}"

    def test_market_probs_sum_to_one(self, entries: list[dict[str, Any]]) -> None:
        for e in entries:
            total = e["market_pH"] + e["market_pD"] + e["market_pA"]
            assert math.isclose(total, 1.0, abs_tol=0.02), \
                f"{e['match']}: market probs sum to {total}"

    def test_edge_consistency(self, entries: list[dict[str, Any]]) -> None:
        for e in entries:
            assert math.isclose(
                e["edge_H_pp"], (e["model_pH"] - e["market_pH"]) * 100, abs_tol=0.1
            )
            assert math.isclose(
                e["edge_A_pp"], (e["model_pA"] - e["market_pA"]) * 100, abs_tol=0.1
            )

    def test_recommended_is_valid(self, entries: list[dict[str, Any]]) -> None:
        valid = {"H", "D", "A", "no_value"}
        for e in entries:
            assert e["recommended"] in valid, \
                f"Invalid recommended: {e['recommended']}"

    def test_no_value_when_all_negative(self, entries: list[dict[str, Any]]) -> None:
        """If all edges are negative the recommended must be 'no_value'."""
        for e in entries:
            edges = [e["edge_H_pp"], e["edge_D_pp"], e["edge_A_pp"]]
            if all(v <= 0 for v in edges):
                assert e["recommended"] == "no_value"


class TestMarketEdgeJsonOutput:
    """AC25: JSON file is written to research/market_edge_today.json."""

    def test_json_written_and_correct_structure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        post = _make_post()
        import backend.app.research.market_edge_today as mod  # noqa: PLC0415

        monkeypatch.setattr(mod, "_RESEARCH_DIR", tmp_path)
        monkeypatch.setattr(mod, "load_post", lambda model_id="current": post)
        monkeypatch.setattr(mod, "load_market", lambda: _MARKET)

        mod.main()

        out_path = tmp_path / "market_edge_today.json"
        assert out_path.exists(), "JSON not written"

        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == 6

        required = {
            "match", "model_pH", "model_pD", "model_pA",
            "market_pH", "market_pD", "market_pA",
            "edge_H_pp", "edge_D_pp", "edge_A_pp", "recommended",
        }
        for entry in data:
            assert required.issubset(entry.keys())

    def test_md_written(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        post = _make_post()
        import backend.app.research.market_edge_today as mod  # noqa: PLC0415

        monkeypatch.setattr(mod, "_RESEARCH_DIR", tmp_path)
        monkeypatch.setattr(mod, "load_post", lambda model_id="current": post)
        monkeypatch.setattr(mod, "load_market", lambda: _MARKET)

        mod.main()

        md_path = tmp_path / "market_edge_today.md"
        assert md_path.exists(), ".md file not written"
        content = md_path.read_text(encoding="utf-8")
        assert "Market Edge" in content
