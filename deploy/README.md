# Production deploy layout on the VPS

From the repository root, production uses:

| Path (on server) | Purpose |
|------------------|---------|
| `/opt/bgg-rec-sys/docker-compose.prod.yml` | App + Caddy + migrate (synced by CI) |
| `/opt/bgg-rec-sys/deploy/Caddyfile` | TLS + reverse proxy (edit `email` here) |
| `/opt/bgg-rec-sys/.env.deploy` | **`BGG_REC_IMAGE=...`** (CI overwrites on each deploy) |
| `/opt/bgg-rec-sys/.env.production` | **You create once** — secrets and `ENVIRONMENT=prod` (never committed) |

First-time server prep: see [`docs/production.md`](../docs/production.md) and optionally run `deploy/scripts/vps-bootstrap.sh` as root.
