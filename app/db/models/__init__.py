# Register FK stub then ORM tables for Alembic (§7.7)
from app.db import supabase_auth_ref  # noqa: F401

from app.db.models.model_promotion import ModelPromotion  # noqa: F401
from app.db.models.onboarding import OnboardingSelection  # noqa: F401
from app.db.models.profile import Profile  # noqa: F401
from app.db.models.user_embedding import UserEmbedding  # noqa: F401

__all__ = [
    "Profile",
    "OnboardingSelection",
    "UserEmbedding",
    "ModelPromotion",
]
