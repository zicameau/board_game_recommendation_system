"""Read category / mechanic label lists from the active bundle and clean BGG-style strings.

Two purposes living together because they all draw from the same parquet:

1. **Onboarding chip options.** `load_category_options` / `load_mechanic_options` produce
   the deduped, case-insensitively sorted strings rendered as chips on the categories /
   mechanics wizard steps. The category function prefers an explicit `categories.json` in
   the bundle when present; both fall back to scanning the parquet's BGG-style columns.

2. **Display cleanup.** `plain_description` strips HTML tags and decodes HTML entities so
   BGG descriptions render as plain text. `labels_from_cell` and `first_category_label`
   parse the BGG list-or-string cells consistently.
"""

from __future__ import annotations

import ast
import html
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.config import settings

_DEFAULT_CATEGORIES = ["Strategy", "Family", "Thematic", "Party", "Wargames"]
_DEFAULT_MECHANICS = ["Deck Building", "Worker Placement", "Dice", "Negotiation"]


def _normalize_label(s: str) -> str:
    """Trim whitespace and strip a single layer of surrounding double quotes."""
    t = str(s).strip()
    if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
        t = t[1:-1].strip()
    return t.strip()


def _iter_labels_in_cell(val: Any) -> list[str]:
    """Return a list of label strings from one BGG-style cell.

    Cells in BGG-exported parquets are inconsistent: sometimes a Python list, sometimes a
    `str(list)` literal that needs `ast.literal_eval`, sometimes a single string, and
    occasionally a numpy ndarray. NaN / None yield `[]`.
    """
    if val is None:
        return []
    if isinstance(val, float) and np.isnan(val):
        return []
    if isinstance(val, np.ndarray):
        val = val.tolist()
    if isinstance(val, (list, tuple)):
        return [_normalize_label(str(x)) for x in val if str(x).strip()]
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return []
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = ast.literal_eval(s)
                if isinstance(parsed, (list, tuple)):
                    return [_normalize_label(str(x)) for x in parsed if str(x).strip()]
            except (SyntaxError, ValueError):
                pass
        return [_normalize_label(s)]
    return [_normalize_label(str(val))]


def first_category_label(val: Any) -> str:
    """First BGG category in a cell — used to diversify onboarding seed games."""
    labs = _iter_labels_in_cell(val)
    return labs[0] if labs else "Other"


def _unique_sorted_from_column(df: pd.DataFrame | None, col: str) -> list[str]:
    """Collect every label across one BGG-style column, dedupe, sort case-insensitively."""
    if df is None or col not in df.columns:
        return []
    seen: set[str] = set()
    for val in df[col]:
        for lab in _iter_labels_in_cell(val):
            if lab:
                seen.add(lab)
    return sorted(seen, key=str.casefold)


def load_category_options() -> list[str]:
    """Return the sorted category labels for the categories chip step.

    Preference order: explicit `categories.json` in the bundle, then unique values from
    the bundle parquet's `boardgamecategory` column, then a small hardcoded default list.
    """
    bundle = Path(settings.MODEL_BUNDLE_PATH).resolve() / settings.MODEL_VERSION
    jp = bundle / "categories.json"
    if jp.is_file():
        try:
            raw = json.loads(jp.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                labels = {_normalize_label(str(x)) for x in raw if str(x).strip()}
                if labels:
                    return sorted(labels, key=str.casefold)
        except (json.JSONDecodeError, OSError):
            pass

    from app.recommenders.registry import registry

    df = getattr(registry.recommender, "games_meta", None)
    found = _unique_sorted_from_column(df, "boardgamecategory")
    return found if found else list(_DEFAULT_CATEGORIES)


def load_mechanic_options() -> list[str]:
    """Return the sorted mechanic labels (parquet `boardgamemechanic` column → hardcoded fallback)."""
    from app.recommenders.registry import registry

    df = getattr(registry.recommender, "games_meta", None)
    found = _unique_sorted_from_column(df, "boardgamemechanic")
    return found if found else list(_DEFAULT_MECHANICS)


_HTML_TAG = re.compile(r"<[^>]+>")


def plain_description(raw: str | None, max_len: int = 480) -> str:
    """Strip HTML tags AND decode entities from BGG descriptions for safe short display.

    BGG ships descriptions with both real tags (<br/>) and HTML entities (&quot;, &amp;, &#10;).
    Tags are stripped first; then entities are unescaped so quotes/ampersands/newlines render as
    real characters; then whitespace is collapsed.
    """
    t = _HTML_TAG.sub(" ", str(raw or ""))
    t = html.unescape(t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


def labels_from_cell(val: Any) -> list[str]:
    """Normalized BGG-style labels from a bundle metadata cell (list or string)."""
    return _iter_labels_in_cell(val)
