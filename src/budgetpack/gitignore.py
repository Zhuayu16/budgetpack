"""A pragmatic subset of .gitignore semantics.

Supported: blank lines, ``#`` comments, ``!`` negation, trailing ``/`` for
dir-only rules, leading or middle ``/`` anchoring, ``**`` cross-directory
globs, and the ``*`` / ``?`` single-level wildcards.

Known limitation: git can re-include a file inside an ignored directory with a
negated rule; because we prune ignored directories while walking, we never
descend far enough to apply such negations. Everything else behaves as
expected for the vast majority of real-world .gitignore files.

The same compiler also powers CLI ``--include`` / ``--exclude`` globs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class IgnorePattern:
    regex: re.Pattern
    negated: bool
    dir_only: bool
    raw: str

    def matches(self, relpath: str, is_dir: bool) -> bool:
        m = self.regex.search(relpath)
        if m is None:
            return False
        if self.dir_only and not is_dir:
            # `build/` ignores the directory itself plus everything under it:
            # for a file path the match must end before the path does.
            return m.end() < len(relpath)
        return True


def _translate(pattern: str) -> str:
    out: list[str] = []
    i, n = 0, len(pattern)
    while i < n:
        c = pattern[i]
        if c == "\\" and i + 1 < n:
            out.append(re.escape(pattern[i + 1]))
            i += 2
        elif c == "*":
            if pattern.startswith("**/", i):
                out.append("(?:[^/]+/)*")
                i += 3
            elif pattern.startswith("**", i):
                out.append(".*")
                i += 2
            else:
                out.append("[^/]*")
                i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return "".join(out)


def compile_ignore_line(raw: str) -> IgnorePattern | None:
    line = raw.rstrip("\r\n")
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if line.startswith("\\#") or line.startswith("\\!"):
        line = line[1:]  # un-escape a literal '#' or '!' at the start
    negated = line.startswith("!")
    if negated:
        line = line[1:]
        if not line.strip():
            return None
    dir_only = line.endswith("/")
    line = line.rstrip("/")
    anchored = "/" in line
    line = line.lstrip("/")
    if not line:
        return None
    body = _translate(line)
    rx = f"^{body}(?:/|$)" if anchored else f"(?:^|/){body}(?:/|$)"
    try:
        return IgnorePattern(re.compile(rx), negated, dir_only, raw)
    except re.error:
        return None


def parse_gitignore_text(text: str) -> list[IgnorePattern]:
    patterns = []
    for line in text.splitlines():
        compiled = compile_ignore_line(line)
        if compiled is not None:
            patterns.append(compiled)
    return patterns


class IgnoreStack:
    """Layers of .gitignore files; deeper files take precedence over shallower."""

    def __init__(self) -> None:
        # list of (base_dir_posix_or_empty, patterns); root pushed first
        self._layers: list[tuple[str, list[IgnorePattern]]] = []

    def push(self, base: str, text: str) -> None:
        self._layers.append((base.strip("/"), parse_gitignore_text(text)))

    def ignored(self, relpath: str, is_dir: bool) -> bool:
        """Decide whether *relpath* (posix, relative to the scan root) is ignored."""
        for base, patterns in reversed(self._layers):
            if base:
                prefix = base + "/"
                if not relpath.startswith(prefix):
                    continue
                sub = relpath[len(prefix) :]
            else:
                sub = relpath
            for pat in reversed(patterns):
                if pat.matches(sub, is_dir):
                    return not pat.negated
        return False


# Built-in hygiene rules, injected at the lowest precedence so a user's own
# .gitignore (or --exclude) can always override them.
DEFAULT_EXCLUDES = """\
.git/
.hg/
.svn/
node_modules/
__pycache__/
.venv/
venv/
.tox/
.mypy_cache/
.pytest_cache/
.ruff_cache/
.eggs/
*.egg-info/
dist/
build/
target/
.idea/
.vscode/
.next/
.nuxt/
coverage/
htmlcov/
*.lock
package-lock.json
pnpm-lock.yaml
yarn.lock
*.min.js
*.min.css
*.map
*.snap
.DS_Store
Thumbs.db
"""
