"""`UserEmbedding` ORM model — cached user-tower vector keyed by `user_id`.

`model_version` records which bundle produced this vector. The runtime invalidation rule
lives in `app.services.embeddings.get_or_refit_user_embedding`: if the stored
`model_version` no longer matches `settings.MODEL_VERSION`, the embedding is recomputed
on the next `/home` visit and merged back here.

`embedding` is stored as `REAL[]` (Postgres array of float4) so the dimension can vary
across bundle versions without a schema change.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import ARRAY, REAL, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.profile import Profile


class UserEmbedding(Base):
    """Cached user-tower vector. Invalidated automatically when `model_version` drifts from `settings.MODEL_VERSION`."""

    __tablename__ = "user_embeddings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    embedding: Mapped[list[float]] = mapped_column(ARRAY(REAL), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    fitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    profile: Mapped[Profile] = relationship(back_populates="embedding")
