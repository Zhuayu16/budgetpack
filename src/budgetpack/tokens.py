"""Token counting.

Uses the optional `tiktoken` package when it is importable and its BPE data can
be loaded; otherwise falls back to a characters/4 heuristic so the tool keeps
working with zero dependencies and no network access.
"""

from __future__ import annotations

_CHARS_PER_TOKEN = 4.0

_encoding = None
_encoding_checked = False


def _get_encoding():
    global _encoding, _encoding_checked
    if not _encoding_checked:
        _encoding_checked = True
        try:
            import tiktoken  # optional dependency

            _encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:  # noqa: BLE001 - any failure means "use the heuristic"
            _encoding = None
    return _encoding


def backend_name() -> str:
    """Human-readable name of the active counting backend."""
    if _get_encoding() is not None:
        return "tiktoken/cl100k_base"
    return f"heuristic (chars/{_CHARS_PER_TOKEN:.0f})"


def count_tokens(text: str) -> int:
    """Count tokens in *text* with the best available backend."""
    if not text:
        return 0
    enc = _get_encoding()
    if enc is not None:
        return len(enc.encode(text, disallowed_special=()))
    return max(1, round(len(text) / _CHARS_PER_TOKEN))


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Return a prefix of *text* worth at most *max_tokens* tokens."""
    if max_tokens <= 0:
        return ""
    enc = _get_encoding()
    if enc is not None:
        ids = enc.encode(text, disallowed_special=())
        if len(ids) <= max_tokens:
            return text
        return enc.decode(ids[:max_tokens])
    max_chars = int(max_tokens * _CHARS_PER_TOKEN)
    if len(text) <= max_chars:
        return text
    return text[:max_chars]
