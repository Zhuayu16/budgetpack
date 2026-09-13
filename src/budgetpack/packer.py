"""Greedy budget packing: whole files first, then truncate one high-value file."""

from __future__ import annotations

from dataclasses import dataclass

from .prioritize import ScoredFile
from .scanner import FileEntry
from .tokens import count_tokens, truncate_to_tokens

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
                shown = truncate_to_tokens(entry.text, remaining)
                used = count_tokens(shown)
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
