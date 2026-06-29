"""Unit tests for backend/app/model/trainer.py — pure functions only.

Network-bound functions (_load_rows, retrain) are tested with mocked _load_rows
so no internet access is required.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest
from backend.app.model.trainer import (
    _N,
    ALIAS,
    TEAMS,
    _atomic_write,
    _build_matrices,
    _export_draws,
    _fit_irls,
    _normalise,
    _top10_from_post,
    retrain,
)

# ---------------------------------------------------------------------------
# Minimal row factory
# ---------------------------------------------------------------------------

_BASE_ROW: dict[str, str] = {
    "home_team": "Argentina",
    "away_team": "Brazil",
    "home_score": "2",
    "away_score": "1",
    "date": "2024-06-01",
    "tournament": "FIFA World Cup",
    "neutral": "FALSE",
}


def _row(**kwargs: str) -> dict[str, str]:
    return {**_BASE_ROW, **kwargs}


# ---------------------------------------------------------------------------
# _normalise
# ---------------------------------------------------------------------------


def test_normalise_known_alias() -> None:
    """Known aliases map correctly."""
    for alias, canonical in ALIAS.items():
        assert _normalise(alias) == canonical


def test_normalise_unknown_passthrough() -> None:
    """Teams not in ALIAS are returned unchanged."""
    assert _normalise("Argentina") == "Argentina"
    assert _normalise("FantasyFC") == "FantasyFC"


# ---------------------------------------------------------------------------
# _build_matrices
# ---------------------------------------------------------------------------


def test_build_matrices_valid_rows() -> None:
    """Valid rows produce X, y, w with the right shape (2 rows per match)."""
    rows = [_row()]
    x_mat, y_vec, w_vec, p = _build_matrices(rows, half_life=3.0)
    assert x_mat.shape[0] == 2  # home + away row
    assert x_mat.shape[1] == p
    assert len(y_vec) == 2
    assert len(w_vec) == 2


def test_build_matrices_skips_unknown_teams() -> None:
    """Rows with teams not in the 48-team list are silently skipped."""
    rows = [_row(home_team="FantasyFC"), _row()]
    x_mat, _, _, _ = _build_matrices(rows, half_life=3.0)
    # Only the valid row contributes (2 rows for 1 match)
    assert x_mat.shape[0] == 2


def test_build_matrices_skips_bad_score() -> None:
    """Rows with non-integer scores are skipped."""
    rows = [_row(home_score="na"), _row()]
    x_mat, _, _, _ = _build_matrices(rows, half_life=3.0)
    assert x_mat.shape[0] == 2


def test_build_matrices_skips_bad_date() -> None:
    """Rows with malformed dates are skipped."""
    rows = [_row(date="not-a-date"), _row()]
    x_mat, _, _, _ = _build_matrices(rows, half_life=3.0)
    assert x_mat.shape[0] == 2


def test_build_matrices_neutral_flag() -> None:
    """Neutral-field rows set home_adv coefficient to 0."""
    rows_neutral = [_row(neutral="TRUE")]
    rows_home = [_row(neutral="FALSE")]
    x_neutral, _, _, _ = _build_matrices(rows_neutral, half_life=3.0)
    x_home, _, _, _ = _build_matrices(rows_home, half_life=3.0)
    # Column index 1 is home_adv; neutral row should have 0 there
    assert x_neutral[0, 1] == 0.0
    assert x_home[0, 1] == 1.0


def test_build_matrices_big_tournament_weight() -> None:
    """Big-tournament matches get higher weight than friendlies."""
    rows_big = [_row(tournament="FIFA World Cup")]
    rows_small = [_row(tournament="Friendly")]
    _, _, w_big, _ = _build_matrices(rows_big, half_life=3.0)
    _, _, w_small, _ = _build_matrices(rows_small, half_life=3.0)
    assert w_big[0] > w_small[0]


def test_build_matrices_produces_p_columns() -> None:
    """Design matrix width equals 2 + 2 * N_TEAMS."""
    rows = [_row()]
    _, _, _, p = _build_matrices(rows, half_life=3.0)
    assert p == 2 + 2 * _N


# ---------------------------------------------------------------------------
# _fit_irls
# ---------------------------------------------------------------------------


def test_fit_irls_returns_beta_and_cov() -> None:
    """IRLS converges and returns beta (p,) and cov (p, p)."""
    p = 4  # tiny synthetic problem: base, home, att0, def0
    x_mat = np.array([[1.0, 1.0, 1.0, -1.0], [1.0, 0.0, 1.0, -1.0]], dtype=float)
    y_vec = np.array([2.0, 1.0])
    w_vec = np.array([1.0, 1.0])
    beta, cov = _fit_irls(x_mat, y_vec, w_vec, p)
    assert beta.shape == (p,)
    assert cov.shape == (p, p)


def test_fit_irls_cov_positive_definite() -> None:
    """Covariance matrix from IRLS must be positive definite."""
    rows = [_row(), _row(home_team="France", away_team="Germany", home_score="1", away_score="1")]
    x_mat, y_vec, w_vec, p = _build_matrices(rows, half_life=3.0)
    beta, cov = _fit_irls(x_mat, y_vec, w_vec, p)
    eigenvalues = np.linalg.eigvalsh(cov)
    assert np.all(eigenvalues >= 0)


# ---------------------------------------------------------------------------
# _export_draws
# ---------------------------------------------------------------------------


def test_export_draws_structure() -> None:
    """_export_draws returns a dict with the POST.json schema."""
    p = 2 + 2 * _N
    beta = np.zeros(p)
    cov = np.eye(p) * 0.01
    result = _export_draws(beta, cov, n_draws=10)
    assert result["teams"] == TEAMS
    assert len(result["base"]) == 10
    assert len(result["home_adv"]) == 10
    assert len(result["att"]) == _N
    assert len(result["deff"]) == _N
    assert len(result["att"][0]) == 10


# ---------------------------------------------------------------------------
# _top10_from_post
# ---------------------------------------------------------------------------


def test_top10_from_post() -> None:
    """_top10_from_post returns exactly 10 team names from the loaded post."""
    from backend.app.model.store import load_post

    post = load_post()
    top10 = _top10_from_post(post)
    assert len(top10) == 10
    assert all(t in TEAMS for t in top10)


# ---------------------------------------------------------------------------
# _atomic_write
# ---------------------------------------------------------------------------


def test_atomic_write_success(tmp_path: Path) -> None:
    """_atomic_write creates the target file with correct JSON content."""
    target = tmp_path / "data.json"
    _atomic_write(target, {"key": "value"})
    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == {"key": "value"}


def test_atomic_write_cleanup_on_failure(tmp_path: Path) -> None:
    """_atomic_write removes the temp file and re-raises on json.dump failure."""
    target = tmp_path / "data.json"
    with patch("json.dump", side_effect=RuntimeError("fail")):
        with pytest.raises(RuntimeError, match="fail"):
            _atomic_write(target, {"x": 1})
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_write_cleanup_silences_unlink_error(tmp_path: Path) -> None:
    """_atomic_write suppresses OSError from os.unlink during cleanup."""
    target = tmp_path / "data.json"
    with (
        patch("json.dump", side_effect=RuntimeError("fail")),
        patch("os.unlink", side_effect=OSError("unlink failed")),
    ):
        with pytest.raises(RuntimeError, match="fail"):
            _atomic_write(target, {"x": 1})


# ---------------------------------------------------------------------------
# retrain (mocked _load_rows — no network)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# _load_rows (mocked HTTP)
# ---------------------------------------------------------------------------


def test_load_rows_downloads_and_parses_csv() -> None:
    """_load_rows fetches and parses CSV — covers lines 146-149 without network."""
    from unittest.mock import MagicMock

    from backend.app.model.trainer import _load_rows

    csv_content = (
        "date,home_team,away_team,home_score,away_score,tournament,neutral\n"
        "2024-01-01,Argentina,Brazil,2,1,FIFA World Cup,FALSE\n"
        "2024-02-01,France,Germany,1,1,Friendly,TRUE\n"
    )
    mock_resp = MagicMock()
    mock_resp.read.return_value = csv_content.encode("utf-8")

    with patch("urllib.request.urlopen", return_value=mock_resp):
        rows = _load_rows()

    assert len(rows) == 2
    assert rows[0]["home_team"] == "Argentina"
    assert rows[1]["neutral"] == "TRUE"


# ---------------------------------------------------------------------------
# retrain (mocked _load_rows — no network)
# ---------------------------------------------------------------------------


def _minimal_rows() -> list[dict[str, str]]:
    """Two valid match rows using WC2026 teams."""
    return [
        {
            "home_team": "Argentina",
            "away_team": "Brazil",
            "home_score": "2",
            "away_score": "1",
            "date": "2024-01-01",
            "tournament": "FIFA World Cup",
            "neutral": "FALSE",
        },
        {
            "home_team": "France",
            "away_team": "Germany",
            "home_score": "1",
            "away_score": "1",
            "date": "2023-06-01",
            "tournament": "Friendly",
            "neutral": "TRUE",
        },
    ]


def test_retrain_writes_post_and_meta(tmp_path: Path) -> None:
    """retrain() with mocked _load_rows writes POST.json and model_meta.json."""
    with (
        patch("backend.app.model.trainer._load_rows", return_value=_minimal_rows()),
        patch("backend.app.model.trainer._DATA_DIR", tmp_path),
    ):
        meta = retrain(half_life=3.0, n_draws=5)

    assert meta["half_life"] == 3.0
    assert meta["n_draws"] == 5
    assert len(meta["top10"]) == 10
    assert (tmp_path / "POST.json").exists()
    assert (tmp_path / "model_meta.json").exists()


def test_retrain_meta_schema(tmp_path: Path) -> None:
    """retrain() meta dict contains all expected keys."""
    with (
        patch("backend.app.model.trainer._load_rows", return_value=_minimal_rows()),
        patch("backend.app.model.trainer._DATA_DIR", tmp_path),
    ):
        meta = retrain(half_life=2.0, n_draws=3)

    for key in ("model_id", "trained_at", "half_life", "n_draws", "top10"):
        assert key in meta, f"Missing key: {key}"


def test_retrain_post_schema(tmp_path: Path) -> None:
    """POST.json written by retrain() has the correct schema."""
    with (
        patch("backend.app.model.trainer._load_rows", return_value=_minimal_rows()),
        patch("backend.app.model.trainer._DATA_DIR", tmp_path),
    ):
        retrain(half_life=3.0, n_draws=8)

    post: Any = json.loads((tmp_path / "POST.json").read_text(encoding="utf-8"))
    assert "teams" in post and "att" in post and "deff" in post
    assert "base" in post and "home_adv" in post
    assert len(post["base"]) == 8
    assert len(post["att"]) == len(TEAMS)
