"""Model trainer â€” importable version of retrain.py.

Ports retrain.py to an importable ``retrain()`` function that:
1. Downloads the martj42 international_results dataset
2. Fits an attack/defence Poisson model with temporal decay (IRLS)
3. Writes data/POST.json and data/model_meta.json atomically
4. Returns a metadata dict matching the model_meta.json schema

CLI usage (unchanged): ``python retrain.py``
Module usage:          ``from backend.app.model.trainer import retrain``
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Constants (verbatim from retrain.py)
# ---------------------------------------------------------------------------

RIDGE: float = 6.0
DATA_URL: str = (
    "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
)

TEAMS: list[str] = [
    "Algeria",
    "Argentina",
    "Australia",
    "Austria",
    "Belgium",
    "Bosnia and Herzegovina",
    "Brazil",
    "Cabo Verde",
    "Canada",
    "Colombia",
    "Croatia",
    "CuraÃ§ao",
    "Czechia",
    "CÃ´te d'Ivoire",
    "DR Congo",
    "Ecuador",
    "Egypt",
    "England",
    "France",
    "Germany",
    "Ghana",
    "Haiti",
    "Iran",
    "Iraq",
    "Japan",
    "Jordan",
    "Mexico",
    "Morocco",
    "Netherlands",
    "New Zealand",
    "Norway",
    "Panama",
    "Paraguay",
    "Portugal",
    "Qatar",
    "Saudi Arabia",
    "Scotland",
    "Senegal",
    "South Africa",
    "South Korea",
    "Spain",
    "Sweden",
    "Switzerland",
    "Tunisia",
    "TÃ¼rkiye",
    "USA",
    "Uruguay",
    "Uzbekistan",
]

ALIAS: dict[str, str] = {
    "Cape Verde": "Cabo Verde",
    "Czech Republic": "Czechia",
    "Ivory Coast": "CÃ´te d'Ivoire",
    "Turkey": "TÃ¼rkiye",
    "United States": "USA",
    "DR Congo": "DR Congo",
    "Congo DR": "DR Congo",
}

_TI: dict[str, int] = {t: i for i, t in enumerate(TEAMS)}
_N: int = len(TEAMS)

_BIG_TOURNAMENTS: tuple[str, ...] = (
    "FIFA World Cup",
    "Copa AmÃ©rica",
    "UEFA Euro",
    "African Cup",
    "Gold Cup",
    "AFC Asian Cup",
    "Confederations",
    "UEFA Nations",
    "Finalissima",
)

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

# This file is at backend/app/model/trainer.py â†’ repo root is 4 levels up
_REPO_ROOT: Path = Path(__file__).resolve().parents[3]
_DATA_DIR: Path = _REPO_ROOT / "data"


def _atomic_write(path: Path, data: Any) -> None:  # noqa: ANN401  # noqa: ANN401 -> None:
    """Write *data* as JSON to *path* atomically (tmp + rename)."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Pipeline steps (mirrors retrain.py functions verbatim)
# ---------------------------------------------------------------------------


def _normalise(name: str) -> str:
    return ALIAS.get(name, name)


def _load_rows() -> list[dict[str, str]]:
    """Download the martj42 dataset and return parsed CSV rows."""
    req = urllib.request.Request(DATA_URL, headers={"User-Agent": "Mozilla/5.0"})  # noqa: S310
    raw = urllib.request.urlopen(req, timeout=30).read().decode()  # noqa: S310
    rows = list(csv.DictReader(raw.splitlines()))
    return rows


