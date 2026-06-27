"""Tests for backend.app.research.halflife_sensitivity (AC24).

Uses RESEARCH_MOCK_DATA=1 to skip network downloads.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from backend.app.research.halflife_sensitivity import (
    HALF_LIFE_KEYS,
    HALF_LIVES,
    _TOP10,
    run_halflife_research,
)

# ---------------------------------------------------------------------------
# Minimal stub POST fixture
# ---------------------------------------------------------------------------

_TEAMS = [
    "Algeria", "Argentina", "Australia", "Austria", "Belgium",
    "Bosnia and Herzegovina", "Brazil", "Cabo Verde", "Canada", "Colombia",
    "Croatia", "Curaçao", "Czechia", "Côte d'Ivoire", "DR Congo",
    "Ecuador", "Egypt", "England", "France", "Germany", "Ghana", "Haiti",
    "Iran", "Iraq", "Japan", "Jordan", "Mexico", "Morocco", "Netherlands",
    "New Zealand", "Norway", "Panama", "Paraguay", "Portugal", "Qatar",
    "Saudi Arabia", "Scotland", "Senegal", "South Africa", "South Korea",
    "Spain", "Sweden", "Switzerland", "Tunisia", "Türkiye", "USA",
    "Uruguay", "Uzbekistan",
]
_N = len(_TEAMS)
_N_DRAWS = 4


def _make_post() -> dict[str, Any]:
    import numpy as np  # noqa: PLC0415

    rng = np.random.default_rng(0)
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

class TestRunHalflifeResearch:
    """AC24: run_halflife_research returns the correct structure."""

    @pytest.fixture(autouse=True)
    def _patch_data(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Patch data loaders to avoid file I/O / network calls."""
        import backend.app.research.halflife_sensitivity as mod  # noqa: PLC0415
        import backend.app.model.store as store_mod  # noqa: PLC0415

        post = _make_post()

        # load_post always returns our stub
        monkeypatch.setattr(store_mod, "load_post", lambda model_id="current": post)
        monkeypatch.setattr(mod, "load_post", lambda model_id="current": post)

        # load_tourney returns a minimal valid tourney state
        from backend.app.model.store import load_tourney  # noqa: PLC0415

        try:
            tourney = load_tourney()
        except Exception:
            # Fallback: build a minimal tourney from the stub
            groups = {
                "A": _TEAMS[0:4], "B": _TEAMS[4:8], "C": _TEAMS[8:12],
                "D": _TEAMS[12:16], "E": _TEAMS[16:20], "F": _TEAMS[20:24],
                "G": _TEAMS[24:28], "H": _TEAMS[28:32], "I": _TEAMS[32:36],
                "J": _TEAMS[36:40], "K": _TEAMS[40:44], "L": _TEAMS[44:48],
            }
            state = {t: {"pts": 3, "gf": 2, "ga": 1, "gd": 1, "g": g}
                     for g, ts in groups.items() for t in ts}
            tourney = {"state": state, "remaining": [], "groups": groups}

        monkeypatch.setattr(store_mod, "load_tourney", lambda: tourney)
        monkeypatch.setattr(mod, "load_tourney", lambda: tourney)

    def test_has_three_keys(self) -> None:
        result = run_halflife_research(mock=True)
        for key in HALF_LIFE_KEYS:
            assert key in result, f"Missing key: {key}"

    def test_each_key_has_top10(self) -> None:
        result = run_halflife_research(mock=True)
        for key in HALF_LIFE_KEYS:
            assert "top10" in result[key]
            assert isinstance(result[key]["top10"], list)
            assert len(result[key]["top10"]) <= _TOP10

    def test_each_key_has_champ(self) -> None:
        result = run_halflife_research(mock=True)
        for key in HALF_LIFE_KEYS:
            assert "champ" in result[key]
            champ = result[key]["champ"]
            assert isinstance(champ, dict)
            # All 48 teams present
            assert len(champ) == _N

    def test_champ_probs_sum_to_approx_one(self) -> None:
        result = run_halflife_research(mock=True)
        for key in HALF_LIFE_KEYS:
            total = sum(result[key]["champ"].values())
            assert abs(total - 1.0) < 0.02, f"{key} champ probs sum to {total}"

    def test_each_key_has_strength_top15(self) -> None:
        result = run_halflife_research(mock=True)
        for key in HALF_LIFE_KEYS:
            assert "strength_top15" in result[key]
            assert isinstance(result[key]["strength_top15"], list)
            assert len(result[key]["strength_top15"]) == 15

    def test_half_life_values_recorded(self) -> None:
        result = run_halflife_research(mock=True)
        for hl, key in zip(HALF_LIVES, HALF_LIFE_KEYS, strict=True):
            assert result[key]["half_life"] == hl

    def test_top10_teams_in_champ(self) -> None:
        result = run_halflife_research(mock=True)
        for key in HALF_LIFE_KEYS:
            top10 = result[key]["top10"]
            champ = result[key]["champ"]
            for team in top10:
                assert team in champ, f"{team} in top10 but not in champ dict"


class TestHalflifeJsonOutput:
    """AC24: JSON file is written with correct structure."""

    @pytest.fixture(autouse=True)
    def _patch_data(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import backend.app.research.halflife_sensitivity as mod  # noqa: PLC0415
        import backend.app.model.store as store_mod  # noqa: PLC0415

        post = _make_post()
        monkeypatch.setattr(store_mod, "load_post", lambda model_id="current": post)
        monkeypatch.setattr(mod, "load_post", lambda model_id="current": post)

        groups = {
            "A": _TEAMS[0:4], "B": _TEAMS[4:8], "C": _TEAMS[8:12],
            "D": _TEAMS[12:16], "E": _TEAMS[16:20], "F": _TEAMS[20:24],
            "G": _TEAMS[24:28], "H": _TEAMS[28:32], "I": _TEAMS[32:36],
            "J": _TEAMS[36:40], "K": _TEAMS[40:44], "L": _TEAMS[44:48],
        }
        state = {t: {"pts": 3, "gf": 2, "ga": 1, "gd": 1, "g": g}
                 for g, ts in groups.items() for t in ts}
        tourney = {"state": state, "remaining": [], "groups": groups}

        monkeypatch.setattr(store_mod, "load_tourney", lambda: tourney)
        monkeypatch.setattr(mod, "load_tourney", lambda: tourney)

    def test_json_written(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import backend.app.research.halflife_sensitivity as mod  # noqa: PLC0415

        monkeypatch.setattr(mod, "_RESEARCH_DIR", tmp_path)
        monkeypatch.setenv("RESEARCH_MOCK_DATA", "1")

        mod.main()

        out_path = tmp_path / "halflife_sensitivity.json"
        assert out_path.exists(), "JSON not written"

        data = json.loads(out_path.read_text(encoding="utf-8"))
        for key in HALF_LIFE_KEYS:
            assert key in data
            assert "top10" in data[key]
            assert "champ" in data[key]
            assert "strength_top15" in data[key]

    def test_md_written(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import backend.app.research.halflife_sensitivity as mod  # noqa: PLC0415

        monkeypatch.setattr(mod, "_RESEARCH_DIR", tmp_path)
        monkeypatch.setenv("RESEARCH_MOCK_DATA", "1")

        mod.main()

        md_path = tmp_path / "halflife_sensitivity.md"
        assert md_path.exists(), ".md file not written"
        content = md_path.read_text(encoding="utf-8")
        assert "Half-Life" in content
        assert "2y" in content or "2.0" in content
