"""Server-side Supabase Auth REST calls (§3.4) — sync httpx."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class SupabaseAuthError(Exception):
    def __init__(self, message: str, status: int = 400, payload: dict | None = None):
        super().__init__(message)
        self.status = status
        self.payload = payload or {}


def _headers() -> dict[str, str]:
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
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=refresh_token"
    body = {"refresh_token": refresh_token}
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, headers=_headers(), json=body)
        data = r.json() if r.content else {}
    if r.status_code >= 400:
        raise SupabaseAuthError("refresh_failed", status=r.status_code, payload=data)
    return data


def sign_out(access_token: str) -> None:
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/logout"
    hdrs = _headers()
    hdrs["Authorization"] = f"Bearer {access_token}"
    with httpx.Client(timeout=30.0) as client:
        client.post(url, headers=hdrs, json={})


def mfa_challenge(factor_id: str, jwt: str) -> dict[str, Any]:
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
