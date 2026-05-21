"""Two-way translation between the play_context wizard form and the single 64-char DB column.

The form has a preset radio (one of `PLAY_CONTEXT_MAIN_OPTIONS` or "Something else") plus
an optional detail textbox. Storage is one column: either the preset alone, the preset
plus separator plus detail, or just the freeform text if the user picked "Something else".
`split_play_context` reverses the encoding when prefilling the form on subsequent visits.
"""

from __future__ import annotations

from app.onboarding_constants import (
    PLAY_CONTEXT_DB_MAX_LEN,
    PLAY_CONTEXT_DETAIL_SEPARATOR,
    PLAY_CONTEXT_MAIN_OPTIONS,
    PLAY_CONTEXT_OTHER_VALUE,
)

__all__ = ["split_play_context", "merge_play_context"]


def split_play_context(stored: str | None) -> tuple[str, str]:
    """Split a stored value back into ``(preset_radio_value, detail_text)`` for form prefill.

    Preset is ``""`` (empty stored value), one of `PLAY_CONTEXT_MAIN_OPTIONS`, or
    `PLAY_CONTEXT_OTHER_VALUE` for unmatched / legacy text. We sort known options by length
    descending so e.g. "Small group" wouldn't accidentally match "Small group (regulars)".
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
    """Combine a preset + optional detail back into a single ≤64-char string for DB storage.

    Returns ``None`` when both inputs are empty (so the column stays NULL). The "Something
    else" sentinel emits just the detail; an unknown preset is treated as empty so a stale
    or tampered form value can't be stored verbatim.
    """
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