def _build_matrices(
    rows: list[dict[str, str]],
    half_life: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """Build design matrix X, target y, weights w from raw rows."""
    ref = dt.date.today()
    p = 2 + 2 * _N  # [base, home_adv, att(N), def(N)]

    x_rows: list[np.ndarray] = []
    y_vals: list[float] = []
    w_vals: list[float] = []

    for r in rows:
        h = _normalise(r["home_team"])
        a = _normalise(r["away_team"])
        if h not in _TI or a not in _TI:
            continue
        try:
            hs = int(r["home_score"])
            as_ = int(r["away_score"])
            d = dt.date.fromisoformat(r["date"])
        except (ValueError, KeyError):
            continue

        age = (ref - d).days / 365.25
        wt = 0.5 ** (age / half_life)
        if any(b in r.get("tournament", "") for b in _BIG_TOURNAMENTS):
            wt *= 1.6
        neutral = r.get("neutral", "").upper() == "TRUE"
        hi = _TI[h]
        ai = _TI[a]

        # Home goals row: base + home_adv (if not neutral) + att_h - def_a
        row_h = np.zeros(p)
        row_h[0] = 1
        if not neutral:
            row_h[1] = 1
        row_h[2 + hi] = 1
        row_h[2 + _N + ai] = -1
        x_rows.append(row_h)
        y_vals.append(float(hs))
        w_vals.append(wt)

        # Away goals row: base + att_a - def_h
        row_a = np.zeros(p)
        row_a[0] = 1
        row_a[2 + ai] = 1
        row_a[2 + _N + hi] = -1
        x_rows.append(row_a)
        y_vals.append(float(as_))
        w_vals.append(wt)

    return (
        np.array(x_rows),
        np.array(y_vals, dtype=float),
        np.array(w_vals),
        p,
    )


def _fit_irls(
    x_mat: np.ndarray,
    y_vec: np.ndarray,
    w_vec: np.ndarray,
    p: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Fit Poisson log-linear model via IRLS with ridge prior."""
    beta = np.zeros(p)
    ridge = np.ones(p) * RIDGE
    ridge[0] = 0.0  # no penalise base
    ridge[1] = 0.0  # no penalise home_adv
    r_mat = np.diag(ridge)
    hessian = r_mat  # initialise; overwritten in first iteration

    for _it in range(60):
        eta = x_mat @ beta
        mu = np.exp(np.clip(eta, -6, 6))
        grad = x_mat.T @ (w_vec * (y_vec - mu)) - ridge * beta
        w_diag = w_vec * mu
        hessian = (x_mat.T * w_diag) @ x_mat + r_mat
        step = np.linalg.solve(hessian, grad)
        beta += step
        if np.max(np.abs(step)) < 1e-7:
            break

    cov = np.linalg.inv(hessian)
    return beta, cov


def _export_draws(
    beta: np.ndarray,
    cov: np.ndarray,
    n_draws: int,
) -> dict[str, Any]:
    """Sample Laplace posterior and build the POST.json payload."""
    l_mat = np.linalg.cholesky(cov + 1e-9 * np.eye(len(beta)))
    draws = beta + (l_mat @ np.random.standard_normal((len(beta), n_draws))).T

    base = draws[:, 0]
    home = draws[:, 1]
    att = draws[:, 2 : 2 + _N].T  # _N x n_draws
    deff = draws[:, 2 + _N : 2 + 2 * _N].T

    return {
        "teams": TEAMS,
        "att": [[round(float(v), 4) for v in att[i]] for i in range(_N)],
        "deff": [[round(float(v), 4) for v in deff[i]] for i in range(_N)],
        "base": [round(float(v), 4) for v in base],
        "home_adv": [round(float(v), 4) for v in home],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def retrain(half_life: float = 3.0, n_draws: int = 400) -> dict[str, Any]:
    """Fit the model and write data/POST.json + data/model_meta.json.

    Parameters
    ----------
    half_life:
        Temporal decay half-life in years.  Must be in [0.5, 10.0).
    n_draws:
        Number of posterior draws to export.

    Returns
    -------
    Metadata dict that was written to data/model_meta.json.
    """
    rows = _load_rows()
    x_mat, y_vec, w_vec, p = _build_matrices(rows, half_life)
    beta, cov = _fit_irls(x_mat, y_vec, w_vec, p)
    post = _export_draws(beta, cov, n_draws)

    # Compute top-10 ranking for metadata
    att_arr = np.array(post["att"])  # _N x n_draws
    deff_arr = np.array(post["deff"])
    scores = att_arr.mean(axis=1) + deff_arr.mean(axis=1)
    order = np.argsort(-scores)
    top10 = [TEAMS[i] for i in order[:10]]

    # Write POST.json
    _atomic_write(_DATA_DIR / "POST.json", post)

    # Write model_meta.json
    trained_at = dt.datetime.now(dt.UTC).isoformat()
    meta: dict[str, Any] = {
        "model_id": "current",
        "trained_at": trained_at,
        "half_life": half_life,
        "n_draws": n_draws,
        "top10": top10,
    }
    _atomic_write(_DATA_DIR / "model_meta.json", meta)

    return meta


def _top10_from_post(post: dict[str, Any]) -> list[str]:
    """Return top-10 teams from an existing POST payload (for re-computing strength)."""
    att_arr = np.array(post["att"])
    deff_arr = np.array(post["deff"])
    scores = att_arr.mean(axis=1) + deff_arr.mean(axis=1)
    order = np.argsort(-scores)
    return [TEAMS[i] for i in order[:10]]

