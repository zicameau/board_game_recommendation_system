"""Enrich top-k recommendation rows for the home UI (scores, copy, imagery)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.db.models.onboarding import OnboardingSelection
from app.services.bundle_taxonomy import labels_from_cell, plain_description


def normalize_match_scores(raw_scores: list[float]) -> list[dict[str, float]]:
    """Map raw dot-product scores to a 0–100% band and 1–10 scale within this result set."""
    if not raw_scores:
        return []
    lo, hi = min(raw_scores), max(raw_scores)
    span = hi - lo
    out: list[dict[str, float]] = []
    for s in raw_scores:
        if span <= 1e-12:
            pct_f = 100.0
            ten = 10.0
        else:
            t = (float(s) - lo) / span
            pct_f = t * 100.0
            ten = 1.0 + 9.0 * t
        out.append({"match_pct": round(pct_f), "match_10": round(ten, 1)})
    return out


def thumbnail_url_from_row(row: pd.Series) -> str | None:
    raw = row.get("thumbnail") or row.get("image") or row.get("imageurl") or ""
    u = str(raw).strip()
    if not u or u.lower() in {"nan", "none"}:
        return None
    if u.startswith("//"):
        return "https:" + u
    if u.startswith(("http://", "https://")):
        return u
    return u


def explain_recommendation(sel: OnboardingSelection, row: pd.Series) -> str:
    """Short justification from onboarding prefs + taxonomy vs this game."""
    liked_cats = {str(x).strip() for x in (sel.liked_categories or []) if str(x).strip()}
    liked_mech = {str(x).strip() for x in (sel.liked_mechanics or []) if str(x).strip()}
    dis_cats = {str(x).strip() for x in (sel.disliked_categories or []) if str(x).strip()}
    dis_mech = {str(x).strip() for x in (sel.disliked_mechanics or []) if str(x).strip()}

    game_cats = set(labels_from_cell(row.get("boardgamecategory")))
    game_mech = set(labels_from_cell(row.get("boardgamemechanic")))

    hit_cat = sorted(liked_cats & game_cats, key=str.casefold)[:4]
    hit_mech = sorted(liked_mech & game_mech, key=str.casefold)[:3]
    avoid_cat = sorted(dis_cats & game_cats, key=str.casefold)[:2]
    avoid_mech = sorted(dis_mech & game_mech, key=str.casefold)[:2]

    parts: list[str] = []
    if hit_cat:
        parts.append("Matches categories you enjoy: " + ", ".join(hit_cat) + ".")
    if hit_mech:
        parts.append("Uses mechanics you like: " + ", ".join(hit_mech) + ".")
    if avoid_cat:
        parts.append(
            "Heads up: it’s also tagged with "
            + ", ".join(avoid_cat)
            + ", which you said you’d rather avoid — but it still scored well, so worth a look."
        )
    elif avoid_mech:
        parts.append(
            "It uses "
            + ", ".join(avoid_mech)
            + ", which you marked as a turn-off — but it scored highly enough that you might still enjoy it."
        )

    if not parts:
        parts.append(
            "Picked because it has a similar feel to the games you rated highest during onboarding."
        )

    return " ".join(parts)


def build_recommendation_items(
    pairs: list[tuple[int, float]],
    games_meta: pd.DataFrame | None,
    sel: OnboardingSelection,
    desc_max_len: int = 360,
) -> list[dict[str, Any]]:
    """Produce template-ready dicts with blurbs, thumbnails, normalized scores."""
    if not pairs:
        return []
    scores = [p[1] for p in pairs]
    norms = normalize_match_scores(scores)
    items: list[dict[str, Any]] = []
    for i, (game_idx, raw_score) in enumerate(pairs):
        title = f"Game {game_idx}"
        bgg = int(game_idx)
        description = ""
        thumb: str | None = None
        row_for_explain = pd.Series(dtype=object)

        if games_meta is not None:
            m = games_meta[games_meta["game_idx"] == game_idx]
            if len(m) > 0:
                row = m.iloc[0]
                row_for_explain = row
                title = str(row.get("title") or row.get("primary") or title)
                bgg = int(row.get("bgg_id", row.get("id", game_idx)))
                description = plain_description(row.get("description"), max_len=desc_max_len)
                thumb = thumbnail_url_from_row(row)

        n = norms[i]
        why_text = explain_recommendation(sel, row_for_explain)

        items.append(
            {
                "game_idx": int(game_idx),
                "title": title,
                "bgg_id": bgg,
                "raw_score": float(raw_score),
                "match_pct": int(n["match_pct"]),
                "match_10": float(n["match_10"]),
                "description": description,
                "thumbnail_url": thumb,
                "why": why_text,
            }
        )
    return items
