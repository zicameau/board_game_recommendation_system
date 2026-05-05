"""Map onboarding labels → recommender inputs; lazy refit user embedding — §5.15.5."""

from __future__ import annotations

import logging
import uuid
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.onboarding import OnboardingSelection
from app.db.models.user_embedding import UserEmbedding
from app.recommenders.registry import ModelRegistry

logger = logging.getLogger(__name__)


def map_game_ratings_to_signed(
    game_ratings: list[dict[str, Any]],
) -> tuple[list[int], list[int], list[float]]:
    """§5.3.2 default mapping."""
    positives: list[int] = []
    negatives: list[int] = []
    weights: list[float] = []
    for row in game_ratings:
        label = row.get("label", "")
        gi = int(row["game_idx"])
        if label == "never_played":
            continue
        if label == "love":
            positives.append(gi)
            weights.append(1.0)
        elif label == "like":
            positives.append(gi)
            weights.append(0.5)
        elif label == "dislike":
            negatives.append(gi)
            weights.append(-0.5)
        elif label == "hate":
            negatives.append(gi)
            weights.append(-1.0)
    return positives, negatives, weights


def get_or_refit_user_embedding(
    user_id: uuid.UUID,
    db: Session,
    reg: ModelRegistry,
) -> np.ndarray:
    active_version = settings.MODEL_VERSION
    row = db.get(UserEmbedding, user_id)
    if row is not None and row.model_version == active_version:
        return np.asarray(row.embedding, dtype=np.float32)

    sel = db.get(OnboardingSelection, user_id)
    if sel is None:
        raise ValueError("onboarding_required")

    pos, neg, wts = map_game_ratings_to_signed(sel.game_ratings)
    user_emb = reg.fit_user_embedding(pos, neg, wts)

    merged = UserEmbedding(
        user_id=user_id,
        embedding=user_emb.tolist(),
        model_version=active_version,
    )
    db.merge(merged)
    db.commit()
    return user_emb


def exclude_indices_from_selections(game_ratings: list[dict[str, Any]]) -> set[int]:
    """Games user rated (non never_played) excluded from recommendations."""
    return {int(r["game_idx"]) for r in game_ratings if r.get("label") != "never_played"}
