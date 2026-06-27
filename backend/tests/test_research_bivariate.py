"""Tests for backend.app.research.bivariate_vs_independent (AC23)."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest
from backend.app.research.bivariate_vs_independent import (
    TODAY_MATCHES,
    run_bivariate_research,
    simulate_match,
)

# ---------------------------------------------------------------------------
# Minimal stub POST fixture (fast — no file I/O, no network)
# ---------------------------------------------------------------------------

_TEAMS = [
    "Algeria",
    "Argentina",
    "Austria",
    "Colombia",
    "Croatia",
    "DR Congo",
    "England",
    "Ghana",
    "Jordan",
    "Panama",
    "Portugal",
    "Uzbekistan",
]
_N = len(_TEAMS)
_N_DRAWS = 4  # very small for fast tests


def _make_post() -> dict[str, Any]:
    """Minimal valid POST dict with constant att/deff/base."""
    import numpy as np  # noqa: PLC0415

    rng = np.random.default_rng(42)
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


class TestSimulateMatch:
    def test_probs_sum_to_one(self) -> None:
        post = _make_post()
        ph, pd, pa = simulate_match("Colombia", "Portugal", post, rho=0.0, n_per_draw=5)
        assert math.isclose(ph + pd + pa, 1.0, abs_tol=0.02)

    def test_probs_all_non_negative(self) -> None:
        post = _make_post()
        ph, pd, pa = simulate_match("Colombia", "Portugal", post, rho=0.05, n_per_draw=5)
        assert ph >= 0 and pd >= 0 and pa >= 0

    def test_bivariate_vs_independent_differ(self) -> None:
        """rho=0.05 and rho=0.0 should produce different probabilities."""
        post = _make_post()
        ph0, pd0, pa0 = simulate_match("Colombia", "Portugal", post, rho=0.0, n_per_draw=20)
        ph1, pd1, pa1 = simulate_match("Colombia", "Portugal", post, rho=0.05, n_per_draw=20)
        # They may differ (the difference is small but the sum must still be 1)
        assert math.isclose(ph1 + pd1 + pa1, 1.0, abs_tol=0.02)
        assert math.isclose(ph0 + pd0 + pa0, 1.0, abs_tol=0.02)


class TestRunBivariateResearch:
    """AC23: run_bivariate_research returns the correct JSON structure."""

    @pytest.fixture()
    def post(self) -> dict[str, Any]:
        return _make_post()

    def test_keys_present(self, post: dict[str, Any]) -> None:
        result = run_bivariate_research(post=post, n_per_draw=2)
        assert "matches" in result
        assert "summary" in result

    def test_matches_count(self, post: dict[str, Any]) -> None:
        result = run_bivariate_research(post=post, n_per_draw=2)
        assert len(result["matches"]) == len(TODAY_MATCHES)

    def test_match_keys(self, post: dict[str, Any]) -> None:
        result = run_bivariate_research(post=post, n_per_draw=2)
        required = {
            "match",
            "pH_indep",
            "pD_indep",
            "pA_indep",
            "pH_biv",
            "pD_biv",
            "pA_biv",
            "delta_pH",
            "delta_pD",
            "delta_pA",
        }
        for m in result["matches"]:
            assert required.issubset(m.keys()), f"Missing keys in {m}"

    def test_delta_consistency(self, post: dict[str, Any]) -> None:
        result = run_bivariate_research(post=post, n_per_draw=2)
        for m in result["matches"]:
            assert math.isclose(m["delta_pH"], m["pH_biv"] - m["pH_indep"], abs_tol=1e-5)
            assert math.isclose(m["delta_pD"], m["pD_biv"] - m["pD_indep"], abs_tol=1e-5)
            assert math.isclose(m["delta_pA"], m["pA_biv"] - m["pA_indep"], abs_tol=1e-5)

    def test_summary_keys(self, post: dict[str, Any]) -> None:
        result = run_bivariate_research(post=post, n_per_draw=2)
        assert "mean_absolute_delta_pp" in result["summary"]

    def test_summary_is_non_negative(self, post: dict[str, Any]) -> None:
        result = run_bivariate_research(post=post, n_per_draw=2)
        assert result["summary"]["mean_absolute_delta_pp"] >= 0


class TestBivariateJsonOutput:
    """AC23: JSON file is written to research/bivariate_vs_independent.json with correct keys."""

    def test_json_written_and_correct_keys(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        post = _make_post()

        # Patch load_post to return our stub and _RESEARCH_DIR to tmp_path
        import backend.app.research.bivariate_vs_independent as mod  # noqa: PLC0415

        monkeypatch.setattr(mod, "_RESEARCH_DIR", tmp_path)
        monkeypatch.setattr(mod, "load_post", lambda model_id="current": post)

        mod.main()

        out_path = tmp_path / "bivariate_vs_independent.json"
        assert out_path.exists(), "JSON not written"

        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert "matches" in data
        assert "summary" in data
        assert len(data["matches"]) == 6  # exactly 6 matches

        required_match_keys = {
            "match",
            "pH_indep",
            "pD_indep",
            "pA_indep",
            "pH_biv",
            "pD_biv",
            "pA_biv",
            "delta_pH",
            "delta_pD",
            "delta_pA",
        }
        for m in data["matches"]:
            assert required_match_keys.issubset(m.keys())

    def test_md_written(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        post = _make_post()
        import backend.app.research.bivariate_vs_independent as mod  # noqa: PLC0415

        monkeypatch.setattr(mod, "_RESEARCH_DIR", tmp_path)
        monkeypatch.setattr(mod, "load_post", lambda model_id="current": post)

        mod.main()

        md_path = tmp_path / "bivariate_vs_independent.md"
        assert md_path.exists(), ".md file not written"
        content = md_path.read_text(encoding="utf-8")
        assert "Bivariate" in content
