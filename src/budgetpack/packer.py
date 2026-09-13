"""Greedy budget packing: whole files first, then truncate one high-value file.

Two-stage design: :func:`pack` makes include/omit decisions from cheap
size-based token estimates without touching file contents;
:func:`materialize` then reads only the chosen files, re-checks the budget
with exact token counts, and produces the final result. On large repositories
this skips decoding the thousands of files that would be omitted anyway.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import tokens as _tokens
from .prioritize import ScoredFile
from .scanner import FileEntry

# Don't bother truncating unless at least this many tokens of room are left.
MIN_TRUNCATE_TOKENS = 1000


@dataclass
class PackedFile:
    entry: FileEntry
    included_tokens: int
    truncated: bool = False
    note: str | None = None
    score: float = 0.0  # kept so render can restore priority order


@dataclass
class OmittedFile:
    entry: FileEntry
    reason: str
    score: float = 0.0


@dataclass
class PackResult:
    packed: list[PackedFile]
    omitted: list[OmittedFile]
    budget: int
    used: int

    @property
    def found_count(self) -> int:
        return len(self.packed) + len(self.omitted)


@dataclass
class ReadStats:
    """What materialize actually touched on disk."""

    files_read: int
    bytes_read: int


def pack(scored: list[ScoredFile], budget: int) -> PackResult:
    """Fill *budget* tokens with the highest-priority files.

    Pass 1 greedily includes whole files in priority order. Pass 2, if at least
    :data:`MIN_TRUNCATE_TOKENS` remain, truncates the highest-priority file that
    did not fit so the budget is never left unused when real content is missing.
    """
    remaining = max(0, budget)
    packed: list[PackedFile] = []
    omitted: list[OmittedFile] = []

    for s in scored:
        entry = s.entry
        if entry.skip_reason:
            omitted.append(OmittedFile(entry, entry.skip_reason, s.score))
        elif entry.tokens <= remaining:
            packed.append(PackedFile(entry, entry.tokens, score=s.score))
            remaining -= entry.tokens
        else:
            omitted.append(
                OmittedFile(
                    entry,
                    f"needs {entry.tokens:,} tokens, only {remaining:,} left in budget",
                    s.score,
                )
            )

    if remaining >= MIN_TRUNCATE_TOKENS:
        for idx, om in enumerate(omitted):
            entry = om.entry
            if entry.skip_reason is None and entry.text is not None and entry.tokens > remaining:
                shown = _tokens.truncate_to_tokens(entry.text, remaining)
                used = _tokens.count_tokens(shown)
                packed.append(
                    PackedFile(
                        entry,
                        used,
                        truncated=True,
                        note=f"truncated - showing first {used:,} of {entry.tokens:,} tokens",
                        score=om.score,
                    )
                )
                omitted.pop(idx)
                remaining -= used
                break

    # Restore priority order for presentation (truncation appended out of order).
    packed.sort(key=lambda p: (-p.score, p.entry.relpath))
    used = sum(p.included_tokens for p in packed)
    return PackResult(packed, omitted, budget, used)


def materialize(plan: PackResult, root: Path, budget: int) -> tuple[PackResult, ReadStats]:
    """Turn a :func:`pack` plan into the final result by reading chosen files.

    Walks the plan in priority order, loads each chosen file, and enforces the
    budget with exact token counts: files that come in over their estimate are
    omitted, and the first one that no longer fits may be truncated to use the
    leftover budget (mirroring :func:`pack`). Returns the final result plus
    read statistics.
    """
    packed: list[PackedFile] = []
    omitted: list[OmittedFile] = list(plan.omitted)
    remaining = max(0, budget)
    truncated_once = False
    files_read = 0
    bytes_read = 0

    for p in plan.packed:
        entry = p.entry
        try:
            text = (root / entry.relpath).read_text(encoding="utf-8", errors="replace")
        except OSError:
            omitted.append(OmittedFile(entry, "unreadable", p.score))
            continue
        files_read += 1
        bytes_read += entry.size
        if "\x00" in text[:8192]:
            omitted.append(OmittedFile(entry, "binary file", p.score))
            continue

        exact = _tokens.count_tokens(text)
        if exact <= remaining:
            packed.append(PackedFile(entry, exact, score=p.score))
            remaining -= exact
        elif not truncated_once and remaining >= MIN_TRUNCATE_TOKENS:
            shown = _tokens.truncate_to_tokens(text, remaining)
            used = _tokens.count_tokens(shown)
            packed.append(
                PackedFile(
                    entry,
                    used,
                    truncated=True,
                    note=f"truncated - showing first {used:,} of {exact:,} tokens",
                    score=p.score,
                )
            )
            remaining -= used
            truncated_once = True
        else:
            omitted.append(
                OmittedFile(
                    entry,
                    f"needs {exact:,} tokens, only {remaining:,} left in budget",
                    p.score,
                )
            )

    used = sum(p.included_tokens for p in packed)
    return (
        PackResult(packed, omitted, budget, used),
        ReadStats(files_read, bytes_read),
    )
