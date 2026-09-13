"""Importance scoring: decide which files deserve the token budget first."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from .scanner import FileEntry

SOURCE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt", ".rb",
    ".php", ".c", ".h", ".cpp", ".hpp", ".cs", ".swift", ".scala", ".sh",
    ".bash", ".sql", ".lua", ".pl", ".ex", ".exs", ".dart", ".zig", ".jl",
}

ENTRY_POINT_BASENAMES = {
    "main.py", "__main__.py", "cli.py", "app.py", "server.py", "manage.py",
    "wsgi.py", "asgi.py", "index.js", "index.ts", "main.js", "main.ts",
    "main.go", "main.rs", "lib.rs", "mod.rs", "main.rb", "app.rb",
    "main.java", "main.c", "main.cpp",
}

MANIFEST_BASENAMES = {
    "pyproject.toml", "setup.py", "setup.cfg", "package.json", "cargo.toml",
    "go.mod", "requirements.txt", "pipfile", "environment.yml", "gemfile",
    "composer.json", "pom.xml", "build.gradle", "makefile", "dockerfile",
    "docker-compose.yml",
}

CORE_DIR_PREFIXES = {"src", "lib", "app", "pkg", "internal", "source", "core"}

TEST_MARKERS = ("tests", "test", "spec", "__tests__")


@dataclass
class ScoredFile:
    entry: FileEntry
    score: float
    reasons: list[str] = field(default_factory=list)


def _is_test(relpath: str, basename: str) -> bool:
    dirs = relpath.split("/")[:-1]
    if any(d in TEST_MARKERS for d in dirs):
        return True
    return (
        basename.startswith("test_")
        or ".spec." in basename
        or ".test." in basename
        or basename.endswith("_test.go")
    )


def score_file(entry: FileEntry, change_counts: Mapping[str, int] | None = None) -> ScoredFile:
    parts = entry.relpath.split("/")
    base = parts[-1].lower()
    ext = os.path.splitext(base)[1]
    depth = len(parts) - 1
    change_counts = change_counts or {}

    score = 0.0
    reasons: list[str] = []

    if base.startswith("readme"):
        score += 1000
        reasons.append("project overview")
    if base in ENTRY_POINT_BASENAMES:
        score += 500
        reasons.append("entry point")
    if base in MANIFEST_BASENAMES:
        score += 400
        reasons.append("project manifest")
    if ext in SOURCE_EXTENSIONS:
        score += 150
        reasons.append("source code")
    if parts[0] in CORE_DIR_PREFIXES:
        score += 120
        reasons.append("core directory")
    if ext == ".md":
        score += 60
        reasons.append("docs")
    if base in ("changelog.md", "contributing.md"):
        score += 40
        reasons.append("meta doc")

    if _is_test(entry.relpath, base):
        score -= 250
        reasons.append("tests")

    score -= 20 * depth  # shallower files matter more
    commits = change_counts.get(entry.relpath, 0)
    if commits:
        score += 10 * min(commits, 20)
        reasons.append(f"git heat ({commits} commits)")
    if entry.tokens > 20_000:
        score -= 100
        reasons.append("very large file")

    if not reasons:
        reasons.append("general file")
    return ScoredFile(entry, score, reasons)


def score_files(
    entries: list[FileEntry], change_counts: Mapping[str, int] | None = None
) -> list[ScoredFile]:
    """Score every entry and return them sorted by priority (best first)."""
    scored = [score_file(e, change_counts) for e in entries]
    scored.sort(key=lambda s: (-s.score, s.entry.relpath))
    return scored
