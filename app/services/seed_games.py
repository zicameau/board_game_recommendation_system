"""Onboarding seed list: same 10 games for every user — deterministic from each bundle's games_meta."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.services.bundle_taxonomy import first_category_label

# Same model version + same parquet ⇒ same indices for all users (no randomness).
SEED_GAME_COUNT = 10
# Prefer games with enough BGG ratings so seeds are household names.
MIN_USERS_RATED = 5000


def pick_seed_game_indices(df: pd.DataFrame | None) -> list[int]:
    """
    Return up to SEED_GAME_COUNT game_idx values: high usersrated first,
    greedy spread across primary (first) BGG category, then fill by popularity.

    Deterministic: stable sort by (usersrated desc, game_idx asc).
    """
    if df is None or df.empty or "game_idx" not in df.columns:
        return []

    work = df.drop_duplicates(subset=["game_idx"], keep="first").copy()

    if "usersrated" not in work.columns:
        g = sorted(int(x) for x in work["game_idx"].tolist())
        return g[:SEED_GAME_COUNT]

    work["_ur"] = pd.to_numeric(work["usersrated"], errors="coerce").fillna(0.0).astype(float)
    work["_gi"] = pd.to_numeric(work["game_idx"], errors="coerce")
    work = work.dropna(subset=["_gi"])
    work["_gi"] = work["_gi"].astype(int)

    pool = work[work["_ur"] >= MIN_USERS_RATED].copy()
    if len(pool) < SEED_GAME_COUNT:
        pool = work.copy()

    pool = pool.sort_values(["_ur", "_gi"], ascending=[False, True], kind="mergesort")
    has_cat = "boardgamecategory" in pool.columns

    picked: list[int] = []
    picked_set: set[int] = set()
    categories_used: set[str] = set()

    def category_for_row(row: Any) -> str:
        if not has_cat:
            return "Other"
        if hasattr(row, "get"):
            return first_category_label(row.get("boardgamecategory"))
        return first_category_label(row["boardgamecategory"])

    for _, row in pool.iterrows():
        if len(picked) >= SEED_GAME_COUNT:
            break
        gi = int(row["_gi"])
        if gi in picked_set:
            continue
        cat = category_for_row(row)
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
