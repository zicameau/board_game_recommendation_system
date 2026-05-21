"""Singleton holding the currently-loaded recommender + the `@register(...)` decorator.

Every concrete recommender class registers itself at import time:

    @register("two_tower")
    class TwoTowerRecommender(BaseRecommender):
        ...

`ModelRegistry.load_active()` runs once at app startup (`lifespan` in `app/main.py`),
reads `bundles/<MODEL_VERSION>/manifest.json`, looks up the registered class by
`model_type`, and instantiates it. On any failure (missing bundle, bad manifest,
unsupported `schema_version`, unknown `model_type`) the registry falls back to the
`popularity-v1-fixture` bundle so the app still serves *something*.

The registry exposes thin pass-through methods (`fit_user_embedding`, `top_k`, `info`) so
callers don't have to reach through `registry.recommender` directly.
"""

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
    """Class decorator: add this recommender class to the global registry keyed by `model_type`.

    Example::

        @register("popularity")
        class PopularityRecommender(BaseRecommender): ...
    """
    def _wrap(cls: type[BaseRecommender]):
        _RECOMMENDERS[model_type] = cls
        return cls

    return _wrap


class ModelRegistry:
    """Process-wide singleton that owns the active `BaseRecommender` instance."""

    def __init__(self) -> None:
        self._rec: BaseRecommender | None = None
        self._lock = threading.Lock()

    def load_active(self) -> None:
        """Load the bundle named by `settings.MODEL_VERSION`; fall back to `popularity-v1-fixture` on any error."""
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
        """Return the loaded recommender; raises if `load_active()` hasn't run yet."""
        if self._rec is None:
            raise RuntimeError("ModelRegistry not initialized")
        return self._rec

    def fit_user_embedding(
        self, positives: list[int], negatives: list[int], weights: list[float]
    ):
        """Pass-through to the active recommender's `fit_user_embedding`."""
        return self.recommender.fit_user_embedding(positives, negatives, weights)

    def top_k(self, user_emb, exclude: set[int], k: int = 10):
        """Pass-through to the active recommender's `top_k`."""
        return self.recommender.top_k(user_emb, exclude, k=k)

    def info(self) -> dict:
        """Healthcheck dict for `/healthz`. Empty if the registry isn't loaded yet."""
        if self._rec is None:
            return {}
        return self._rec.healthcheck()


registry = ModelRegistry()
