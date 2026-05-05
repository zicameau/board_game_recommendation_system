"""Verify Supabase JWTs: legacy HS256 (shared secret) or asymmetric (JWKS at auth/v1)."""

from __future__ import annotations

import jwt
from jwt import ExpiredSignatureError, InvalidAudienceError, InvalidTokenError, PyJWKClient

from app.config import settings

_jwks_client: PyJWKClient | None = None


def _jwks() -> PyJWKClient:
    global _jwks_client
    if not settings.SUPABASE_URL:
        raise InvalidTokenError("SUPABASE_URL not configured")
    if _jwks_client is None:
        url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(url, cache_keys=True)
    return _jwks_client


def decode_access_token(token: str) -> dict:
    """Verify signature and return claims. Supports HS256 (legacy) and ES256/RS256 via JWKS."""
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
