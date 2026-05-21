"""ORM model registry.

Importing this package has the side effect of registering every ORM table on
`Base.metadata`. Alembic's `target_metadata = Base.metadata` only sees tables that have
been imported, so this module is the single import point used by both the app and
`alembic/env.py`.

The `supabase_auth_ref` import must come first — `profiles.id` FKs to `auth.users.id`,
which only exists once that module declares the reference table on `Base.metadata`.
"""

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
