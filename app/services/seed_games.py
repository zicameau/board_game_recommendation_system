"""Onboarding seed list: same games for every user — deterministic from each bundle's games_meta.

Selection spans the BGG complexity axis (averageweight 1-5) so the user's ratings
inform the model about where on the complexity dimension they prefer, in addition
to which genres they enjoy. Within each complexity bucket, picks popular and
category-diverse games.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.services.bundle_taxonomy import first_category_label

# Same model version + same parquet -> same indices for all users (no randomness).
SEED_GAME_COUNT = 10
# Prefer games with enough BGG ratings so seeds are household names.
MIN_USERS_RATED = 5000

# Complexity buckets on BGG averageweight (1.0 = lightest, 5.0 = heaviest).
# Five buckets so we can pick 2 games per bucket for SEED_GAME_COUNT = 10.
COMPLEXITY_BUCKETS: list[tuple[float, float]] = [
    (1.0, 2.0),   # light: party / kids / quick fillers
    (2.0, 2.5),   # medium-light: gateway games
    (2.5, 3.0),   # medium: classic hobby games
    (3.0, 3.5),   # medium-heavy: strategy / euro
    (3.5, 5.01),  # heavy: long strategy, wargames (upper end inclusive)
]
PER_BUCKET = SEED_GAME_COUNT // len(COMPLEXITY_BUCKETS)  # 2


def _category_for_row(row: Any, has_cat: bool) -> str:
    if not has_cat:
        return "Other"
    if hasattr(row, "get"):
        return first_category_label(row.get("boardgamecategory"))
    return first_category_label(row["boardgamecategory"])


def _legacy_pick(work: pd.DataFrame) -> list[int]:
    """Fallback when averageweight column is missing — popularity + category diversity."""
    pool = work[work["_ur"] >= MIN_USERS_RATED].copy()
    if len(pool) < SEED_GAME_COUNT:
        pool = work.copy()
    pool = pool.sort_values(["_ur", "_gi"], ascending=[False, True], kind="mergesort")
    has_cat = "boardgamecategory" in pool.columns

    picked: list[int] = []
    picked_set: set[int] = set()
    categories_used: set[str] = set()

    for _, row in pool.iterrows():
        if len(picked) >= SEED_GAME_COUNT:
            break
        gi = int(row["_gi"])
        if gi in picked_set:
            continue
        cat = _category_for_row(row, has_cat)
        if cat not in categories_used:
            picked.append(gi)
            picked_set.add(gi)
            categories_used.add(cat)

    for _, row in pool.iterrows():
        if len(picked) >= SEED_GAME_COUNT:
            break
        gi = int(row["_gi"])
        if gi not in picked_set:
            picked.append(gi)
            picked_set.add(gi)

    return picked[:SEED_GAME_COUNT]


def _pick_from_bucket(
    bucket_df: pd.DataFrame,
    n: int,
    already_picked: set[int],
    has_cat: bool,
) -> list[int]:
    """Pick n games from a complexity bucket, preferring category diversity."""
    picked: list[int] = []
    bucket_cats_used: set[str] = set()

    # First pass: prefer category diversity within the bucket.
    for _, row in bucket_df.iterrows():
        if len(picked) >= n:
            break
        gi = int(row["_gi"])
        if gi in already_picked:
            continue
        cat = _category_for_row(row, has_cat)
        if cat in bucket_cats_used:
            continue
        picked.append(gi)
        bucket_cats_used.add(cat)

    # Second pass: fill remaining slots with most popular unpicked games.
    for _, row in bucket_df.iterrows():
        if len(picked) >= n:
            break
        gi = int(row["_gi"])
        if gi in already_picked or gi in picked:
            continue
        picked.append(gi)

    return picked


def pick_seed_game_indices(df: pd.DataFrame | None) -> list[int]:
    """
    Return up to SEED_GAME_COUNT game_idx values, spread across complexity buckets.

    Strategy:
      1. Bucket games by averageweight (5 buckets covering 1.0-5.0).
      2. Within each bucket, sort by popularity and pick PER_BUCKET games,
         preferring category diversity within the bucket.
      3. If a bucket is short, redistribute slots to the most-populated buckets.

    Deterministic: stable sort by (averageweight bucket, usersrated desc, game_idx asc).
    Falls back to legacy popularity+category logic if averageweight is missing.
    """
    if df is None or df.empty or "game_idx" not in df.columns:
        return []

    work = df.drop_duplicates(subset=["game_idx"], keep="first").copy()

    # Normalize game_idx; required for any path.
    work["_gi"] = pd.to_numeric(work["game_idx"], errors="coerce")
    work = work.dropna(subset=["_gi"])
    work["_gi"] = work["_gi"].astype(int)

    # Without usersrated, the only stable order is by game_idx ascending.
    if "usersrated" not in work.columns:
        return sorted(int(x) for x in work["_gi"].tolist())[:SEED_GAME_COUNT]

    work["_ur"] = pd.to_numeric(work["usersrated"], errors="coerce").fillna(0.0).astype(float)

    # Fall back to legacy logic if averageweight is missing — preserves behavior on
    # bundles that don't ship the complexity column (e.g., the popularity fixture).
    if "averageweight" not in work.columns:
        return _legacy_pick(work)

    work["_w"] = pd.to_numeric(work["averageweight"], errors="coerce").fillna(0.0).astype(float)

    pool = work[work["_ur"] >= MIN_USERS_RATED].copy()
    if len(pool) < SEED_GAME_COUNT:
        pool = work.copy()

    # Pre-sort the entire pool by popularity (desc) + game_idx (asc) for determinism.
    pool = pool.sort_values(["_ur", "_gi"], ascending=[False, True], kind="mergesort")
    has_cat = "boardgamecategory" in pool.columns

    picked: list[int] = []
    picked_set: set[int] = set()

    # Pass 1: try to take PER_BUCKET from each bucket.
    for lo, hi in COMPLEXITY_BUCKETS:
        bucket_df = pool[(pool["_w"] >= lo) & (pool["_w"] < hi)]
        chosen = _pick_from_bucket(bucket_df, PER_BUCKET, picked_set, has_cat)
        for gi in chosen:
            if gi not in picked_set:
                picked.append(gi)
                picked_set.add(gi)

    # Pass 2: if any bucket was short, fill remaining slots from the overall pool
    # by popularity. Guarantees SEED_GAME_COUNT output when the pool is large enough.
    if len(picked) < SEED_GAME_COUNT:
        for _, row in pool.iterrows():
            if len(picked) >= SEED_GAME_COUNT:
                break
            gi = int(row["_gi"])
            if gi not in picked_set:
                picked.append(gi)
                picked_set.add(gi)

    return picked[:SEED_GAME_COUNT]
