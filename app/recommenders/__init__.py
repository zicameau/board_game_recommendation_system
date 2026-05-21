"""Recommender plugin system.

Each concrete recommender lives in its own module and registers itself via the
`@register("<model_type>")` decorator from `app.recommenders.registry`. The runtime picks
a class to instantiate based on `manifest.json["model_type"]` in the active bundle, so to
add a new model strategy you just drop a new file in this package and import it here so
the decorator runs.
"""

from app.recommenders import popularity  # noqa: F401
from app.recommenders import two_tower  # noqa: F401
from app.recommenders.base import CONTEXT_SCHEMA_VERSION, BaseRecommender
from app.recommenders.registry import ModelRegistry, registry

__all__ = [
    "BaseRecommender",
    "CONTEXT_SCHEMA_VERSION",
    "ModelRegistry",
    "registry",
]
