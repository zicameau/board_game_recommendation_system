"""`Profile` ORM model — the application's per-user row.

One-to-one with Supabase `auth.users` (`profiles.id` is both PK and FK with `ON DELETE
CASCADE`). The owning relationships to `OnboardingSelection` and `UserEmbedding` also
cascade — deleting a profile cleans up onboarding + embedding rows in one step.

`onboarding_completed_at` is the canonical "did this user finish the wizard" flag; routes
check `is None` rather than tracking it in the session.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.onboarding import OnboardingSelection
    from app.db.models.user_embedding import UserEmbedding


class Profile(Base):
    """Application user. PK + FK to `auth.users.id`; deletes cascade to owned rows."""

    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    username: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    selections: Mapped[OnboardingSelection | None] = relationship(
        back_populates="profile", uselist=False, cascade="all, delete-orphan"
    )
    embedding: Mapped[UserEmbedding | None] = relationship(
        back_populates="profile", uselist=False, cascade="all, delete-orphan"
    )
