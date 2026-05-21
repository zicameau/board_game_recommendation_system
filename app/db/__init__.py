"""Database subsystem: SQLAlchemy engine, declarative `Base`, ORM models, and the FastAPI session dep.

- `session.py` — engine + `SessionLocal` + `get_db()` (use as `Depends(get_db)`).
- `base.py` — `Base = DeclarativeBase` with the project's Alembic-friendly naming convention.
- `models/` — the four ORM tables (`Profile`, `OnboardingSelection`, `UserEmbedding`, `ModelPromotion`).
- `supabase_auth_ref.py` — reference-only `auth.users` declaration so `profiles.id` can FK.
"""
