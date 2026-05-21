"""BGG Recommender — Phase 1 FastAPI application.

Architecture overview lives in `docs/architecture.md`. Per-package roles:

- `app.api` — HTTP routes (auth, onboarding, home).
- `app.auth` — Supabase JWT verification, cookies, dev shim, FastAPI deps.
- `app.db` — SQLAlchemy engine, Base, ORM models, session dep.
- `app.recommenders` — registry pattern + popularity/two-tower implementations.
- `app.services` — request-time logic (embedding refit, recommendation view, taxonomy).
- `app.templates` / `app.static` — Jinja SSR templates and CSS/assets.
- `app.config` — Pydantic Settings loaded from `.env.local`.
"""
