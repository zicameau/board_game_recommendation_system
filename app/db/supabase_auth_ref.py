"""Reference-only table so SQLAlchemy can resolve FKs to Supabase `auth.users` (Alembic never creates this)."""

from sqlalchemy import Column, Table
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

Table(
    "users",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    schema="auth",
)
