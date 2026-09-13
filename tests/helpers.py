"""Shared test utilities. Also makes `src/` importable without installing."""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def force_heuristic_tokens() -> None:
    """Pin the token backend to the chars/4 heuristic for deterministic tests."""
    import budgetpack.tokens as tokens

    tokens._encoding = None
    tokens._encoding_checked = True


def make_repo(base: Path) -> Path:
    """Create a small fixture repository."""
    root = base / "repo"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "node_modules" / "pkg").mkdir(parents=True)

    (root / "README.md").write_text("# demo repo\n\nhello world\n", encoding="utf-8")
    (root / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (root / "src" / "app.py").write_text("def app():\n    return 42\n", encoding="utf-8")
    (root / "src" / "util.py").write_text("x = 1\n", encoding="utf-8")
    (root / "tests" / "test_app.py").write_text("assert True\n", encoding="utf-8")
    (root / "notes.log").write_text("2026-01-01 started\n", encoding="utf-8")
    (root / "node_modules" / "pkg" / "index.js").write_text(
        "module.exports = 1;\n", encoding="utf-8"
    )
    (root / "blob.bin").write_bytes(b"abc\x00def\n")
    (root / ".gitignore").write_text("*.log\n", encoding="utf-8")
    return root
