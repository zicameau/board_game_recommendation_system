"""Base recommender interface — §5.3."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np

CONTEXT_SCHEMA_VERSION = 1


class BaseRecommender(ABC):
    model_type: str
    supported_schema_versions: tuple[int, ...]
    version: str

    @classmethod
    @abstractmethod
    def load(cls, model_dir: Path) -> BaseRecommender:
        """Load recommender from bundle directory."""

    @abstractmethod
    def fit_user_embedding(
        self,
        positives: list[int],
        negatives: list[int],
        weights: list[float],
    ) -> np.ndarray:
        """Produce user embedding vector from onboarding game_idx labels."""

    @abstractmethod
    def top_k(
        self,
        user_emb: np.ndarray,
        exclude: set[int],
        k: int = 10,
    ) -> list[tuple[int, float]]:
        """Return top-k (game_idx, score) descending."""

    @abstractmethod
    def healthcheck(self) -> dict:
        """Registry /health diagnostics."""
