"""Unit tests for backend/app/model/store.py — covers edge-case branches."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from backend.app.model.store import (
    _DEFAULT_META,
    _write_json,
    load_coaches,
    load_meta,
    load_r32,
    load_r32_bracket,
    save_market,
    save_r32,
)


def test_load_meta_creates_default_when_missing(tmp_path: Path) -> None:
    """load_meta() seeds the file with defaults when model_meta.json is absent."""
    with patch("backend.app.model.store._DATA_DIR", tmp_path):
        result = load_meta()
    assert result["model_id"] == _DEFAULT_META["model_id"]
    assert result["half_life"] == _DEFAULT_META["half_life"]
    seeded = tmp_path / "model_meta.json"
    assert seeded.exists(), "load_meta should write the default file"


def test_load_coaches_returns_empty_when_missing(tmp_path: Path) -> None:
    """load_coaches() returns {} when coaches.json does not exist."""
    with patch("backend.app.model.store._DATA_DIR", tmp_path):
        result = load_coaches()
    assert result == {}


def test_load_r32_bracket_returns_none_when_missing(tmp_path: Path) -> None:
    """load_r32_bracket() returns None when r32_bracket.json does not exist."""
    with patch("backend.app.model.store._DATA_DIR", tmp_path):
        result = load_r32_bracket()
    assert result is None


def test_load_r32_returns_empty_results_when_missing(tmp_path: Path) -> None:
    """load_r32() returns {results: {}} when r32.json does not exist."""
    with patch("backend.app.model.store._DATA_DIR", tmp_path):
        result = load_r32()
    assert result == {"results": {}}


def test_save_market_writes_file(tmp_path: Path) -> None:
    """save_market() atomically writes market.json."""
    with patch("backend.app.model.store._DATA_DIR", tmp_path):
        save_market({"Brazil|Argentina": {"h": 150, "d": 300, "a": 210}})
    assert (tmp_path / "market.json").exists()


def test_save_r32_writes_file(tmp_path: Path) -> None:
    """save_r32() atomically writes r32.json."""
    with patch("backend.app.model.store._DATA_DIR", tmp_path):
        save_r32({"results": {"73": {"score_h": 2, "score_a": 1}}})
    assert (tmp_path / "r32.json").exists()


def test_write_json_cleans_up_temp_on_failure(tmp_path: Path) -> None:
    """_write_json() removes the temp file and re-raises when json.dump fails."""
    target = tmp_path / "out.json"
    with patch("json.dump", side_effect=RuntimeError("simulated write error")):
        with pytest.raises(RuntimeError, match="simulated write error"):
            _write_json(target, {"x": 1})
    # No stray temp files should remain
    assert list(tmp_path.glob("*.tmp")) == []


def test_write_json_cleanup_silences_unlink_error(tmp_path: Path) -> None:
    """_write_json() suppresses OSError from os.unlink during cleanup and re-raises original."""
    target = tmp_path / "out.json"
    with (
        patch("json.dump", side_effect=RuntimeError("write error")),
        patch("os.unlink", side_effect=OSError("unlink failed")),
    ):
        with pytest.raises(RuntimeError, match="write error"):
            _write_json(target, {"x": 1})
