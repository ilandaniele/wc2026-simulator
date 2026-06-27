"""Monte Carlo simulation engine — Python port of the JS runT() / play() / pois() / mul().

The PRNG replicates JavaScript's Math.imul (32-bit signed integer overflow) using
numpy uint32 arithmetic so that results are numerically identical to the browser.

All functions that consume a PRNG state operate on a *mutable* uint32 held in a
length-1 numpy array so callers share the same state across calls (mirrors JS closure).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from numpy.typing import NDArray

# ---------------------------------------------------------------------------
# Annex C bracket constants (from index.html)
# ---------------------------------------------------------------------------

# For each slot (key = which bracket slot letter), which third-place group letters
# are allowed to fill it.
TALLOW: dict[str, list[str]] = {
    "E": ["A", "B", "C", "D", "F"],
    "I": ["C", "D", "F", "G", "H"],
    "A": ["C", "E", "F", "H", "I"],
    "L": ["E", "H", "I", "J", "K"],
    "D": ["B", "E", "F", "I", "J"],
    "G": ["A", "E", "H", "I", "J"],
    "B": ["E", "F", "G", "I", "J"],
    "K": ["D", "E", "I", "J", "L"],
}

# The order in which backtracking assigns slots (least-constrained last).
TSLOTS: list[str] = ["E", "I", "A", "L", "D", "G", "B", "K"]

# ---------------------------------------------------------------------------
# PRNG — xorshift/murmur hash, exact JS Math.imul replication
# ---------------------------------------------------------------------------


def _to_u32(x: int) -> int:
    """Mask to 32-bit unsigned integer range [0, 2^32)."""
    return x & 0xFFFFFFFF


def _to_i32(x: int) -> int:
    """Reinterpret a 32-bit unsigned integer as signed int32."""
    x = x & 0xFFFFFFFF
    return x if x < 0x80000000 else x - 0x100000000


def _imul32(a: int, b: int) -> int:
    """Replicate JavaScript Math.imul: signed 32-bit integer multiplication.

    JS Math.imul(a, b) = C (int32)(uint32(a) * uint32(b)).
    We use pure-Python 64-bit multiplication then mask to 32 bits and sign-extend.
    This avoids all numpy overflow issues.
    """
    result = (_to_u32(a) * _to_u32(b)) & 0xFFFFFFFF
    return _to_i32(result)


def mul(seed: int) -> list[int]:
    """Create a deterministic PRNG from *seed* — matches JS ``mul(a)``.

    Returns a one-element list ``[state]`` so the int32 state can be mutated
    in-place (mirrors a JS closure).  Call ``next_rand(state)`` to draw floats.
    """
    # JS: a|=0  →  treat seed as signed int32
    return [_to_i32(seed)]


def next_rand(state: list[int]) -> float:
    """Draw one uniform float in [0, 1) — mutates *state* in-place.

    JavaScript source (verbatim):
        a|=0; a=(a+0x6D2B79F5)|0;
        let t=Math.imul(a^(a>>>15),1|a);
        t=(t+Math.imul(t^(t>>>7),61|t))^t;
        return((t^(t>>>14))>>>0)/4294967296;

    ``>>>`` is unsigned right shift (operates on uint32 view of the int32 value).
    ``|0`` after addition is signed-truncate-to-int32.
    """
    a = state[0]
    # a = (a + 0x6D2B79F5)|0
    a = _to_i32(_to_u32(a) + 0x6D2B79F5)
    state[0] = a

    # a>>>15: unsigned right shift — treat a as uint32 for shift only
    a_u = _to_u32(a)
    t = _imul32(a_u ^ (a_u >> 15), 1 | a_u)

    t_u = _to_u32(t)
    t = (_to_i32(t) + _imul32(t_u ^ (t_u >> 7), 61 | t_u)) ^ t

    # (t^(t>>>14))>>>0  — final unsigned shift + mask
    t_u2 = _to_u32(t)
    result = _to_u32(t_u2 ^ (t_u2 >> 14))
    return result / 4_294_967_296.0


# ---------------------------------------------------------------------------
# Poisson draw — inverse transform (same algorithm as JS)
# ---------------------------------------------------------------------------


def pois(lam: float, state: list[Any]) -> int:
    """Draw from Poisson(lam) via inverse CDF — matches JS ``pois(l, r)``."""
    if lam <= 0:
        return 0
    big_l = math.exp(-lam)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= next_rand(state)
        if p <= big_l:
            break
    return k - 1


# ---------------------------------------------------------------------------
# Lambda computation
# ---------------------------------------------------------------------------


def lams(
    hi: int,
    ai: int,
    draw_idx: int,
    post: dict[str, Any],
    adja: NDArray[np.float64],
    adjd: NDArray[np.float64],
) -> tuple[float, float]:
    """Compute (lambda_home, lambda_away) from posterior draw *draw_idx*.

    Mirrors JS: ``lams(hi, ai, d)`` where POST is the model object.
    """
    b = post["base"][draw_idx]
    ah = post["att"][hi][draw_idx] + float(adja[hi])
    dh = post["deff"][hi][draw_idx] + float(adjd[hi])
    aa = post["att"][ai][draw_idx] + float(adja[ai])
    da = post["deff"][ai][draw_idx] + float(adjd[ai])
    return math.exp(b + ah - da), math.exp(b + aa - dh)


# ---------------------------------------------------------------------------
# Single-match simulation
# ---------------------------------------------------------------------------


def play(
    hi: int,
    ai: int,
    draw_idx: int,
    state: list[Any],
    ko: bool,
    rho: float,
    post: dict[str, Any],
    adja: NDArray[np.float64],
    adjd: NDArray[np.float64],
) -> tuple[int, int, int]:
    """Simulate one match.

    Returns (goals_home, goals_away, winner_idx) where:
        winner_idx = 0  → home wins
        winner_idx = 1  → away wins
        winner_idx = 2  → draw (group stage only)

    Bivariate Poisson: common shock term lambda_3 = rho * min(lh, la).
    If ko=True and it's a draw after 90 min, play extra-time Poisson
    (lambda * 0.36) then penalty kicks via strength-weighted coin flip.
    """
    lh, la = lams(hi, ai, draw_idx, post, adja, adjd)

    if rho > 0:
        l3 = rho * min(lh, la)
        c = pois(l3, state)
        x = pois(lh - l3, state) + c
        y = pois(la - l3, state) + c
    else:
        x = pois(lh, state)
        y = pois(la, state)

    if not ko:
        if x > y:
            return x, y, 0
        elif y > x:
            return x, y, 1
        else:
            return x, y, 2

    # Knockout: play on if tied
    if x == y:
        x += pois(lh * 0.36, state)
        y += pois(la * 0.36, state)
        if x == y:
            # Penalty kick tiebreak: strength-weighted coin
            e = (
                0.5
                + (
                    (post["att"][hi][draw_idx] + post["deff"][hi][draw_idx])
                    - (post["att"][ai][draw_idx] + post["deff"][ai][draw_idx])
                )
                * 0.15
            )
            e = max(0.3, min(0.7, e))
            winner = 0 if next_rand(state) < e else 1
            return x, y, winner

    winner = 0 if x > y else 1
    return x, y, winner


# ---------------------------------------------------------------------------
# Annex C third-place allocation
# ---------------------------------------------------------------------------


def assign_thirds(groups_qualified: set[str]) -> dict[str, str] | None:
    """Backtracking assignment of 8 third-place groups to bracket slots.

    Mirrors JS ``assignThirds(Q)``:
    - Sort slots by how many qualified groups they can accept (ascending),
      so most-constrained slots are filled first.
    - Backtrack if no valid assignment found for a slot.

    Returns a dict mapping slot letter → group letter, or None if impossible.
    """
    def slot_options(slot: str) -> list[str]:
        return [g for g in TALLOW[slot] if g in groups_qualified]

    # Sort slots ascending by number of eligible groups (most constrained first)
    slots = sorted(TSLOTS, key=lambda s: len(slot_options(s)))

    used: dict[str, int] = {}
    result: dict[str, str] = {}

    def bt(i: int) -> bool:
        if i == len(slots):
            return True
        s = slots[i]
        for g in TALLOW[s]:
            if g in groups_qualified and g not in used:
                used[g] = 1
                result[s] = g
                if bt(i + 1):
                    return True
                del used[g]
        return False

    return result if bt(0) else None


# ---------------------------------------------------------------------------
# Strength computation (mirrors JS computeStrength)
# ---------------------------------------------------------------------------


def compute_strength(
    post: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compute mean attack + defence strength per team from all posterior draws.

    Returns a list sorted by strength descending:
    [{"team": str, "score": float, "att": float, "def": float}, ...]
    """
    teams = post["teams"]
    out = []
    for i, team in enumerate(teams):
        att_mean = float(np.mean(post["att"][i]))
        def_mean = float(np.mean(post["deff"][i]))
        out.append({"team": team, "score": att_mean + def_mean, "att": att_mean, "def": def_mean})
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


