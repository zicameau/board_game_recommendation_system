"""Model registry singleton — §5.7."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from app.config import settings
from app.recommenders.base import BaseRecommender, CONTEXT_SCHEMA_VERSION

logger = logging.getLogger(__name__)

_RECOMMENDERS: dict[str, type[BaseRecommender]] = {}


def register(model_type: str):
    def _wrap(cls: type[BaseRecommender]):
        _RECOMMENDERS[model_type] = cls
        return cls

    return _wrap


class ModelRegistry:
    def __init__(self) -> None:
        self._rec: BaseRecommender | None = None
        self._lock = threading.Lock()

    def load_active(self) -> None:
        bundle_dir = Path(settings.MODEL_BUNDLE_PATH).resolve() / settings.MODEL_VERSION
        manifest_path = bundle_dir / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            schema_v = manifest.get("schema_version", 1)
            if schema_v not in (CONTEXT_SCHEMA_VERSION,):
                raise RuntimeError(f"bundle schema_version {schema_v} not supported")
            model_type = manifest["model_type"]
            cls = _RECOMMENDERS.get(model_type)
            if cls is None:
                raise RuntimeError(f"no recommender registered for {model_type!r}")
            rec = cls.load(bundle_dir)
        except Exception as e:
            logger.warning("Primary bundle load failed (%s), trying popularity fallback", e)
            fallback_name = "popularity-v1-fixture"
            fb = Path(settings.MODEL_BUNDLE_PATH).resolve() / fallback_name
            pcls = _RECOMMENDERS.get("popularity")
            if pcls is None:
                raise RuntimeError("popularity fallback unavailable") from e
            rec = pcls.load(fb)
        with self._lock:
            self._rec = rec
        logger.info("Loaded recommender: %s %s", rec.model_type, getattr(rec, "version", "?"))

    @property
    def recommender(self) -> BaseRecommender:
        if self._rec is None:
            raise RuntimeError("ModelRegistry not initialized")
        return self._rec

    def fit_user_embedding(
        self, positives: list[int], negatives: list[int], weights: list[float]
    ):
        return self.recommender.fit_user_embedding(positives, negatives, weights)

    def top_k(self, user_emb, exclude: set[int], k: int = 10):
        return self.recommender.top_k(user_emb, exclude, k=k)

    def info(self) -> dict:
        if self._rec is None:
            return {}
        return self._rec.healthcheck()


registry = ModelRegistry()
