"""Model promotion audit — §4.5.4."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ModelPromotion(Base):
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
