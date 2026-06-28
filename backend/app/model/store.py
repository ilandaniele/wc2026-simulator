"""Data I/O layer — reads / writes JSON state files under data/.

All paths are resolved relative to the repo root (parent of backend/).
Atomic writes use a tmp file + rename to prevent partial reads.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, cast

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

# DATA_DIR env var overrides the default (used in tests via backend/tests/fixtures/).
# Default: repo root's data/ directory (4 parents up from backend/app/model/store.py).
_REPO_ROOT: Path = Path(__file__).resolve().parents[3]
_DATA_DIR: Path = Path(os.environ.get("DATA_DIR") or str(_REPO_ROOT / "data"))


def _data_path(filename: str) -> Path:
    return _DATA_DIR / filename


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------


def load_post(model_id: str = "current") -> dict[str, Any]:
    """Load posterior samples.

    model_id="current" → data/POST.json
    model_id="legacy"  → data/POST_A.json
    """
    filename = "POST.json" if model_id == "current" else "POST_A.json"
    path = _data_path(filename)
    with open(path, encoding="utf-8") as f:
        return cast(dict[str, Any], json.load(f))


def load_tourney() -> dict[str, Any]:
    """Load tournament state from data/tourney.json."""
    with open(_data_path("tourney.json"), encoding="utf-8") as f:
        return cast(dict[str, Any], json.load(f))


def load_market() -> dict[str, Any]:
    """Load market odds from data/market.json."""
    with open(_data_path("market.json"), encoding="utf-8") as f:
        return cast(dict[str, Any], json.load(f))


_DEFAULT_META: dict[str, Any] = {
    "model_id": "current",
    "half_life": 3.0,
    "n_draws": 400,
    "trained_at": "2026-06-27T00:00:00Z",
    "top10": [
        "Argentina",
        "Portugal",
        "Brazil",
        "France",
        "Spain",
        "Colombia",
        "Belgium",
        "Germany",
        "Netherlands",
        "England",
    ],
}


def load_meta() -> dict[str, Any]:
    """Load model metadata from data/model_meta.json.

    If the file does not exist (e.g. fresh clone before retrain), returns and
    seeds with default values matching the spec.
    """
    path = _data_path("model_meta.json")
    if not path.exists():
        # Seed the file so subsequent calls find it
        _write_json(path, _DEFAULT_META)
        return dict(_DEFAULT_META)
    with open(path, encoding="utf-8") as f:
        return cast(dict[str, Any], json.load(f))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Write *data* to *path* atomically."""
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
# Writers
# ---------------------------------------------------------------------------


def save_tourney(state: dict[str, Any]) -> None:
    """Atomically write *state* to data/tourney.json.

    Uses a temporary file in the same directory then renames so a failed
    write cannot corrupt the existing file.
    """
    _write_json(_data_path("tourney.json"), state)


def save_market(data: dict[str, Any]) -> None:
    """Atomically write *data* to data/market.json.

    Uses a temporary file in the same directory then renames so a failed
    write cannot corrupt the existing file.
    """
    _write_json(_data_path("market.json"), data)


def load_r32() -> dict[str, Any]:
    """Load R32 actual results from data/r32.json. Returns empty dict if missing."""
    path = _data_path("r32.json")
    if not path.exists():
        return {"results": {}}
    with open(path, encoding="utf-8") as f:
        return cast(dict[str, Any], json.load(f))


def save_r32(data: dict[str, Any]) -> None:
    """Atomically write R32 results to data/r32.json."""
    _write_json(_data_path("r32.json"), data)


def load_coaches() -> dict[str, Any]:
    """Load coach metadata from data/coaches.json. Returns empty dict if missing."""
    path = _data_path("coaches.json")
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return cast(dict[str, Any], json.load(f))
