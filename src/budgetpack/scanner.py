"""Filesystem scanning: walk the tree, apply ignore rules, read text files."""

from __future__ import annotations

import contextlib
import os
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .gitignore import DEFAULT_EXCLUDES, IgnoreStack, compile_ignore_line
from .tokens import count_tokens

DEFAULT_MAX_FILE_SIZE = 1_000_000  # bytes of source text per file

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".icns", ".tiff",
    ".mp3", ".mp4", ".avi", ".mov", ".mkv", ".webm", ".wav", ".flac", ".ogg",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".jar", ".war",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".obj", ".o", ".a", ".lib",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".db", ".sqlite", ".sqlite3", ".mdb",
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    ".pyc", ".pyo", ".class", ".wasm",
    ".psd", ".ai", ".sketch", ".fig",
    ".onnx", ".pt", ".pth", ".h5", ".keras", ".pb", ".safetensors",
    ".parquet", ".feather", ".arrow", ".npy", ".npz", ".pkl", ".pickle",
}


@dataclass
class FileEntry:
    relpath: str  # posix-style, relative to the scan root
    abspath: Path
    size: int
    text: str | None  # None when skipped (binary / too large)
    tokens: int
    skip_reason: str | None = None  # set when the content was not read


def _looks_binary(chunk: bytes) -> bool:
    return b"\x00" in chunk


def scan(
    root: Path,
    extra_excludes: Sequence[str] = (),
    extra_includes: Sequence[str] = (),
    respect_gitignore: bool = True,
    use_default_excludes: bool = True,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
) -> list[FileEntry]:
    """Walk *root* and return readable text files as :class:`FileEntry` items."""
    exclude_pats = [p for line in extra_excludes if (p := compile_ignore_line(line))]
    include_pats = [p for line in extra_includes if (p := compile_ignore_line(line))]

    def cli_excluded(relpath: str, is_dir: bool) -> bool:
        return any(p.matches(relpath, is_dir) for p in exclude_pats)

    def cli_included(relpath: str) -> bool:
        return not include_pats or any(p.matches(relpath, False) for p in include_pats)

    stack = IgnoreStack()
    if use_default_excludes:
        stack.push("", DEFAULT_EXCLUDES)
    if respect_gitignore:
        root_gitignore = root / ".gitignore"
        if root_gitignore.is_file():
            with contextlib.suppress(OSError):
                stack.push("", root_gitignore.read_text(encoding="utf-8", errors="replace"))

    entries: list[FileEntry] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirpath = Path(dirpath)
        rel_dir = dirpath.relative_to(root).as_posix()
        if rel_dir != "." and stack.ignored(rel_dir, True):
            dirnames[:] = []
            continue

        gitignore = dirpath / ".gitignore"
        if respect_gitignore and gitignore.is_file():
            with contextlib.suppress(OSError):
                stack.push(rel_dir, gitignore.read_text(encoding="utf-8", errors="replace"))

        kept_dirs = []
        for d in sorted(dirnames):
            rel = f"{rel_dir}/{d}" if rel_dir != "." else d
            if d == ".git" or stack.ignored(rel, True) or cli_excluded(rel, True):
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs

        for name in sorted(filenames):
            rel = f"{rel_dir}/{name}" if rel_dir != "." else name
            if name == ".gitignore" or stack.ignored(rel, False) or cli_excluded(rel, False):
                continue
            if not cli_included(rel):
                continue
            entry = _make_entry(root, rel, max_file_size)
            if entry is not None:
                entries.append(entry)

    entries.sort(key=lambda e: e.relpath)
    return entries


def _make_entry(root: Path, rel: str, max_file_size: int) -> FileEntry | None:
    abspath = root / rel
    try:
        size = abspath.stat().st_size
    except OSError:
        return None
    ext = os.path.splitext(rel)[1].lower()
    if ext in BINARY_EXTENSIONS:
        return FileEntry(rel, abspath, size, None, 0, skip_reason="binary file")
    if size > max_file_size:
        mb = max_file_size / 1_000_000
        return FileEntry(
            rel, abspath, size, None, size // 4,
            skip_reason=f"too large (> {mb:g} MB limit)",
        )
    try:
        text = abspath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return FileEntry(rel, abspath, size, None, 0, skip_reason="unreadable")
    return FileEntry(rel, abspath, size, text, count_tokens(text))


def git_change_counts(root: Path, timeout: float = 10.0) -> dict[str, int]:
    """Map each tracked file to how many commits touched it.

    Returns an empty dict outside a git repository, when git is missing, or on
    timeout - callers must treat it as best-effort metadata.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "log", "--name-only", "--pretty=format:"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if proc.returncode != 0 or not proc.stdout:
        return {}
    counts: dict[str, int] = {}
    for line in proc.stdout.splitlines():
        line = line.strip().replace("\\", "/")
        if line:
            counts[line] = counts.get(line, 0) + 1
    return counts
