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


def _write(path: Path, text: str) -> None:
    # Force LF so file sizes (and token estimates derived from them) are
    # identical on Windows, Linux and macOS.
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def make_repo(base: Path) -> Path:
    """Create a small fixture repository."""
    root = base / "repo"
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "node_modules" / "pkg").mkdir(parents=True)

    _write(root / "README.md", "# demo repo\n\nhello world\n")
    _write(root / "main.py", "print('hi')\n")
    _write(root / "src" / "app.py", "def app():\n    return 42\n")
    _write(root / "src" / "util.py", "x = 1\n")
    _write(root / "tests" / "test_app.py", "assert True\n")
    _write(root / "notes.log", "2026-01-01 started\n")
    (root / "node_modules" / "pkg" / "index.js").write_text(
        "module.exports = 1;\n", encoding="utf-8"
    )
    (root / "blob.bin").write_bytes(b"abc\x00def\n")
    _write(root / ".gitignore", "*.log\n")
    return root
