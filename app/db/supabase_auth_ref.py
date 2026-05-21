"""Reference-only declaration of `auth.users` so `profiles.id` can FK to it.

Supabase owns the `auth` schema; we *must not* let Alembic create or alter it. By
declaring the table with only the `id` column on our `Base.metadata`, SQLAlchemy can
resolve the FK target for typing/relationship purposes without ever attempting DDL on the
real Supabase table. The migration that creates the FK uses raw SQL to avoid even hinting
at table creation.
"""

from sqlalchemy import Column, Table
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base

Table(
    "users",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    schema="auth",
)
