"""Merge/split play_context for DB (≤64 chars) + onboarding chips."""

from __future__ import annotations

from app.onboarding_constants import (
    PLAY_CONTEXT_DB_MAX_LEN,
    PLAY_CONTEXT_DETAIL_SEPARATOR,
    PLAY_CONTEXT_MAIN_OPTIONS,
    PLAY_CONTEXT_OTHER_VALUE,
)

__all__ = ["split_play_context", "merge_play_context"]


def split_play_context(stored: str | None) -> tuple[str, str]:
    """
    Return (preset_radio_value, detail_text).
    preset is "", a MAIN option string, or PLAY_CONTEXT_OTHER_VALUE for unmatched/legacy text.
    """
    if not stored or not str(stored).strip():
        return "", ""
    s = str(stored).strip()[:PLAY_CONTEXT_DB_MAX_LEN]
    sep = PLAY_CONTEXT_DETAIL_SEPARATOR
    for opt in sorted(PLAY_CONTEXT_MAIN_OPTIONS, key=len, reverse=True):
        if s == opt:
            return opt, ""
        if s.startswith(opt + sep):
            return opt, s[len(opt) + len(sep) :].strip()[:PLAY_CONTEXT_DB_MAX_LEN]
    return PLAY_CONTEXT_OTHER_VALUE, s


def merge_play_context(preset: str | None, detail: str | None) -> str | None:
    """Combine preset + optional detail; enforce DB length."""
    p = (preset or "").strip()
    d = (detail or "").strip()
    d = d[:PLAY_CONTEXT_DB_MAX_LEN]

    if p == PLAY_CONTEXT_OTHER_VALUE:
        return d[:PLAY_CONTEXT_DB_MAX_LEN] if d else None

    if p and p not in PLAY_CONTEXT_MAIN_OPTIONS and p != "":
        p = ""

    if not p and not d:
        return None
    if not p:
        return d[:PLAY_CONTEXT_DB_MAX_LEN] if d else None
    if not d:
        return p[:PLAY_CONTEXT_DB_MAX_LEN]
    combined = f"{p}{PLAY_CONTEXT_DETAIL_SEPARATOR}{d}"
    return combined[:PLAY_CONTEXT_DB_MAX_LEN]
