"""Verify Supabase access tokens (HS256 legacy or asymmetric ES256/RS256 via JWKS).

Older Supabase projects sign tokens with a shared HS256 secret (`SUPABASE_JWT_SECRET`).
Newer projects rotate keys and publish them at `<SUPABASE_URL>/auth/v1/.well-known/jwks.json`;
`decode_access_token` inspects the token header and routes to whichever path matches.

The JWKS client is cached at module scope so we only hit the JWKS endpoint once per process.
"""

from __future__ import annotations

import jwt
from jwt import ExpiredSignatureError, InvalidAudienceError, InvalidTokenError, PyJWKClient

from app.config import settings

_jwks_client: PyJWKClient | None = None


def _jwks() -> PyJWKClient:
    """Return the lazily-initialized JWKS client for the configured Supabase URL."""
    global _jwks_client
    if not settings.SUPABASE_URL:
        raise InvalidTokenError("SUPABASE_URL not configured")
    if _jwks_client is None:
        url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(url, cache_keys=True)
    return _jwks_client


def decode_access_token(token: str) -> dict:
    """Verify the signature and return decoded claims.

    Picks the algorithm from the token header. For HS256, requires `SUPABASE_JWT_SECRET`.
    For asymmetric algs, fetches the signing key from JWKS. Requires `exp` and `sub` claims.
    Audience is checked against ``"authenticated"`` if present; if a token omits the
    audience claim, the verification is retried without that requirement (some Supabase
    edge cases ship tokens without `aud`).

    Raises:
        jwt.InvalidTokenError: for unsupported algs, missing config, or signature failures.
        jwt.ExpiredSignatureError: when the token's `exp` is in the past.
    """
    header = jwt.get_unverified_header(token)
    alg = header.get("alg") or "HS256"

    if alg == "HS256":
        if not settings.SUPABASE_JWT_SECRET:
            raise InvalidTokenError("SUPABASE_JWT_SECRET required for HS256 tokens")
        try:
            return jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
                options={"require": ["exp", "sub"]},
            )
        except InvalidAudienceError:
            return jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"require": ["exp", "sub"]},
            )

    if alg in ("ES256", "ES384", "ES512", "RS256"):
        signing_key = _jwks().get_signing_key_from_jwt(token)
        try:
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience="authenticated",
                options={"require": ["exp", "sub"]},
            )
        except InvalidAudienceError:
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                options={"require": ["exp", "sub"]},
            )

    raise InvalidTokenError(f"unsupported JWT alg: {alg}")
