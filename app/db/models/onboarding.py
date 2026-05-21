"""`OnboardingSelection` ORM model — one row per user, populated incrementally by the wizard.

`game_ratings` is the only field that drives recommendations directly; the categories /
mechanics / complexity / play_context / player_profile fields are captured for future
personalization (Phase 2+) and for the summary screen, but the current two-tower path only
reads `game_ratings`.

`model_version` snapshots which bundle was active when the row was first persisted, useful
for debugging old onboarding data after a bundle bump.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.profile import Profile


class OnboardingSelection(Base):
    """Per-user wizard answers. `game_ratings` is the only field that the recommender reads today."""

    __tablename__ = "onboarding_selections"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    game_ratings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    liked_categories: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    disliked_categories: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    liked_mechanics: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    disliked_mechanics: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    complexity_pref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    play_context: Mapped[str | None] = mapped_column(String(64), nullable=True)
    player_profile: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )

    profile: Mapped[Profile] = relationship(back_populates="selections")
