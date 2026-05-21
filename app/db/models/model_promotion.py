"""`ModelPromotion` ORM model — append-only audit of bundle promotions.

A row records "at this timestamp, this `(model_type, model_version)` became active",
optionally with the bundle's SHA-256 and any training/eval metrics. The table exists so
post-incident debugging can correlate user-embedding drift with the exact bundle that
caused it.

Phase 1 caveat: nothing in the serving path *writes* to or *reads* from this table yet —
active model selection is purely via the `MODEL_VERSION` env var. Treat this as a hook
for the future promotion CLI / CI job.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelPromotion(Base):
    """Append-only audit row for one bundle promotion event (not yet wired into serving)."""

    __tablename__ = "model_promotions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    model_type: Mapped[str] = mapped_column(String(128), nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    promoted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    promoted_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    bundle_sha: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
