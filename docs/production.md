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

**CI deploy runs `docker compose` on the server.** If GitHub Actions fails with `docker: command not found`, Docker Engine is not installed yet — run bootstrap **once** as **root** (no clone required):

```bash
curl -fsSL https://raw.githubusercontent.com/OWNER/REPO/main/deploy/scripts/vps-bootstrap.sh | bash
```

Replace **`OWNER/REPO`** with your GitHub path (e.g. `zicameau/board_game_recommendation_system`). Review the script in the repo before piping to `bash`.

If you already have the repo on the machine:

```bash
sudo bash deploy/scripts/vps-bootstrap.sh
```

Then create `/opt/bgg-rec-sys` layout (files are synced by CI on each deploy):

1. **`/opt/bgg-rec-sys/.env.production`** — **create manually** with real secrets (never in git):

   - `ENVIRONMENT=prod`
   - `SECURE_COOKIES=true`
   - Strong `SESSION_SECRET`
   - `DATABASE_URL` / `ALEMBIC_DATABASE_URL` — paste from **Supabase Dashboard → Database → Connect**.
     On **IPv4-only** hosts (most DigitalOcean droplets), use the **Session pooler** URI from **Connect** (`*.pooler.supabase.com:5432`, e.g. `aws-1-us-east-2…` — copy verbatim; prefix/shard varies), username **`postgres.<project_ref>`**.
     Do **not** rely on **`db.<project_ref>.supabase.co`** for the server: DNS is often **IPv6-only**, which produces **`Network is unreachable`** during **`docker compose … migrate`**.
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
| `MODEL_VERSION` | Subdirectory under `bundles/` baked into Docker (CI default **`bgg-two-tower-v1`** if unset; override per repo); e.g. `popularity-v1-fixture` |

Ensure the **workflow** can push packages (**`build`** job declares **`permissions: packages: write`**).

If **`build`** fails with **`denied: permission_denied: write_package`**, **`GITHUB_TOKEN` is still read-only**:

1. **Repository:** **Settings → Actions → General → Workflow permissions** → choose **Read and write permissions** → **Save** (or whatever your org minimum is that allows **writing packages**). If this stays **Read-only**, workflows **cannot push** to GHCR even when YAML asks for **`packages: write`**.
2. **Organization (if repo is under an org):** Org **Settings → Actions → General** — ensure repositories are allowed **`GITHUB_TOKEN`** **write** for **Packages** where required.
3. **Fallback:** Create a classic PAT with **`write:packages`** (and **`read:packages`**), store as repo secret **`GHCR_PUSH_TOKEN`**, and change the **`docker/login-action`** **`password`** to **`${{ secrets.GHCR_PUSH_TOKEN }}`** (**`username`** = account that owns that PAT).

Image tags: **`main`** and **`:${{ github.sha }}`**.

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
- **Deploy: `docker: command not found`** → run [§3 First-time VPS setup](#3-first-time-vps-setup) bootstrap on the droplet (Docker Engine + compose plugin), then re-run the workflow.
- **Pull denied** → **`docker login ghcr.io`** with PAT (**`GHCR_PULL_*`** in CI).
- **Certificate failures behind Cloudflare** → origin must expose valid HTTPS for **Full (strict)** (Caddy obtains certs automatically when **80** is reachable on the apex names).
- **Wrong model / bundle** → mismatch between baked **`MODEL_VERSION`** in CI and **`MODEL_VERSION`/`MODEL_BUNDLE_PATH`** in `.env.production`.
- **`OperationalError` … IPv6 address … `Network is unreachable`** → Postgres URL points at **`db.<ref>.supabase.co`** (IPv6-only). Switch **`DATABASE_URL`** / **`ALEMBIC_DATABASE_URL`** to the **Session pooler** string from **Connect** (**`*.pooler.supabase.com`**, user **`postgres.<ref>`**). If you see **`Tenant or user not found`**, paste the URI from the dashboard instead of guessing host/region.

## 10. Reference paths (repo)

- [`Dockerfile`](../Dockerfile) — **`ARG MODEL_VERSION`**
- [`docker-compose.prod.yml`](../docker-compose.prod.yml)
- [`deploy/Caddyfile`](../deploy/Caddyfile)
- [`deploy/scripts/vps-bootstrap.sh`](../deploy/scripts/vps-bootstrap.sh)
