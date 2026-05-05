"""HTTP-only auth cookies — §3.4.1."""

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
    response.delete_cookie(settings.ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(settings.REFRESH_COOKIE_NAME, path="/")
