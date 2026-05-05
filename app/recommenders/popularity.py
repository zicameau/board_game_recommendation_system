"""Popularity-based recommender — §5.5 P1 fallback."""

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
        return {
            "model_type": self.model_type,
            "version": self.version,
            "n_items": int(len(self.games_meta)),
            "device": "cpu",
        }
