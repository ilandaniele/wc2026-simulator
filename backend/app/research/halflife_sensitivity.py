"""Research script: half-life sensitivity analysis (2y vs 3y vs 5y).

Retrains the model three times with different temporal decay half-lives and
compares tournament champion probabilities.

Usage:
    python -m backend.app.research.halflife_sensitivity

Environment variables:
    RESEARCH_MOCK_DATA=1  — skip network downloads; use data/POST.json for
                            all three half-lives (for CI / unit tests)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from backend.app.model.store import load_post, load_tourney
from backend.app.simulation.engine import run_tournament

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT: Path = Path(__file__).resolve().parents[3]
_RESEARCH_DIR: Path = _REPO_ROOT / "research"

# ---------------------------------------------------------------------------
# Half-lives to compare
# ---------------------------------------------------------------------------

HALF_LIVES: list[float] = [2.0, 3.0, 5.0]
HALF_LIFE_KEYS: list[str] = ["2y", "3y", "5y"]

_N_DRAWS_RESEARCH = 200
_N_SIM = 1000
_SEED = 42
_TOP10 = 10


# ---------------------------------------------------------------------------
# Post loader with mock support
# ---------------------------------------------------------------------------

def _load_post_for_hl(half_life: float, mock: bool) -> dict[str, Any]:
    """Load or retrain posterior for the given half-life.

    In mock mode (RESEARCH_MOCK_DATA=1): always use data/POST.json.
    In live mode: call retrain() which downloads data and fits the model.
    """
    if mock:
        return load_post("current")

    # Live: import here to avoid eager import (slow network call on import)
    from backend.app.model.trainer import retrain  # noqa: PLC0415
    retrain(half_life=half_life, n_draws=_N_DRAWS_RESEARCH)
    return load_post("current")


# ---------------------------------------------------------------------------
# Main research function
# ---------------------------------------------------------------------------

def run_halflife_research(mock: bool = False) -> dict[str, Any]:
    """Run half-life sensitivity analysis.

    Parameters
    ----------
    mock:
        If True, skip network calls and use the current data/POST.json for
        all three half-lives.  Intended for tests and CI.

    Returns
    -------
    dict with keys "2y", "3y", "5y".  Each value is:
        ``top10``: list of top-10 team names by champion probability
        ``champ``: dict {team: champ_probability} for all 48 teams
        ``strength_top15``: list of top-15 teams by mean att+def strength
    """
    tourney_state = load_tourney()
    n_teams = 48  # 48 teams in WC2026
    adja = np.zeros(n_teams, dtype=np.float64)
    adjd = np.zeros(n_teams, dtype=np.float64)

    results: dict[str, Any] = {}

    for hl, key in zip(HALF_LIVES, HALF_LIFE_KEYS, strict=True):
        print(f"\n--- half_life={hl}y ---")  # crew-debug-ok
        if mock:
            print("  [MOCK] Using data/POST.json (no network call)")  # crew-debug-ok
        else:
            print(f"  Retraining model (half_life={hl}, n_draws={_N_DRAWS_RESEARCH})...")  # crew-debug-ok

        post = _load_post_for_hl(hl, mock)
        teams: list[str] = post["teams"]

        print(f"  Running tournament simulation (n={_N_SIM}, seed={_SEED})...")  # crew-debug-ok
        tally = run_tournament(
            n=_N_SIM,
            post=post,
            tourney_state=tourney_state,
            adja=adja,
            adjd=adjd,
            rho=0.05,
            seed=_SEED,
        )

        champ_dict: dict[str, float] = {
            t: round(tally[t]["champ"] / _N_SIM, 6) for t in teams
        }

        # Top-10 by champion probability
        top10 = sorted(champ_dict, key=lambda t: champ_dict[t], reverse=True)[:_TOP10]

        # Strength ranking: mean att + def across all draws
        att_arr = np.array(post["att"])   # n_teams x n_draws
        def_arr = np.array(post["deff"])
        scores = att_arr.mean(axis=1) + def_arr.mean(axis=1)
        order = np.argsort(-scores)
        strength_top15 = [teams[i] for i in order[:15]]

        results[key] = {
            "half_life": hl,
            "top10": top10,
            "champ": champ_dict,
            "strength_top15": strength_top15,
        }

    return results


def _print_comparison(results: dict[str, Any]) -> None:
    """Print a side-by-side comparison table."""
    print("\n\nHalf-Life Sensitivity — Champion Probability Comparison")  # crew-debug-ok
    print("=" * 70)  # crew-debug-ok

    col_w = 20
    header = "Rank  " + "".join(f"{'HL=' + k:>{col_w}}" for k in HALF_LIFE_KEYS)
    print(header)  # crew-debug-ok
    print("-" * len(header))  # crew-debug-ok

    for rank in range(_TOP10):
        row = f"{rank + 1:>4}  "
        for key in HALF_LIFE_KEYS:
            top10 = results[key]["top10"]
            team = top10[rank] if rank < len(top10) else ""
            champ = results[key]["champ"].get(team, 0.0)
            cell = f"{team} ({champ:.2%})"
            row += f"{cell:>{col_w}}"
        print(row)  # crew-debug-ok

    print("-" * len(header))  # crew-debug-ok
    print("\nFinding: shorter half-lives weight recent form more heavily,")  # crew-debug-ok
    print("shifting probability toward in-form teams at the expense of")  # crew-debug-ok
    print("historically dominant sides. Convergence can be assessed by")  # crew-debug-ok
    print("comparing the champion dicts across the three half-lives.")  # crew-debug-ok


def _write_md(results: dict[str, Any]) -> None:
    """Write research/halflife_sensitivity.md."""
    _RESEARCH_DIR.mkdir(exist_ok=True)
    lines: list[str] = [
        "# Half-Life Sensitivity Analysis",
        "",
        "How does the temporal decay half-life (2y / 3y / 5y) affect "
        "the tournament champion probabilities?",
        "",
    ]

    for key in HALF_LIFE_KEYS:
        hl = results[key]["half_life"]
        top10 = results[key]["top10"]
        champ = results[key]["champ"]
        lines.append(f"## Half-life = {hl}y")
        lines.append("")
        lines.append("| Rank | Team | Champion % |")
        lines.append("|---|---|---|")
        for rank, team in enumerate(top10, 1):
            lines.append(f"| {rank} | {team} | {champ[team]:.2%} |")
        lines.append("")

    lines += [
        "## Discussion",
        "",
        "- **2y half-life**: weights only the most recent ~2 years, making "
        "current form the dominant signal. Teams on hot streaks benefit most.",
        "- **3y half-life** (default): balances recent form with sustained "
        "excellence over a World Cup cycle.",
        "- **5y half-life**: longer memory, smoothing out short-term variance "
        "and favouring consistently strong nations.",
        "",
        "Convergence test: if top-3 is stable across all three half-lives, "
        "the ranking is robust to the decay assumption.",
        "",
    ]

    md_path = _RESEARCH_DIR / "halflife_sensitivity.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {md_path}")  # crew-debug-ok


def main() -> None:
    """Entry point — run research and write outputs."""
    mock = os.environ.get("RESEARCH_MOCK_DATA", "0") == "1"
    if mock:
        print("[RESEARCH_MOCK_DATA=1] Skipping network downloads.")  # crew-debug-ok

    results = run_halflife_research(mock=mock)
    _print_comparison(results)

    _RESEARCH_DIR.mkdir(exist_ok=True)
    out_path = _RESEARCH_DIR / "halflife_sensitivity.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {out_path}")  # crew-debug-ok

    _write_md(results)


if __name__ == "__main__":
    main()
