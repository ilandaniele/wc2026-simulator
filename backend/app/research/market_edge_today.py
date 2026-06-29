"""Research script: model vs bookmaker market edge for today's 6 matches.

Computes expected value (EV) edge for each outcome in today's 6 Group J/K/L
matches and writes the analysis to research/market_edge_today.json.

Usage:
    python -m backend.app.research.market_edge_today
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from backend.app.model.store import load_market, load_post
from backend.app.simulation.engine import lams, mul, pois

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT: Path = Path(__file__).resolve().parents[3]
_RESEARCH_DIR: Path = _REPO_ROOT / "research"

# ---------------------------------------------------------------------------
# Match order (must match market.json key order)
# ---------------------------------------------------------------------------

TODAY_MATCHES: list[tuple[str, str]] = [
    ("Algeria", "Austria"),
    ("Jordan", "Argentina"),
    ("Colombia", "Portugal"),
    ("DR Congo", "Uzbekistan"),
    ("Panama", "England"),
    ("Croatia", "Ghana"),
]

MARKET_KEYS: list[str] = [
    "Algeria|Austria",
    "Jordan|Argentina",
    "Colombia|Portugal",
    "DR Congo|Uzbekistan",
    "Panama|England",
    "Croatia|Ghana",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def am2prob(american: int | None) -> float:
    """Convert an American odds value to implied probability.

    Returns 0.0 for None (draw not offered in some markets).
    """
    if american is None:
        return 0.0
    if american < 0:
        return (-american) / (-american + 100)
    return 100 / (american + 100)


def simulate_match(
    home: str,
    away: str,
    post: dict[str, Any],
    rho: float,
    n_per_draw: int,
) -> tuple[float, float, float]:
    """Monte Carlo match probabilities via full draw loop.

    Returns (pH, pD, pA) for home win / draw / away win.
    """
    teams: list[str] = post["teams"]
    ti: dict[str, int] = {t: i for i, t in enumerate(teams)}

    hi = ti[home]
    ai = ti[away]
    n_draws = len(post["base"])

    adja = np.zeros(len(teams), dtype=np.float64)
    adjd = np.zeros(len(teams), dtype=np.float64)

    wins_h = 0
    draws_ct = 0
    wins_a = 0
    rng = mul(0xC0FFEE)

    for d in range(n_draws):
        lh, la = lams(hi, ai, d, post, adja, adjd)
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
                draws_ct += 1

    total = n_draws * n_per_draw
    return wins_h / total, draws_ct / total, wins_a / total


def _devig(raw_h: float, raw_d: float, raw_a: float) -> tuple[float, float, float]:
    """Remove bookmaker margin (vig) by normalising to 1.0."""
    total = raw_h + raw_d + raw_a
    if total <= 0:
        return 1 / 3, 1 / 3, 1 / 3
    return raw_h / total, raw_d / total, raw_a / total


# ---------------------------------------------------------------------------
# Main research function
# ---------------------------------------------------------------------------


def run_market_edge_research(
    post: dict[str, Any] | None = None,
    market: dict[str, Any] | None = None,
    n_per_draw: int = 50,
) -> list[dict[str, Any]]:
    """Compute model vs market edge for today's 6 matches.

    Parameters
    ----------
    post:
        Pre-loaded POST dict.  If None, loads from data/POST.json.
    market:
        Pre-loaded market dict.  If None, loads from data/market.json.
    n_per_draw:
        Simulations per posterior draw.

    Returns
    -------
    List of 6 entry dicts, one per match, with keys:
        match, model_pH, model_pD, model_pA,
        market_pH, market_pD, market_pA,
        edge_H_pp, edge_D_pp, edge_A_pp, recommended
    """
    if post is None:
        post = load_post("current")
    if market is None:
        market = load_market()

    entries: list[dict[str, Any]] = []

    for (home, away), mkey in zip(TODAY_MATCHES, MARKET_KEYS, strict=True):
        # Model probabilities
        model_ph, model_pd, model_pa = simulate_match(
            home, away, post, rho=0.05, n_per_draw=n_per_draw
        )

        # Market de-vigged probabilities
        odds = market[mkey]
        raw_h = am2prob(odds.get("h"))
        raw_d = am2prob(odds.get("d"))
        raw_a = am2prob(odds.get("a"))
        mkt_ph, mkt_pd, mkt_pa = _devig(raw_h, raw_d, raw_a)

        # Edge in percentage points (pp)
        edge_h = round((model_ph - mkt_ph) * 100, 2)
        edge_d = round((model_pd - mkt_pd) * 100, 2)
        edge_a = round((model_pa - mkt_pa) * 100, 2)

        # Best +EV outcome (highest positive edge) or "no_value"
        candidates = [
            ("H", edge_h),
            ("D", edge_d),
            ("A", edge_a),
        ]
        best_outcome, best_edge = max(candidates, key=lambda x: x[1])
        recommended = best_outcome if best_edge > 0 else "no_value"

        entries.append(
            {
                "match": f"{home} vs {away}",
                "model_pH": round(model_ph, 6),
                "model_pD": round(model_pd, 6),
                "model_pA": round(model_pa, 6),
                "market_pH": round(mkt_ph, 6),
                "market_pD": round(mkt_pd, 6),
                "market_pA": round(mkt_pa, 6),
                "edge_H_pp": edge_h,
                "edge_D_pp": edge_d,
                "edge_A_pp": edge_a,
                "recommended": recommended,
            }
        )

    return entries


def _print_table(entries: list[dict[str, Any]]) -> None:
    """Print a human-readable edge table."""
    print("\nMarket Edge Analysis — Model vs Bookmaker (today's 6 matches)")  # crew-debug-ok
    print("=" * 100)  # crew-debug-ok
    header = (
        f"{'Match':<30} {'mH':>7} {'mktH':>7} {'edgH':>7}"
        f" {'mD':>7} {'mktD':>7} {'edgD':>7}"
        f" {'mA':>7} {'mktA':>7} {'edgA':>7}"
        f" {'Rec':>8}"
    )
    print(header)  # crew-debug-ok
    print("-" * 100)  # crew-debug-ok

    for e in entries:
        label = e["match"][:29]
        rec = e["recommended"]

        # Flag positive-edge outcomes
        def _fmt_edge(val: float) -> str:
            s = f"{val:+.2f}"
            return f"[{s}]" if val > 0 else f" {s} "

        print(  # crew-debug-ok
            f"{label:<30}"
            f" {e['model_pH']:>7.4f} {e['market_pH']:>7.4f} {_fmt_edge(e['edge_H_pp']):>7}"
            f" {e['model_pD']:>7.4f} {e['market_pD']:>7.4f} {_fmt_edge(e['edge_D_pp']):>7}"
            f" {e['model_pA']:>7.4f} {e['market_pA']:>7.4f} {_fmt_edge(e['edge_A_pp']):>7}"
            f" {rec:>8}"
        )

    print("-" * 100)  # crew-debug-ok
    ev_bets = [e for e in entries if e["recommended"] != "no_value"]
    print(f"\n+EV bets today: {len(ev_bets)}/6 matches")  # crew-debug-ok
    for e in ev_bets:
        rec = e["recommended"]
        edge_key = f"edge_{rec}_pp"
        print(  # crew-debug-ok
            f"  {e['match']}: {rec} side  "
            f"(model {e[f'model_p{rec}']:.2%} vs mkt {e[f'market_p{rec}']:.2%}, "
            f"edge {e[edge_key]:+.2f} pp)"
        )


def _write_md(entries: list[dict[str, Any]]) -> None:
    """Write research/market_edge_today.md."""
    _RESEARCH_DIR.mkdir(exist_ok=True)
    lines: list[str] = [
        "# Market Edge — Today's Matches",
        "",
        "Model probability vs de-vigged bookmaker implied probability for "
        "today's 6 Group J/K/L matches.",
        "",
        "## Edge Table",
        "",
        "| Match | Model H | Mkt H | Edge H | Model D | Mkt D | Edge D | "
        "Model A | Mkt A | Edge A | Rec |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for e in entries:
        lines.append(
            f"| {e['match']}"
            f" | {e['model_pH']:.3f} | {e['market_pH']:.3f} | {e['edge_H_pp']:+.2f} pp"
            f" | {e['model_pD']:.3f} | {e['market_pD']:.3f} | {e['edge_D_pp']:+.2f} pp"
            f" | {e['model_pA']:.3f} | {e['market_pA']:.3f} | {e['edge_A_pp']:+.2f} pp"
            f" | **{e['recommended']}** |"
        )

    ev_bets = [e for e in entries if e["recommended"] != "no_value"]
    lines += [
        "",
        "## +EV Bets",
        "",
    ]
    if ev_bets:
        for e in ev_bets:
            rec = e["recommended"]
            edge_key = f"edge_{rec}_pp"
            lines.append(
                f"- **{e['match']}** — {rec} "
                f"(model {e[f'model_p{rec}']:.1%} vs mkt {e[f'market_p{rec}']:.1%}, "
                f"edge {e[edge_key]:+.1f} pp)"
            )
    else:
        lines.append("No +EV bets identified today.")

    lines += [
        "",
        "## Interpretation",
        "",
        "- **Edge (pp)** = (model probability − market implied probability) × 100.",
        "- Positive edge means the model assigns higher probability than "
        "the bookmaker, suggesting potential value.",
        "- Market implied probabilities are de-vigged (normalised to sum to 1.0).",
        "- Recommended outcome is the one with the highest positive edge, "
        "or 'no_value' if all edges are negative.",
        "",
        "> Note: edges based on 50 simulations per draw may have Monte Carlo noise "
        "of ±0.5 pp. Rerun with higher n_per_draw for tighter estimates.",
        "",
    ]

    md_path = _RESEARCH_DIR / "market_edge_today.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {md_path}")  # crew-debug-ok


def main() -> None:
    """Entry point — run research and write outputs."""
    print("Loading model and market odds...")  # crew-debug-ok
    post = load_post("current")
    market = load_market()
    print(f"Model: {len(post['teams'])} teams, {len(post['base'])} draws.")  # crew-debug-ok
    print(f"Market: {len(market)} matches loaded.")  # crew-debug-ok

    print("Running market edge analysis (n_per_draw=50)...")  # crew-debug-ok
    entries = run_market_edge_research(post=post, market=market, n_per_draw=50)

    _print_table(entries)

    _RESEARCH_DIR.mkdir(exist_ok=True)
    out_path = _RESEARCH_DIR / "market_edge_today.json"
    out_path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {out_path}")  # crew-debug-ok

    _write_md(entries)


if __name__ == "__main__":  # pragma: no cover
    main()
