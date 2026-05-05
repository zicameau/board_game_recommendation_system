"""Load category / mechanic label lists from the active model bundle (JSON + parquet fallbacks)."""

from __future__ import annotations

import ast
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
    t = str(s).strip()
    if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
        t = t[1:-1].strip()
    return t.strip()


def _iter_labels_in_cell(val: Any) -> list[str]:
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
    if df is None or col not in df.columns:
        return []
    seen: set[str] = set()
    for val in df[col]:
        for lab in _iter_labels_in_cell(val):
            if lab:
                seen.add(lab)
    return sorted(seen, key=str.casefold)


def load_category_options() -> list[str]:
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
    from app.recommenders.registry import registry

    df = getattr(registry.recommender, "games_meta", None)
    found = _unique_sorted_from_column(df, "boardgamemechanic")
    return found if found else list(_DEFAULT_MECHANICS)


_HTML_TAG = re.compile(r"<[^>]+>")


def plain_description(raw: str | None, max_len: int = 480) -> str:
    """Strip basic HTML from BGG descriptions for safe short display."""
    t = _HTML_TAG.sub(" ", str(raw or ""))
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


def labels_from_cell(val: Any) -> list[str]:
    """Normalized BGG-style labels from a bundle metadata cell (list or string)."""
    return _iter_labels_in_cell(val)
