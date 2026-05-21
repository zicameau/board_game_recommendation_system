"""Process-wide SQLAlchemy engine, sessionmaker, and FastAPI session dependency.

Connection pool sizing assumes a small-instance app (one or two worker processes); when
deploying behind a Supabase pooler (`pgbouncer` transaction mode) the per-process pool size
is fine because the real pooling happens upstream. The 10s `statement_timeout` is a safety
net so a runaway query can't block a worker indefinitely.

`expire_on_commit=False` matters: after `db.commit()` we keep ORM instances usable instead
of forcing a refetch — important because many routes commit and then return data on the
same instance.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

_engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=1800,
    connect_args={"options": "-c statement_timeout=10000"}
    if "postgresql" in settings.DATABASE_URL
    else {},
)

SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


def get_engine():
    """Return the shared engine (useful for Alembic / `pd.read_sql` integrations)."""
    return _engine


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yield a `Session` and close it when the request finishes.

    Use as ``db: Session = Depends(get_db)`` in a route. Each request gets its own
    session; commit/rollback is the route's responsibility.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
