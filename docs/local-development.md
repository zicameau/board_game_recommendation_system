# Local development

This guide covers running the BGG recommender app on your machine: database, Python environment, configuration files, and optional auth modes.

## Prerequisites

- **Python** 3.11 or newer  
- **Git** and **Git LFS** (for `bundles/**/*.npy` and `bundles/**/*.parquet` tracked in-repo; run `git lfs install` once per clone, then `git lfs pull` if large files show as pointers)  
- **Docker Desktop** (recommended) for local PostgreSQL via `docker-compose.yml`  
- A **Supabase** project if you use `AUTH_MODE=supabase` (or use `dev_shim` without cloud auth)

## 1. Clone and install dependencies

```bash
cd bgg-rec-sys
git lfs install
git lfs pull

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -e ".[dev]"
```

## 2. Environment files: `.env.local` (required)

The app reads settings with **Pydantic Settings** from a single file:

| File            | Used by app? |
|-----------------|--------------|
| **`.env.local`**| Yes — this is the file you edit. |
| `.env`          | Not loaded by default (use `.env.local`). |
| `.env.example`  | Template only; safe to commit. |

**Setup:** copy the example and fill in secrets.

```bash
copy .env.example .env.local    # Windows
# cp .env.example .env.local     # Unix
```

Never commit `.env.local` (it is gitignored). Commit `.env.example` only as a template.

### Variable reference

| Variable | What it does |
|----------|----------------|
| `ENVIRONMENT` | `local` \| `staging` \| `prod` — informational; defaults to `local`. |
| **`DATABASE_URL`** | SQLAlchemy URL to Postgres (app + API). Default matches Docker Compose: `postgresql://bgg:bgg@127.0.0.1:5433/bgg_dev`. Special characters in the password must be **URL-encoded** (`#`, `@`, `/`, etc.). |
| `ALEMBIC_DATABASE_URL` | Optional. If set, Alembic migrations use this URL instead of `DATABASE_URL` (useful when the app uses a pooler URL but migrations need the direct/session URL). |
| `AUTH_MODE` | `supabase` — real Supabase Auth (JWT cookies, login/register). `dev_shim` — no Supabase; identity comes from `X-Dev-User` header or `?dev_user=` query; use for UI-only work with Docker Postgres. |
| `SUPABASE_URL` | Project URL, e.g. `https://<project>.supabase.co`. |
| `SUPABASE_KEY` or `SUPABASE_ANON_KEY` | Publishable **anon** key (either name works). |
| `SUPABASE_SERVICE_ROLE_KEY` | Optional server-side operations (if you add admin features later). |
| `SUPABASE_JWT_SECRET` | **JWT secret** from Supabase (Settings → API → JWT) — used to verify access tokens from cookies. Must match the project whose keys you use. |
| `API_BASE_URL` | Base URL of this app (e.g. `http://localhost:8000`) for links/callbacks if needed. |
| `CORS_ORIGINS` | JSON-style list string, e.g. `["http://localhost:8000"]`. |
| `SECURE_COOKIES` | `false` for plain HTTP on localhost; `true` behind HTTPS in production. |
| **`SESSION_SECRET`** | Long random string for signing the Starlette session cookie — change from any default in production. |
| `MODEL_BUNDLE_PATH` | Root directory for model bundles (default `bundles`). |
| `MODEL_VERSION` | Subdirectory name under that path, e.g. `popularity-v1-fixture` or `bgg-two-tower-v1`. Must match a folder containing `manifest.json` (and the `.npy` / `.parquet` artifacts if you use them). |
| `LOG_LEVEL` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |

Cookie names (`ACCESS_COOKIE_NAME`, `REFRESH_COOKIE_NAME`) are defined in code with defaults; override only if you have a conflict.

### Supabase vs local Docker Postgres

- **Docker (same machine as the app):** set `DATABASE_URL` to the compose URL on port **5433** (host maps to container 5432). Start DB: `docker compose up -d`.  
- **Supabase-hosted DB:** paste the URI from the Supabase dashboard (**Connect**). Use the **session** or **transaction** pooler URL as documented in `.env.example`. If password has symbols, encode them for URLs.  
- **Split URLs:** If your hosted pooler does not play nicely with Alembic, keep `DATABASE_URL` for the app and set `ALEMBIC_DATABASE_URL` to the direct Postgres connection for migrations only.

## 3. Database and migrations

With Postgres running:

```bash
alembic upgrade head
```

This assumes `DATABASE_URL` (or `ALEMBIC_DATABASE_URL`) points at the same database the app will use.

## 4. Run the app

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. Health: `http://127.0.0.1:8000/healthz`.

## 5. Authentication modes (quick)

| Mode | When to use |
|------|-------------|
| **`supabase`** | Full login/register, JWT cookies, production-like auth. Requires valid `SUPABASE_*` and usually cloud or linked Postgres if you mirror auth users. |
| **`dev_shim`** | Fast UI/dev without Supabase. Set in `.env.local`, restart uvicorn. Visit e.g. `/onboarding/welcome?dev_user=you` or send header `X-Dev-User: you`. |

## 6. Tests

```bash
pytest
```

## 7. Troubleshooting

- **“Supabase not configured” / 503 on auth calls:** fill `SUPABASE_URL` and anon key; for token verification add `SUPABASE_JWT_SECRET`.  
- **Migration or login errors against Supabase DB:** ensure `auth.users` / FK expectations match your deployment (local stub vs hosted Supabase).  
- **LFS files missing / tiny pointer files:** run `git lfs install` and `git lfs pull` in the repo root.  
- **Model fails to load:** check `MODEL_BUNDLE_PATH` / `MODEL_VERSION` and that the bundle directory exists with `manifest.json` (and LFS-pulled binaries if applicable).

For schema context, see `docs/BGG_Recommender_Phased_ERD_v8.docx`.
