# Production: boardlore.com + DigitalOcean

Operational runbook for **`boardlore.com`** on Cloudflare and the **Ubuntu 24.04** droplet (**public IPv4 `64.23.133.195`**, region SFO3).

## 1. Architecture

- **Visitors** → Cloudflare DNS → **HTTPS** to the droplet (**Caddy** on ports **80 / 443**).
- **Caddy** → internal Docker network **`bgg_rec_edge`** → **`app:8000`** (FastAPI + uvicorn).
- **Alembic** runs as **`docker compose run --rm migrate`** before or alongside deploys.

Image is built whenever **`main`** is updated (**direct push**, **PR merge into `main`** — that also appears as a **`push` event** — or **manual workflow run** on `main`), pushed to **GHCR**, then the workflow **SCPs** manifests and **SSH** runs compose `pull`, `migrate`, `up`.

## 2. DNS (Cloudflare)

| Record | Content | Proxy |
|--------|---------|--------|
| `A` `@` (`boardlore.com`) | `64.23.133.195` | Start **grey** during bring-up |
| `CNAME` or `A` **`www`** | `@` or same IP | Match apex |

Later: enable **orange cloud**, then **SSL/TLS → Full (strict)** once the droplet presents a trusted cert for apex + `www`.

## 3. First-time VPS setup

```bash
# As root once (review script first)
sudo bash deploy/scripts/vps-bootstrap.sh
```

Then create `/opt/bgg-rec-sys` layout (files are synced by CI on each deploy):

1. **`/opt/bgg-rec-sys/.env.production`** — **create manually** with real secrets (never in git):

   - `ENVIRONMENT=prod`
   - `SECURE_COOKIES=true`
   - Strong `SESSION_SECRET`
   - `DATABASE_URL` / optional `ALEMBIC_DATABASE_URL`
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY` or `SUPABASE_KEY`, `SUPABASE_JWT_SECRET` (Supabase Auth)
   - `MODEL_BUNDLE_PATH=bundles` and `MODEL_VERSION=…` (**must match the bundle baked into the image** — controlled by CI `MODEL_VERSION` repository variable).
   - `API_BASE_URL=https://boardlore.com`
   - `CORS_ORIGINS=["https://boardlore.com"]` (include `www` only if you use it)

   Pydantic also looks for `.env.local` inside the container; Compose injects **`env_file: .env.production`** as environment variables, which overrides/augments defaults.

2. Edit **`deploy/Caddyfile`** (after SCP from CI) and set **`email`** to your real address for Let's Encrypt.

3. **Docker login to GHCR** on the VPS (needed if packages are **private**):

   ```bash
   echo TOKEN | docker login ghcr.io -u USERNAME --password-stdin
   ```

Use a **[classic PAT](https://github.com/settings/tokens)** or fine-grained token with **`read:packages`** (and `write` only if pushing from droplet).

## 4. Supabase checklist

In **Authentication → URL configuration**:

- **Site URL:** `https://boardlore.com` (match your canonical apex vs www).
- **Redirect URLs:** `https://boardlore.com/auth/callback` and, if served, `https://www.boardlore.com/auth/callback`.

Email links and JWT flows must align with **`API_BASE_URL` / Site URL.**

## 5. CI/CD secrets (GitHub)

Repository secrets for **`.github/workflows/ci-cd.yml`**:

| Secret | Purpose |
|--------|---------|
| `SSH_HOST` | `64.23.133.195` |
| `SSH_USER` | e.g. `root` |
| `SSH_PRIVATE_KEY` | PEM for that user (`ssh-ed25519`/`rsa`) |
| `GHCR_PULL_USER` *(optional)* | GH username for **`docker login`** |
| `GHCR_PULL_TOKEN` *(optional)* | PAT with **`read:packages`** if image is private |

Repository **Variables** (optional):

| Variable | Purpose |
|---------|---------|
| `MODEL_VERSION` | Subdirectory under `bundles/` baked into Docker (default **`popularity-v1-fixture`** if unset); e.g. `bgg-two-tower-v1` |

Ensure the **workflow** has **packages: write** (already set for `GITHUB_TOKEN`) so pushes to **`ghcr.io/<owner>/<repo>`** succeed. Image tags: **`main`** and **`:${{ github.sha }}`**.

## 6. Git LFS & Docker build

Workflow uses **`checkout` with `lfs: true`** so **`bundles/**/*.npy`** and **`*.parquet`** are real files during **`docker build`**. Without LFS pointers, **`COPY bundles/...`** breaks.

Locally: **`git lfs install && git lfs pull`** before **`docker build`**.

## 7. Firewall

On DigitalOcean (**Networking → Firewalls**) or **`uffw`**: allow **`22/tcp`** from your IPs, **`80`**, **`443`**. Optionally restrict **`22`** to your home/office IP.

## 8. Rollback

On the VPS:

```bash
cd /opt/bgg-rec-sys
printf 'BGG_REC_IMAGE=%s\n' 'ghcr.io/OWNER/repo:PRIOR_SHA' > .env.deploy
docker compose -f docker-compose.prod.yml --env-file .env.deploy pull
docker compose -f docker-compose.prod.yml --env-file .env.deploy up -d
```

Run **`docker compose -f docker-compose.prod.yml … run --rm migrate`** again only if migrations on `main` are backward-compatible with schema you need.

## 9. Troubleshooting

- **Compose: missing `.env.production`** → create it before the first CI deploy succeeds.
- **Pull denied** → **`docker login ghcr.io`** with PAT (**`GHCR_PULL_*`** in CI).
- **Certificate failures behind Cloudflare** → origin must expose valid HTTPS for **Full (strict)** (Caddy obtains certs automatically when **80** is reachable on the apex names).
- **Wrong model / bundle** → mismatch between baked **`MODEL_VERSION`** in CI and **`MODEL_VERSION`/`MODEL_BUNDLE_PATH`** in `.env.production`.

## 10. Reference paths (repo)

- [`Dockerfile`](../Dockerfile) — **`ARG MODEL_VERSION`**
- [`docker-compose.prod.yml`](../docker-compose.prod.yml)
- [`deploy/Caddyfile`](../deploy/Caddyfile)
- [`deploy/scripts/vps-bootstrap.sh`](../deploy/scripts/vps-bootstrap.sh)
