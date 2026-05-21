"""Popularity-based recommender — the Phase 1 fallback.

Used when `MODEL_VERSION` points at `popularity-v1-fixture` (the bundle shipped for tests
and as the registry's safety net). Ignores user preferences for *ranking* — every user
sees the same list — but still satisfies the `BaseRecommender` interface so it slots into
the same registry / refit / view-builder pipeline as the real model.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.recommenders.base import BaseRecommender
from app.recommenders.registry import register


@register("popularity")
class PopularityRecommender(BaseRecommender):
    """Ranks games by popularity column in games_meta; ignores user_emb for ranking."""

    model_type = "popularity"
    supported_schema_versions = (1,)

    def __init__(self, games_meta: pd.DataFrame, version: str):
        """Hold the games metadata table; backfill `popularity_score` and `game_idx` if the bundle omits them."""
        self.games_meta = games_meta.reset_index(drop=True)
        self.version = version
        if "popularity_score" not in self.games_meta.columns:
            self.games_meta["popularity_score"] = self.games_meta.get(
                "bayes_average", self.games_meta.get("avg_rating", 5.0)
            )
        if "game_idx" not in self.games_meta.columns:
            self.games_meta.insert(0, "game_idx", range(len(self.games_meta)))

    @classmethod
    def load(cls, model_dir: Path) -> PopularityRecommender:
        """Read `manifest.json` and `games_meta.parquet` from the bundle dir."""
        manifest = json.loads((model_dir / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("schema_version", 1) not in cls.supported_schema_versions:
            raise ValueError("unsupported schema_version")
        games = pd.read_parquet(model_dir / "games_meta.parquet")
        return cls(games, manifest.get("version", "unknown"))

    def fit_user_embedding(
        self,
        positives: list[int],
        negatives: list[int],
        weights: list[float],
    ) -> np.ndarray:
        """Return a small zero vector — popularity ranking doesn't use it, but the contract requires one."""
        if not positives and not negatives:
            raise ValueError("at least one positive or negative required")
        # Fixed small vector for storage contract; not used in top_k for popularity
        return np.zeros(8, dtype=np.float32)

    def top_k(
        self,
        user_emb: np.ndarray,
        exclude: set[int],
        k: int = 10,
    ) -> list[tuple[int, float]]:
        """Return top-k games by `popularity_score`, skipping anything in `exclude`. `user_emb` is ignored."""
        df = self.games_meta
        scores = df["popularity_score"].astype(float).values
        game_idx = df["game_idx"].astype(int).values
        order = np.argsort(-scores, kind="stable")
        out: list[tuple[int, float]] = []
        for i in order:
            gi = int(game_idx[i])
            if gi in exclude:
                continue
            out.append((gi, float(scores[i])))
            if len(out) >= k:
                break
        # If short, fill from remaining (should not happen with enough games)
        return out[:k]

    def healthcheck(self) -> dict:
        """Diagnostics for `/healthz`."""
        return {
            "model_type": self.model_type,
            "version": self.version,
            "n_items": int(len(self.games_meta)),
            "device": "cpu",
        }
