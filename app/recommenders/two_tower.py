"""Two-tower dot-product recommender backed by numpy item embeddings.

This is the production recommender. Item embeddings are precomputed offline and shipped in
the bundle as `item_embeddings.npy`; we memory-map them at load time so startup is cheap
even for large catalogs. The user "tower" is computed on the fly as an L2-normalized,
weight-signed average of the user's seed-game item embeddings (see
`fit_user_embedding`) — no Torch model load at request time.

Scoring is a single matrix-vector dot product (`item_emb @ user_emb`), followed by
top-k via `argpartition` for O(n) selection instead of a full sort.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.recommenders.base import BaseRecommender
from app.recommenders.registry import register


@register("two_tower")
class TwoTowerRecommender(BaseRecommender):
    """Dot-product retrieval with precomputed item embeddings + on-the-fly user vector."""

    model_type = "two_tower"
    supported_schema_versions = (1,)

    def __init__(
        self,
        item_emb: np.ndarray,
        games_meta: pd.DataFrame,
        version: str,
    ):
        """Hold the item embedding matrix + aligned games_meta; backfill `game_idx` if absent."""
        self.item_emb = np.asarray(item_emb, dtype=np.float32)
        self.games_meta = games_meta.reset_index(drop=True)
        self.version = version
        if "game_idx" not in self.games_meta.columns:
            self.games_meta.insert(0, "game_idx", range(len(self.games_meta)))

    @classmethod
    def load(cls, model_dir: Path) -> TwoTowerRecommender:
        """Memory-map `item_embeddings.npy` and read `games_meta.parquet` from the bundle dir.

        Backfills `title` from `primary` and `bgg_id` from `id` when the parquet schema uses
        the older column names. We `np.array(item_emb)` after mmap so the array is owned
        (mmap'd ndarrays don't survive being indexed across processes in some setups).
        """
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
        """Return the L2-normalized weighted sum of seed-game item embeddings.

        `positives` come with positive weights (Love=+1.0, Like=+0.5), `negatives` with
        negative weights (Dislike=-0.5, Hate=-1.0). If the accumulator vanishes (e.g.
        every weight cancels), we return a stable unit vector along axis 0 so downstream
        scoring still works.
        """
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
        """Rank items by dot product, mask `exclude` with -inf, return top-k via `argpartition`.

        Ties (same score) break on `game_idx` ascending so results are deterministic.
        """
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
        """Diagnostics for `/healthz`."""
        return {
            "model_type": self.model_type,
            "version": self.version,
            "n_items": int(len(self.item_emb)),
            "device": "cpu",
        }
