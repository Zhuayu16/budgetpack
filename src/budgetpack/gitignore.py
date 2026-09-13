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
    # Fast-path classification. Most real-world rules are plain names
    # (``node_modules``) or simple suffixes (``*.log``); matching those with
    # string ops instead of regex search keeps scanning large trees fast.
    # The regex is kept as the reference semantics for every kind.
    kind: str = "regex"  # "basename" | "suffix" | "anchored-literal" | "regex"
    literal: str = ""

    def matches(self, relpath: str, is_dir: bool) -> bool:
        if self.kind == "basename":
            return self._match_basename(relpath, is_dir)
        if self.kind == "suffix":
            return self._match_suffix(relpath, is_dir)
        if self.kind == "anchored-literal":
            return self._match_anchored(relpath, is_dir)
        return self._match_regex(relpath, is_dir)

    def _accepted(self, pos: int, relpath: str, is_dir: bool) -> bool:
        # dir_only rules ignore the directory and everything below it, but not
        # a file that merely shares the name: for a file the match must end
        # before the path does.
        if self.dir_only and not is_dir:
            return pos < len(relpath)
        return True

    def _match_basename(self, relpath: str, is_dir: bool) -> bool:
        name = self.literal
        if relpath == name:
            return self._accepted(len(name), relpath, is_dir)
        if relpath.startswith(name + "/"):
            return self._accepted(len(name) + 1, relpath, is_dir)
        idx = relpath.find("/" + name + "/")
        if idx >= 0:
            return self._accepted(idx + 1 + len(name) + 1, relpath, is_dir)
        if relpath.endswith("/" + name):
            return self._accepted(len(relpath), relpath, is_dir)
        return False

    def _match_suffix(self, relpath: str, is_dir: bool) -> bool:
        # `*.log` is `(?:^|/)[^/]*\.log(?:/|$)`: the glob cannot cross "/", so
        # the match is exactly "some full component ends with the suffix".
        suffix = self.literal
        start = 0
        while True:
            slash = relpath.find("/", start)
            comp_end = len(relpath) if slash < 0 else slash
            if (
                comp_end - start >= len(suffix)
                and relpath.endswith(suffix, start, comp_end)
                and self._accepted(comp_end, relpath, is_dir)
            ):
                return True
            if slash < 0:
                return False
            start = slash + 1

    def _match_anchored(self, relpath: str, is_dir: bool) -> bool:
        name = self.literal
        if relpath == name:
            return self._accepted(len(name), relpath, is_dir)
        if relpath.startswith(name + "/"):
            return self._accepted(len(name) + 1, relpath, is_dir)
        return False

    def _match_regex(self, relpath: str, is_dir: bool) -> bool:
        m = self.regex.search(relpath)
        if m is None:
            return False
        return self._accepted(m.end(), relpath, is_dir)


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
        regex = re.compile(rx)
    except re.error:
        return None

    kind, literal = "regex", ""
    if "\\" not in line:
        if "*" not in line and "?" not in line:
            kind = "anchored-literal" if anchored else "basename"
            literal = line
        elif (
            not dir_only
            and not anchored
            and line.startswith("*")
            and not any(c in line[1:] for c in "*?/")
        ):
            kind, literal = "suffix", line[1:]
    return IgnorePattern(regex, negated, dir_only, raw, kind, literal)


def parse_gitignore_text(text: str) -> list[IgnorePattern]:
    patterns = []
    for line in text.splitlines():
        compiled = compile_ignore_line(line)
        if compiled is not None:
            patterns.append(compiled)
    return patterns


class _Layer:
    """One parsed .gitignore file, with patterns bucketed for fast matching.

    Within a file the LAST matching line wins; buckets keep the original line
    index so `ignored()` can still apply that rule across buckets.
    """

    __slots__ = ("patterns", "literal", "suffixes", "other")

    def __init__(self, patterns: list[IgnorePattern]) -> None:
        self.patterns = patterns
        self.literal: dict[str, list[tuple[int, IgnorePattern]]] = {}
        self.suffixes: list[tuple[int, str, IgnorePattern]] = []
        self.other: list[tuple[int, IgnorePattern]] = []
        for idx, pat in enumerate(patterns):
            if pat.kind == "basename":
                self.literal.setdefault(pat.literal, []).append((idx, pat))
            elif pat.kind == "suffix":
                self.suffixes.append((idx, pat.literal, pat))
            else:
                self.other.append((idx, pat))


class IgnoreStack:
    """Layers of .gitignore files; deeper files take precedence over shallower."""

    def __init__(self) -> None:
        # list of (base_dir_posix_or_empty, layer); root pushed first
        self._layers: list[tuple[str, _Layer]] = []

    def push(self, base: str, text: str) -> None:
        self._layers.append((base.strip("/"), _Layer(parse_gitignore_text(text))))

    def ignored(self, relpath: str, is_dir: bool) -> bool:
        """Decide whether *relpath* (posix, relative to the scan root) is ignored."""
        comps = relpath.split("/")
        for base, layer in reversed(self._layers):
            if base:
                prefix = base + "/"
                if not relpath.startswith(prefix):
                    continue
                sub = relpath[len(prefix) :]
                sub_comps = comps[len(base.split("/")) :]
            else:
                sub, sub_comps = relpath, comps

            best_idx = -1
            ignore = False
            n = len(sub)
            last = len(sub_comps) - 1

            for d, comp in enumerate(sub_comps):
                for idx, pat in layer.literal.get(comp, ()):
                    pos_end = n if d == last else n - len("/".join(sub_comps[d + 1 :])) - 1
                    if pat._accepted(pos_end, sub, is_dir) and idx > best_idx:
                        best_idx, ignore = idx, not pat.negated

            for idx, suffix, pat in layer.suffixes:
                if (
                    any(len(c) >= len(suffix) and c.endswith(suffix) for c in sub_comps)
                    and idx > best_idx
                ):
                    best_idx, ignore = idx, not pat.negated

            for idx, pat in layer.other:
                if pat.matches(sub, is_dir) and idx > best_idx:
                    best_idx, ignore = idx, not pat.negated

            if best_idx >= 0:
                return ignore
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
