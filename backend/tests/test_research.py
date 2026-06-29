"""Unit tests for backend/app/research/* — covers uncovered branches.

All tests mock I/O (network, disk writes) and use fixture POST data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from backend.app.model.store import load_post, load_tourney

# ---------------------------------------------------------------------------
# Shared fixture data
# ---------------------------------------------------------------------------


@pytest.fixture
def post() -> dict[str, Any]:
    return load_post()


@pytest.fixture
def tourney() -> dict[str, Any]:
    return load_tourney()


# Market data keyed by MARKET_KEYS — odds set so all edges are negative (no +EV)
_HIGH_VIG_MARKET: dict[str, dict[str, int]] = {
    "Algeria|Austria": {"h": -300, "d": 240, "a": 450},
    "Jordan|Argentina": {"h": 450, "d": 240, "a": -300},
    "Colombia|Portugal": {"h": 200, "d": 250, "a": -180},
    "DR Congo|Uzbekistan": {"h": -200, "d": 280, "a": 300},
    "Panama|England": {"h": 400, "d": 280, "a": -250},
    "Croatia|Ghana": {"h": -180, "d": 290, "a": 350},
}


# ---------------------------------------------------------------------------
# bivariate_vs_independent.py
# ---------------------------------------------------------------------------


def test_run_bivariate_with_post_provided(post: dict[str, Any]) -> None:
    """run_bivariate_research with explicit post skips load_post (post path)."""
    from backend.app.research.bivariate_vs_independent import run_bivariate_research

    result = run_bivariate_research(post=post, n_per_draw=10)
    assert "matches" in result
    assert len(result["matches"]) == 6
    assert "summary" in result


def test_run_bivariate_post_none_loads_from_store(post: dict[str, Any]) -> None:
    """run_bivariate_research(post=None) calls load_post — covers line 120."""
    from backend.app.research.bivariate_vs_independent import run_bivariate_research

    with patch(
        "backend.app.research.bivariate_vs_independent.load_post",
        return_value=post,
    ):
        result = run_bivariate_research(post=None, n_per_draw=5)

    assert "matches" in result


# ---------------------------------------------------------------------------
# halflife_sensitivity.py
# ---------------------------------------------------------------------------


def test_load_post_for_hl_mock_mode(post: dict[str, Any]) -> None:
    """_load_post_for_hl with mock=True calls load_post directly."""
    from backend.app.research.halflife_sensitivity import _load_post_for_hl

    with patch(
        "backend.app.research.halflife_sensitivity.load_post",
        return_value=post,
    ):
        result = _load_post_for_hl(3.0, mock=True)

    assert "teams" in result


def test_load_post_for_hl_live_mode(post: dict[str, Any]) -> None:
    """_load_post_for_hl with mock=False mocks retrain — covers lines 60-63."""
    from backend.app.research.halflife_sensitivity import _load_post_for_hl

    with (
        patch("backend.app.model.trainer.retrain"),
        patch(
            "backend.app.research.halflife_sensitivity.load_post",
            return_value=post,
        ),
    ):
        result = _load_post_for_hl(2.0, mock=False)

    assert "teams" in result


def test_run_halflife_research_mock(post: dict[str, Any], tourney: dict[str, Any]) -> None:
    """run_halflife_research(mock=True) returns results for all three half-lives."""
    from backend.app.research.halflife_sensitivity import run_halflife_research

    with (
        patch(
            "backend.app.research.halflife_sensitivity.load_tourney",
            return_value=tourney,
        ),
        patch(
            "backend.app.research.halflife_sensitivity._load_post_for_hl",
            return_value=post,
        ),
    ):
        result = run_halflife_research(mock=True)

    assert "2y" in result and "3y" in result and "5y" in result


def test_run_halflife_research_live_prints_retrain(
    post: dict[str, Any], tourney: dict[str, Any]
) -> None:
    """run_halflife_research(mock=False) covers the non-mock print branch (line 99)."""
    from backend.app.research.halflife_sensitivity import run_halflife_research

    with (
        patch(
            "backend.app.research.halflife_sensitivity.load_tourney",
            return_value=tourney,
        ),
        patch(
            "backend.app.research.halflife_sensitivity._load_post_for_hl",
            return_value=post,
        ),
    ):
        result = run_halflife_research(mock=False)

    assert "2y" in result


# ---------------------------------------------------------------------------
# market_edge_today.py
# ---------------------------------------------------------------------------


def test_devig_zero_total() -> None:
    """_devig with total=0 returns equal thirds — covers line 119."""
    from backend.app.research.market_edge_today import _devig

    ph, pd, pa = _devig(0.0, 0.0, 0.0)
    assert abs(ph - 1 / 3) < 1e-9
    assert abs(pd - 1 / 3) < 1e-9
    assert abs(pa - 1 / 3) < 1e-9


def test_simulate_match_rho_zero(post: dict[str, Any]) -> None:
    """simulate_match with rho=0 exercises the independent Poisson branch (lines 102-103)."""
    from backend.app.research.market_edge_today import simulate_match

    ph, pd, pa = simulate_match("Algeria", "Austria", post, rho=0.0, n_per_draw=20)
    assert abs(ph + pd + pa - 1.0) < 1e-6


def test_run_market_edge_post_none(post: dict[str, Any]) -> None:
    """run_market_edge_research with post=None loads post from store — covers line 152."""
    from backend.app.research.market_edge_today import run_market_edge_research

    with patch(
        "backend.app.research.market_edge_today.load_post",
        return_value=post,
    ):
        entries = run_market_edge_research(post=None, market=_HIGH_VIG_MARKET, n_per_draw=5)

    assert len(entries) == 6


def test_run_market_edge_market_none(post: dict[str, Any]) -> None:
    """run_market_edge_research with market=None loads market from store — covers line 154."""
    from backend.app.research.market_edge_today import run_market_edge_research

    with patch(
        "backend.app.research.market_edge_today.load_market",
        return_value=_HIGH_VIG_MARKET,
    ):
        entries = run_market_edge_research(post=post, market=None, n_per_draw=5)

    assert len(entries) == 6


def test_write_md_no_ev_bets(tmp_path: Path) -> None:
    """_write_md with all no_value entries covers the else branch (line 287)."""
    from backend.app.research.market_edge_today import _write_md

    entries = [
        {
            "match": "Algeria vs Austria",
            "model_pH": 0.30,
            "model_pD": 0.35,
            "model_pA": 0.35,
            "market_pH": 0.40,
            "market_pD": 0.33,
            "market_pA": 0.27,
            "edge_H_pp": -10.0,
            "edge_D_pp": 2.0,
            "edge_A_pp": 8.0,
            "recommended": "no_value",
        }
    ]

    with patch("backend.app.research.market_edge_today._RESEARCH_DIR", tmp_path):
        _write_md(entries)

    md = (tmp_path / "market_edge_today.md").read_text(encoding="utf-8")
    assert "No +EV bets identified today." in md
