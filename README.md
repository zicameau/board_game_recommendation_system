# BGG Recommendation System

A board-game recommender for BoardGameGeek users. FastAPI + Jinja2 SSR + SQLAlchemy + Alembic, backed by Supabase or local Postgres, serving a two-tower retrieval model from a versioned on-disk bundle. Live demo: [boardlore.com](https://boardlore.com).

> **New to the codebase?** Start with [`docs/architecture.md`](docs/architecture.md) for a guided tour of how the pieces fit together, *then* come back here for setup.

## Team

- **Trevor** — Web app, deployment & evaluation harness
- **Brandon** — Matrix factorization & neural collaborative filtering
- **Alexander** — Hyperparameter tuning & evaluation methodology

See [`docs/architecture.md`](docs/architecture.md) for a full breakdown of contributions.

## Dataset

[BoardGameGeek Reviews on Kaggle](https://www.kaggle.com/datasets/jvanelteren/boardgamegeek-reviews) (`jvanelteren/boardgamegeek-reviews`). The training notebook downloads it via the Kaggle API — a Kaggle account and `kaggle.json` API token are required. The raw CSVs are not committed to this repo (they are well over 100 MB); only the model artifacts produced from them live under [`bundles/`](bundles).

## Documentation

- **Architecture** (how the system works — read this first): [`docs/architecture.md`](docs/architecture.md)
- **Local development** (environment variables, `.env.local`, Git LFS, troubleshooting): [`docs/local-development.md`](docs/local-development.md)
- **Production deploy** (boardlore.com, DigitalOcean, CI/CD, Docker, Caddy): [`docs/production.md`](docs/production.md)
- **Training notebooks** (Colab notebook that produced the two-tower bundle): [`notebooks/README.md`](notebooks/README.md)
- **ERD (v8)**: [`docs/BGG_Recommender_Phased_ERD_v8.docx`](docs/BGG_Recommender_Phased_ERD_v8.docx)

## Prerequisites

- Python 3.11+
- Postgres (Docker recommended)
- Git LFS (`git lfs install && git lfs pull`) — the model bundle's `.npy` and `.parquet` files are stored via LFS

## How to Run

1. Start Postgres:

   ```powershell
   docker compose up -d postgres
   ```

2. Copy `.env.example` to `.env.local` and set:

   ```env
   DATABASE_URL=postgresql://bgg:bgg@127.0.0.1:5433/bgg_dev
   ```

   `docker-compose.yml` maps **host port 5433** to the container's Postgres on 5432. This avoids "port already in use" conflicts when another Postgres on your machine is already listening on 5432.

   Default credentials: user `bgg`, password `bgg`, database `bgg_dev`.

3. Install dependencies (use `requirements.txt` for plain pip, or `pip install -e ".[dev]"` to install in editable mode), run migrations, and start the app:

   ```powershell
   pip install -r requirements.txt
   alembic upgrade head
   uvicorn app.main:app --reload
   ```

   Open [http://127.0.0.1:8000](http://127.0.0.1:8000) and sign up — or set `AUTH_MODE=dev_shim` in `.env.local` and visit `http://127.0.0.1:8000/onboarding/welcome?dev_user=you` to skip Supabase entirely.

### Re-train the two-tower model

The serving path reads precomputed artifacts from `bundles/<MODEL_VERSION>/`. To retrain from scratch, open [`notebooks/bgg_phase1_trevor_v2_2_fixed.ipynb`](notebooks/bgg_phase1_trevor_v2_2_fixed.ipynb) in Google Colab (T4 GPU recommended) and run all cells. Training dependencies live in [`notebooks/requirements.txt`](notebooks/requirements.txt). See [`notebooks/README.md`](notebooks/README.md) for the export-to-bundle mapping.

## Supabase

Use the **pooler URL** for runtime in `DATABASE_URL`. Set `ALEMBIC_DATABASE_URL` to the **direct migration URL** when needed.

### Authentication / URL configuration

- **Site URL** should be `http://localhost:8000` while developing (this app runs `uvicorn` on **8000**, not 3000).
- **Redirect URLs**: allow `http://localhost:8000/auth/callback` and optionally `http://127.0.0.1:8000/auth/callback`.

Email confirmation sends users to `/auth/callback` with tokens in the **URL hash** (`#access_token=...`). The callback page POSTs them to `/auth/set-session`, which verifies **ES256** JWTs using **JWKS** from your project (or **HS256** with `SUPABASE_JWT_SECRET`) and sets the `bgg_access` / `bgg_refresh` cookies.

## Dev Shim

Requires `AUTH_MODE=dev_shim` and `ENVIRONMENT=local`. Blocked otherwise.

- **CLI / API clients:** send header `X-Dev-User: yourname`
- **Browser:** optional query `?dev_user=yourname` on the **first** visit (header wins if both are set), e.g.
  `http://127.0.0.1:8000/onboarding/welcome?dev_user=smoketest`
- After the first visit, the name is stored in the **signed session cookie** so onboarding links keep working without repeating the query.
- **Logout** clears `dev_user` from the session.

## Tests

```powershell
pytest -q
```

## Troubleshooting

### Alembic: "password authentication failed for user bgg"

Alembic uses `ALEMBIC_DATABASE_URL` if set (in the environment or `.env.local`), otherwise it falls back to `DATABASE_URL`.

1. Prefer **port 5433** in `DATABASE_URL` when using this repo's Docker Postgres (Compose publishes 5433 on the host). If you accidentally use `:5432`, you may hit a different Postgres install and see wrong-user / password errors.
2. Prefer `127.0.0.1` over `localhost` on Windows to avoid IPv6 (`::1`) surprises.
3. If you changed `POSTGRES_PASSWORD` in compose after the first run, the old volume still has the old password. Reset it with:

   ```powershell
   docker compose down -v
   docker compose up -d postgres
   alembic upgrade head
   ```