# ---------------------------------------------------------------------------
# Full tournament Monte Carlo
# ---------------------------------------------------------------------------


def run_tournament(
    n: int,
    post: dict[str, Any],
    tourney_state: dict[str, Any],
    adja: NDArray[np.float64],
    adjd: NDArray[np.float64],
    rho: float,
    seed: int,
) -> dict[str, dict[str, int]]:
    """Run *n* full-tournament Monte Carlo simulations.

    Returns a dict of {team_name → {ko, r16, qf, sf, final, champ, grpW}}
    where values are **counts** (not fractions).

    Exactly mirrors JS ``runT(N)`` including bracket structure,
    Annex-C third-place assignment, and fallback strength-seeded bracket.
    """
    teams: list[str] = post["teams"]
    n_draws: int = len(post["base"])

    # Team-name → index mapping (mirrors JS TI)
    ti: dict[str, int] = {t: i for i, t in enumerate(teams)}

    # Tourney data
    state_data: dict[str, dict[str, Any]] = tourney_state["state"]
    remaining: list[list[str]] = tourney_state["remaining"]
    groups: dict[str, list[str]] = tourney_state["groups"]
    gl: list[str] = list(groups.keys())

    # Strength ranking for tiebreak / fallback bracket (mirrors JS SR)
    strength = compute_strength(post)
    sr: dict[str, int] = {x["team"]: i for i, x in enumerate(strength)}

    # Tally initialisation
    tally: dict[str, dict[str, int]] = {
        t: {"ko": 0, "r16": 0, "qf": 0, "sf": 0, "final": 0, "champ": 0, "grpW": 0} for t in teams
    }

    # Single PRNG state for whole simulation (mirrors JS ``const r = mul(0xC0FFEE)``)
    rng = mul(0xC0FFEE)

    for _ in range(n):
        # Pick a posterior draw index
        d = int(next_rand(rng) * n_draws)

        # Copy current standings
        st: dict[str, dict[str, Any]] = {
            t: {"pts": s["pts"], "gf": s["gf"], "ga": s["ga"], "gd": s["gd"]}
            for t, s in state_data.items()
        }

        # Simulate remaining group-stage matches
        for h, a in remaining:
            gh, ga, w = play(ti[h], ti[a], d, rng, False, rho, post, adja, adjd)
            st[h]["gf"] += gh
            st[h]["ga"] += ga
            st[a]["gf"] += ga
            st[a]["ga"] += gh
            if w == 0:
                st[h]["pts"] += 3
            elif w == 1:
                st[a]["pts"] += 3
            else:
                st[h]["pts"] += 1
                st[a]["pts"] += 1

        # Recompute GD
        for t in st:
            st[t]["gd"] = st[t]["gf"] - st[t]["ga"]

        # Sort each group: pts → gd → gf → strength rank
        wn: dict[str, str] = {}
        ru: dict[str, str] = {}
        th: dict[str, str] = {}
        thirds: list[dict[str, Any]] = []

        for g in gl:
            sorted_teams = sorted(
                groups[g],
                key=lambda x: (
                    -st[x]["pts"],
                    -st[x]["gd"],
                    -st[x]["gf"],
                    sr.get(x, 99),
                ),
            )
            wn[g] = sorted_teams[0]
            ru[g] = sorted_teams[1]
            th[g] = sorted_teams[2]
            thirds.append(
                {
                    "g": g,
                    "t": sorted_teams[2],
                    "pts": st[sorted_teams[2]]["pts"],
                    "gd": st[sorted_teams[2]]["gd"],
                    "gf": st[sorted_teams[2]]["gf"],
                }
            )
            tally[sorted_teams[0]]["grpW"] += 1

        # Rank thirds: pts → gd → gf → strength rank
        thirds.sort(
            key=lambda x: (
                -x["pts"],
                -x["gd"],
                -x["gf"],
                sr.get(x["t"], 99),
            )
        )
        top8 = thirds[:8]
        groups_q = {x["g"] for x in top8}

        assign = assign_thirds(groups_q)

        w_match_map: dict[int, str] = {}

        def wmatch(team_a: str, team_b: str, _d: int = d) -> str:  # noqa: B023
            """Play a knockout match and return the winner's name."""
            _, _, winner = play(ti[team_a], ti[team_b], _d, rng, True, rho, post, adja, adjd)
            return team_a if winner == 0 else team_b

        if assign:
            def t_slot(
                slot: str,
                _th: dict[str, str] = th,
                _a: dict[str, str] = assign,
            ) -> str:
                """Third-place team assigned to *slot*."""
                return _th[_a[slot]]

            # R32 — 16 matches
            w_match_map[73] = wmatch(ru["A"], ru["B"])
            w_match_map[74] = wmatch(wn["E"], t_slot("E"))
            w_match_map[75] = wmatch(wn["F"], ru["C"])
            w_match_map[76] = wmatch(wn["C"], ru["F"])
            w_match_map[77] = wmatch(wn["I"], t_slot("I"))
            w_match_map[78] = wmatch(ru["E"], ru["I"])
            w_match_map[79] = wmatch(wn["A"], t_slot("A"))
            w_match_map[80] = wmatch(wn["L"], t_slot("L"))
            w_match_map[81] = wmatch(wn["D"], t_slot("D"))
            w_match_map[82] = wmatch(wn["G"], t_slot("G"))
            w_match_map[83] = wmatch(ru["K"], ru["L"])
            w_match_map[84] = wmatch(wn["H"], ru["J"])
            w_match_map[85] = wmatch(wn["B"], t_slot("B"))
            w_match_map[86] = wmatch(wn["J"], ru["H"])
            w_match_map[87] = wmatch(wn["K"], t_slot("K"))
            w_match_map[88] = wmatch(ru["D"], ru["G"])

            # All 32 R32 participants
            field = [
                ru["A"],
                ru["B"],
                wn["E"],
                t_slot("E"),
                wn["F"],
                ru["C"],
                wn["C"],
                ru["F"],
                wn["I"],
                t_slot("I"),
                ru["E"],
                ru["I"],
                wn["A"],
                t_slot("A"),
                wn["L"],
                t_slot("L"),
                wn["D"],
                t_slot("D"),
                wn["G"],
                t_slot("G"),
                ru["K"],
                ru["L"],
                wn["H"],
                ru["J"],
                wn["B"],
                t_slot("B"),
                wn["J"],
                ru["H"],
                wn["K"],
                t_slot("K"),
                ru["D"],
                ru["G"],
            ]
            for team in field:
                tally[team]["ko"] += 1

            # R16
            w_match_map[89] = wmatch(w_match_map[74], w_match_map[77])
            w_match_map[90] = wmatch(w_match_map[73], w_match_map[75])
            w_match_map[91] = wmatch(w_match_map[76], w_match_map[78])
            w_match_map[92] = wmatch(w_match_map[79], w_match_map[80])
            w_match_map[93] = wmatch(w_match_map[83], w_match_map[84])
            w_match_map[94] = wmatch(w_match_map[81], w_match_map[82])
            w_match_map[95] = wmatch(w_match_map[86], w_match_map[88])
            w_match_map[96] = wmatch(w_match_map[85], w_match_map[87])
            for m in [89, 90, 91, 92, 93, 94, 95, 96]:
                tally[w_match_map[m]]["r16"] += 1

            # QF
            w_match_map[97] = wmatch(w_match_map[89], w_match_map[90])
            w_match_map[98] = wmatch(w_match_map[93], w_match_map[94])
            w_match_map[99] = wmatch(w_match_map[91], w_match_map[92])
            w_match_map[100] = wmatch(w_match_map[95], w_match_map[96])
            for m in [97, 98, 99, 100]:
                tally[w_match_map[m]]["qf"] += 1

            # SF
            w_match_map[101] = wmatch(w_match_map[97], w_match_map[98])
            w_match_map[102] = wmatch(w_match_map[99], w_match_map[100])
            for m in [101, 102]:
                tally[w_match_map[m]]["sf"] += 1

            # Final
            w_match_map[104] = wmatch(w_match_map[101], w_match_map[102])
            tally[w_match_map[101]]["final"] += 1
            tally[w_match_map[102]]["final"] += 1
            tally[w_match_map[104]]["champ"] += 1

        else:
            # Fallback: strength-seeded bracket (rare — assign_thirds returns None)
            field = [wn[g] for g in gl] + [ru[g] for g in gl] + [x["t"] for x in top8]
            for team in field:
                tally[team]["ko"] += 1

            stages = ["r16", "qf", "sf", "final", "champ"]
            current_round = field[:]
            stage_idx = 0
            while len(current_round) > 1:
                current_round.sort(key=lambda x: sr.get(x, 99))
                next_round: list[str] = []
                half = len(current_round) // 2
                for i in range(half):
                    team_a = current_round[i]
                    team_b = current_round[len(current_round) - 1 - i]
                    _, _, w = play(ti[team_a], ti[team_b], d, rng, True, rho, post, adja, adjd)
                    next_round.append(team_a if w == 0 else team_b)
                for team in next_round:
                    tally[team][stages[stage_idx]] += 1
                current_round = next_round
                stage_idx += 1

    return tally
