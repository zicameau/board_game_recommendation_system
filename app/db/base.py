"""SQLAlchemy `Base` with explicit constraint naming.

Alembic compares constraint names when autogenerating migrations; without a stable naming
convention every autogen run wants to rename indexes and FKs. The convention here matches
what's already in the migrations folder, so `alembic revision --autogenerate` produces
clean diffs.

Every ORM model in `app.db.models` inherits from this `Base`.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model in `app.db.models`."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
