"""Authentication subsystem.

- `deps.py` — FastAPI dependencies (`require_login`, `get_profile_optional`) used by every protected route.
- `supabase_jwt.py` — verify access-token signatures (HS256 shared secret or asymmetric via JWKS).
- `supabase_client.py` — thin sync httpx wrappers around Supabase Auth REST endpoints.
- `cookies.py` — set/clear the HTTP-only `bgg_access` / `bgg_refresh` cookies.
- `dev_shim.py` — local-only escape hatch (no Supabase round trip).
"""
