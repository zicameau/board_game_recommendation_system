"""Set and clear the HTTP-only auth cookies (`bgg_access`, `bgg_refresh`).

Cookies are scoped to the whole site (`path="/"`), SameSite=Lax (so they survive top-level
GET navigations but not cross-site POSTs), and `secure` is governed by `SECURE_COOKIES`
(false locally, true in production behind HTTPS).

Note: when setting cookies on a redirect, the `Response` object passed in must be the
same one returned from the route — see `tests/test_login_cookies.py` for the regression.
"""

from __future__ import annotations

from fastapi import Response

from app.config import settings


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    *,
    max_age_access: int = 3600,
    max_age_refresh: int = 30 * 24 * 3600,
) -> None:
    """Attach access + refresh cookies to `response` with the project's standard policy.

    Args:
        response: The response that will be returned to the browser.
        access_token: Supabase JWT access token (short-lived).
        refresh_token: Supabase refresh token (long-lived).
        max_age_access: Seconds until the access cookie expires (default 1 hour).
        max_age_refresh: Seconds until the refresh cookie expires (default 30 days).
    """
    response.set_cookie(
        key=settings.ACCESS_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=settings.SECURE_COOKIES,
        samesite="lax",
        max_age=max_age_access,
        path="/",
    )
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.SECURE_COOKIES,
        samesite="lax",
        max_age=max_age_refresh,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    """Remove both auth cookies (used on logout and on auth errors that need a clean slate)."""
    response.delete_cookie(settings.ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(settings.REFRESH_COOKIE_NAME, path="/")
