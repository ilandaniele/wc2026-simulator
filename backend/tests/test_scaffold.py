"""Tests for W1: repo scaffold, .gitignore, and README.md.

AC28 — .gitignore lists the required patterns.
AC29 — README.md includes the uvicorn launch command, frontend dev commands,
        and the 3 research module commands.
"""

from pathlib import Path

# Repo root is two levels above this file (backend/tests/test_scaffold.py)
REPO_ROOT = Path(__file__).parent.parent.parent


class TestGitignore:
    """AC28 — .gitignore contains all required patterns."""

    def _read(self) -> str:
        return (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

    def test_data_post_json(self) -> None:
        assert "data/POST.json" in self._read()

    def test_data_post_a_json(self) -> None:
        assert "data/POST_A.json" in self._read()

    def test_frontend_node_modules(self) -> None:
        assert "frontend/node_modules/" in self._read()

    def test_frontend_dist(self) -> None:
        assert "frontend/dist/" in self._read()

    def test_backend_venv(self) -> None:
        assert "backend/.venv/" in self._read()

    def test_pycache(self) -> None:
        assert "__pycache__/" in self._read()

    def test_pytest_cache(self) -> None:
        assert ".pytest_cache/" in self._read()

    def test_research_json(self) -> None:
        assert "research/*.json" in self._read()

    def test_research_md(self) -> None:
        assert "research/*.md" in self._read()


class TestReadme:
    """AC29 — README.md contains setup instructions."""

    def _read(self) -> str:
        return (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    def test_uvicorn_launch_command(self) -> None:
        assert "uvicorn" in self._read()

    def test_frontend_npm_install(self) -> None:
        content = self._read()
        assert "npm install" in content or "npm ci" in content

    def test_frontend_npm_dev(self) -> None:
        assert "npm run dev" in self._read()

    def test_research_bivariate_command(self) -> None:
        assert "bivariate_vs_independent" in self._read()

    def test_research_halflife_command(self) -> None:
        assert "halflife_sensitivity" in self._read()

    def test_research_market_edge_command(self) -> None:
        assert "market_edge_today" in self._read()
