# Documentation

| Document | Description |
|----------|-------------|
| [**Architecture**](architecture.md) | How the system works — read this first. Module map, request flows, DB schema, recommendation subsystem, testing strategy, contributor onboarding. |
| [**Local development**](local-development.md) | Python/Docker setup, `.env.local`, environment variables, migrations, auth modes. |
| [**Production**](production.md) | Boardlore deploy: Cloudflare, droplet, GHCR, CI secrets, Caddy, rollback. |
| [**BGG_Recommender_Phased_ERD_v8.docx**](BGG_Recommender_Phased_ERD_v8.docx) | Phased ERD (v8) for the recommender system. |
| [**Training notebooks**](../notebooks/README.md) | Offline notebooks that produce the model bundles (e.g. the two-tower training notebook for `bundles/bgg-two-tower-v1/`). |

Also see the repository root `README.md` and `.env.example` for a commented template of all variables.
