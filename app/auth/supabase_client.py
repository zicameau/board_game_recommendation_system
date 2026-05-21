"""Sync HTTP client for Supabase Auth's REST endpoints (signup, sign-in, refresh, logout, MFA).

We use `httpx` synchronously because FastAPI's sync def routes do the same — keeping
everything sync avoids needing an async DB session just for auth-adjacent calls. Each call
opens and closes a short-lived client to avoid leaking connections across requests.

All errors are wrapped in `SupabaseAuthError` with the original status and JSON payload so
route handlers can render a friendly message (and optionally inspect `payload["error_code"]`
for rate-limit-style cases).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class SupabaseAuthError(Exception):
    """Raised when a Supabase Auth REST call returns a non-2xx status."""

    def __init__(self, message: str, status: int = 400, payload: dict | None = None):
        super().__init__(message)
        self.status = status
        self.payload = payload or {}


def _headers() -> dict[str, str]:
    """Standard auth headers; raises 503 if Supabase isn't configured."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        raise SupabaseAuthError("Supabase not configured", status=503)
    return {
        "apikey": settings.SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }


def _auth_error_message(data: dict[str, Any]) -> str:
    """Readable message from Supabase Auth JSON (GoTrue uses `msg`; OAuth-style errors use `error_description`)."""
    return (
        (data.get("msg") or "").strip()
        or (data.get("error_description") or "").strip()
        or (data.get("message") or "").strip()
        or "Request failed"
    )


def signup_email_password(email: str, password: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """Create a Supabase auth user; `metadata` lands on `user_metadata` (we put `username` there)."""
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/signup"
    body = {"email": email, "password": password, "data": metadata}
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, headers=_headers(), json=body)
        data = r.json() if r.content else {}
    if r.status_code >= 400:
        logger.warning("signup failed: %s %s", r.status_code, data)
        msg = _auth_error_message(data)
        raise SupabaseAuthError(msg, status=r.status_code, payload=data)
    return data


def sign_in_password(email: str, password: str) -> dict[str, Any]:
    """Password grant — returns `{access_token, refresh_token, expires_in, user}` on success."""
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=password"
    body = {"email": email, "password": password}
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, headers=_headers(), json=body)
        data = r.json() if r.content else {}
    if r.status_code >= 400:
        logger.warning("sign_in failed: %s %s", r.status_code, data)
        msg = _auth_error_message(data)
        raise SupabaseAuthError(msg, status=r.status_code, payload=data)
    return data


def refresh_session(refresh_token: str) -> dict[str, Any]:
    """Exchange the refresh token for a fresh access token (and a rotated refresh token)."""
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=refresh_token"
    body = {"refresh_token": refresh_token}
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, headers=_headers(), json=body)
        data = r.json() if r.content else {}
    if r.status_code >= 400:
        raise SupabaseAuthError("refresh_failed", status=r.status_code, payload=data)
    return data


def sign_out(access_token: str) -> None:
    """Best-effort server-side logout (revokes the refresh token on Supabase). Errors are swallowed by the caller."""
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/logout"
    hdrs = _headers()
    hdrs["Authorization"] = f"Bearer {access_token}"
    with httpx.Client(timeout=30.0) as client:
        client.post(url, headers=hdrs, json={})


def mfa_challenge(factor_id: str, jwt: str) -> dict[str, Any]:
    """Begin an MFA challenge for the given factor; returns the challenge id used in `mfa_verify`."""
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/factors/{factor_id}/challenge"
    hdrs = _headers()
    hdrs["Authorization"] = f"Bearer {jwt}"
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, headers=hdrs, json={})
        data = r.json() if r.content else {}
    if r.status_code >= 400:
        raise SupabaseAuthError("mfa_challenge_failed", status=r.status_code, payload=data)
    return data


def mfa_verify(factor_id: str, challenge_id: str, code: str, jwt: str) -> dict[str, Any]:
    """Verify the user-entered MFA `code` against an in-flight challenge; promotes the session to AAL2."""
    url = (
        f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/factors/"
        f"{factor_id}/verify/challenge?id={challenge_id}"
    )
    hdrs = _headers()
    hdrs["Authorization"] = f"Bearer {jwt}"
    body = {"code": code}
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, headers=hdrs, json=body)
        data = r.json() if r.content else {}
    if r.status_code >= 400:
        raise SupabaseAuthError("mfa_verify_failed", status=r.status_code, payload=data)
    return data
