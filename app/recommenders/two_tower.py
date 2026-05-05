"""Two-tower-style dot-product recommender using numpy item embeddings only — no Torch required."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.recommenders.base import BaseRecommender
from app.recommenders.registry import register


@register("two_tower")
class TwoTowerRecommender(BaseRecommender):
    model_type = "two_tower"
    supported_schema_versions = (1,)

    def __init__(
        self,
        item_emb: np.ndarray,
        games_meta: pd.DataFrame,
        version: str,
    ):
        self.item_emb = np.asarray(item_emb, dtype=np.float32)
        self.games_meta = games_meta.reset_index(drop=True)
        self.version = version
        if "game_idx" not in self.games_meta.columns:
            self.games_meta.insert(0, "game_idx", range(len(self.games_meta)))

    @classmethod
    def load(cls, model_dir: Path) -> TwoTowerRecommender:
        manifest = json.loads((model_dir / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("schema_version", 1) not in cls.supported_schema_versions:
            raise ValueError("unsupported schema_version")
        item_emb = np.load(model_dir / "item_embeddings.npy", mmap_mode="r")
        games_meta = pd.read_parquet(model_dir / "games_meta.parquet")
        add_title = "title" not in games_meta.columns and "primary" in games_meta.columns
        add_bgg = "bgg_id" not in games_meta.columns and "id" in games_meta.columns
        if add_title or add_bgg:
            games_meta = games_meta.copy()
            if add_title:
                games_meta["title"] = games_meta["primary"]
            if add_bgg:
                games_meta["bgg_id"] = games_meta["id"]
        return cls(np.array(item_emb), games_meta, manifest.get("version", "unknown"))

    def fit_user_embedding(
        self,
        positives: list[int],
        negatives: list[int],
        weights: list[float],
    ) -> np.ndarray:
        if not positives and not negatives:
            raise ValueError("at least one positive or negative required")
        idxs = list(positives) + list(negatives)
        d = self.item_emb.shape[1]
        acc = np.zeros(d, dtype=np.float64)
        for gi, w in zip(idxs, weights):
            gi = int(gi)
            if 0 <= gi < len(self.item_emb):
                acc += float(w) * self.item_emb[gi]
        nrm = np.linalg.norm(acc)
        if nrm < 1e-12:
            out = np.zeros(d, dtype=np.float32)
            out[0] = 1.0
            return out
        return (acc / nrm).astype(np.float32)

    def top_k(
        self,
        user_emb: np.ndarray,
        exclude: set[int],
        k: int = 10,
    ) -> list[tuple[int, float]]:
        u = np.asarray(user_emb, dtype=np.float32)
        scores = self.item_emb @ u
        for gi in exclude:
            if 0 <= gi < len(scores):
                scores[gi] = -np.inf
        if len(scores) <= k:
            order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
        else:
            part = np.argpartition(-scores, k)[:k]
            order = sorted(part.tolist(), key=lambda i: (-scores[i], i))
        return [(int(i), float(scores[i])) for i in order[:k]]

    def healthcheck(self) -> dict:
        return {
            "model_type": self.model_type,
            "version": self.version,
            "n_items": int(len(self.item_emb)),
            "device": "cpu",
        }
