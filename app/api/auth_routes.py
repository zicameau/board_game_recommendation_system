"""Authentication HTML routes (login, register, logout, email-confirm callback, MFA placeholder).

The forms collect email + password only — `_derive_username_from_email` generates a unique
display name from the email's local part to satisfy the NOT-NULL + UNIQUE `profiles.username`
column without making the user pick one.

The Supabase email-confirm flow (`/auth/callback` → `/auth/set-session`) is two-stage because
the access/refresh tokens arrive in the URL **hash** (not the query string) and therefore
can't be read server-side. The callback page JS POSTs them to `set-session`, which verifies
the JWT (HS256 or JWKS) and sets HTTP-only cookies.

`POST /logout` clears auth cookies, best-effort revokes the Supabase session, and (in
dev_shim) wipes the signed-session `dev_user` so logout actually logs you out.
"""

from __future__ import annotations

import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.cookies import clear_auth_cookies, set_auth_cookies
from app.auth.deps import (
    DependsProfileOptional,
    ProfileUsernameUnavailableError,
    ensure_profile,
    is_profile_username_in_use,
)
from app.auth.supabase_jwt import decode_access_token
from app.auth.supabase_client import (
    SupabaseAuthError,
    sign_in_password,
    sign_out,
    signup_email_password,
)
from app.config import settings
from app.db.session import get_db

router = APIRouter(tags=["auth"])


class SetSessionBody(BaseModel):
    """Request body for `POST /auth/set-session` (tokens forwarded from the callback JS)."""

    access_token: str
    refresh_token: str
    expires_in: int = Field(default=3600, ge=60, le=86400 * 14)

@router.get("/auth/callback")
def auth_callback(request: Request):
    """Land the email-confirm redirect; the page's JS reads tokens from the URL hash."""
    return request.app.state.templates.TemplateResponse(
        request,
        "auth/callback.html",
        {"request": request, "viewer": None},
    )


@router.post("/auth/set-session")
def auth_set_session(
    request: Request,
    body: SetSessionBody,
    db: Session = Depends(get_db),
):
    """Verify the just-confirmed JWT, upsert a local profile, set auth cookies, and return a JSON redirect target.

    Called only by the JS in `auth/callback.html` (browser-side hand-off). 401 if the JWT is
    invalid, 409 if the user_metadata username collides with another local profile.
    """
    if settings.AUTH_MODE != "supabase":
        return JSONResponse(
            {"detail": "set-session only for AUTH_MODE=supabase"},
            status_code=400,
        )
    try:
        claims = decode_access_token(body.access_token)
    except Exception as e:
        return JSONResponse({"detail": f"invalid_token: {e!s}"}, status_code=401)

    uid = uuid.UUID(str(claims["sub"]))
    md = claims.get("user_metadata") or {}
    email = (claims.get("email") or md.get("email") or "").strip()
    if not email:
        email = f"user-{uid.hex[:12]}@profile.local"
    username = (md.get("username") or email.split("@")[0] or "user")[:64]
    try:
        profile = ensure_profile(db, uid, email, str(username))
    except ProfileUsernameUnavailableError as e:
        return JSONResponse(
            {
                "detail": "username_unavailable",
                "message": f"Username {e.username!r} is already linked to another account in this app.",
            },
            status_code=409,
        )

    resp = JSONResponse(
        {
            "redirect": (
                "/home" if profile.onboarding_completed_at else "/onboarding/welcome"
            )
        }
    )
    set_auth_cookies(
        resp,
        body.access_token,
        body.refresh_token,
        max_age_access=body.expires_in,
    )
    return resp


@router.get("/login")
def login_form(
    request: Request,
    profile: DependsProfileOptional,
):
    """Render the login form; redirect away if the visitor already has a valid session."""
    if profile:
        return RedirectResponse(
            "/home" if profile.onboarding_completed_at else "/onboarding/welcome",
            status_code=303,
        )
    qerr = request.query_params.get("error")
    query_error = None
    if qerr == "username_conflict":
        query_error = (
            "Your display name is already used by another profile in this app. "
            "Pick a unique username when you register, or update user metadata in Supabase Authentication."
        )
    return request.app.state.templates.TemplateResponse(
        request,
        "auth/login.html",
        {
            "request": request,
            "error": query_error,
            "viewer": profile,
            "dev_shim": settings.AUTH_MODE == "dev_shim",
        },
    )


@router.post("/login")
def login_post(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    """Process the login form: Supabase password grant, ensure local profile, set cookies, redirect.

    Re-renders the form with `error` on any failure (bad credentials, MFA-required without
    completion, username conflict). On success redirects to `/home` (onboarded) or
    `/onboarding/welcome`.
    """
    email = email.strip().lower()
    try:
        data = sign_in_password(email, password)
    except Exception as e:
        return request.app.state.templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "request": request,
                "error": str(e),
                "viewer": None,
                "dev_shim": settings.AUTH_MODE == "dev_shim",
            },
            status_code=400,
        )
    access = data.get("access_token")
    refresh = data.get("refresh_token")
    expires_in = int(data.get("expires_in") or 3600)
    ub = data.get("user") or {}
    if not access or not refresh or not ub.get("id"):
        return request.app.state.templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "request": request,
                "error": "Login incomplete — if MFA is enabled complete /login/mfa (placeholder) or disable MFA for local dev.",
                "viewer": None,
                "dev_shim": settings.AUTH_MODE == "dev_shim",
            },
            status_code=400,
        )
    uid = uuid.UUID(str(ub["id"]))
    md = ub.get("user_metadata") or {}
    username = md.get("username") or email.split("@")[0]
    meta_email = ub.get("email") or email
    try:
        profile = ensure_profile(db, uid, meta_email, str(username))
    except ProfileUsernameUnavailableError:
        return request.app.state.templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "request": request,
                "error": (
                    "Could not finish linking your account (display name already used in this app). "
                    "This is unusual if you registered here — try a different username in Supabase user metadata, or contact support."
                ),
                "viewer": None,
                "dev_shim": settings.AUTH_MODE == "dev_shim",
            },
            status_code=400,
        )

    target = "/home" if profile.onboarding_completed_at else "/onboarding/welcome"
    resp = RedirectResponse(target, status_code=303)
    set_auth_cookies(resp, access, refresh, max_age_access=expires_in)
    return resp


@router.get("/register")
def register_form(request: Request):
    """Render the registration form; the dev_shim branch explains the local-only flow instead."""
    dev = settings.AUTH_MODE == "dev_shim"
    return request.app.state.templates.TemplateResponse(
        request,
        "auth/register.html",
        {
            "request": request,
            "error": None,
            "notice": None,
            "viewer": None,
            "dev_shim": dev,
        },
    )


def _derive_username_from_email(db: Session, email: str) -> str:
    """Derive a unique, NOT-NULL username from the email's local part for `profiles.username`."""
    base = (email.split("@")[0] or "user")[:64]
    if not is_profile_username_in_use(db, base):
        return base
    suffix = secrets.token_hex(3)
    return f"{base[: 64 - 1 - len(suffix)]}_{suffix}"


@router.post("/register")
def register_post(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    """Process the registration form: derive username, Supabase signup, link local profile.

    Username comes from the email's local part with a hex suffix on collision (see
    `_derive_username_from_email`). If Supabase returns an immediate session (email
    confirmation disabled), cookies are set and the user goes straight to onboarding;
    otherwise the user is told to confirm their email and come back to log in.
    """
    if settings.AUTH_MODE == "dev_shim":
        notice = (
            "Registration is disabled in dev_shim mode. "
            "Open /onboarding/welcome?dev_user=yourname once — the name is saved in your session."
        )
        return request.app.state.templates.TemplateResponse(
            request,
            "auth/register.html",
            {
                "request": request,
                "error": None,
                "notice": notice,
                "viewer": None,
                "dev_shim": True,
            },
            status_code=400,
        )
    email = email.strip().lower()
    username = _derive_username_from_email(db, email)
    try:
        data = signup_email_password(email, password, metadata={"username": username})
    except SupabaseAuthError as e:
        err = str(e)
        code = (e.payload or {}).get("error_code") or ""
        if code == "over_email_send_rate_limit" or e.status == 429:
            err = (
                "Supabase email rate limit — too many signup/confirmation emails. "
                "Wait 15–60 minutes, or manage the user under Supabase → Authentication → Users."
            )
        return request.app.state.templates.TemplateResponse(
            request,
            "auth/register.html",
            {
                "request": request,
                "error": err,
                "notice": None,
                "viewer": None,
                "dev_shim": False,
            },
            status_code=400,
        )
    except Exception as e:
        return request.app.state.templates.TemplateResponse(
            request,
            "auth/register.html",
            {
                "request": request,
                "error": str(e),
                "notice": None,
                "viewer": None,
                "dev_shim": False,
            },
            status_code=400,
        )
    sess = data.get("session") or {}
    access = sess.get("access_token")
    refresh = sess.get("refresh_token")
    user_blob = data.get("user") or {}
    uid = user_blob.get("id")
    if access and refresh and uid:
        uid_u = uuid.UUID(str(uid))
        try:
            ensure_profile(db, uid_u, email, username)
        except ProfileUsernameUnavailableError:
            base = username[:55]
            fallback = f"{base}_{uid_u.hex[:8]}"
            ensure_profile(db, uid_u, email, fallback)
        resp = RedirectResponse("/onboarding/welcome", status_code=303)
        set_auth_cookies(resp, access, refresh, max_age_access=int(sess.get("expires_in") or 3600))
        return resp
    return request.app.state.templates.TemplateResponse(
        request,
        "auth/register.html",
        {
            "request": request,
            "error": None,
            "notice": "Confirm your email, then log in.",
            "viewer": None,
            "dev_shim": False,
        },
    )


@router.post("/logout")
def logout(request: Request):
    """Clear auth cookies, best-effort revoke the Supabase session, drop dev_shim identity."""
    access = request.cookies.get(settings.ACCESS_COOKIE_NAME)
    if access and settings.AUTH_MODE == "supabase":
        try:
            sign_out(access)
        except Exception:
            pass
    resp = RedirectResponse("/login", status_code=303)
    clear_auth_cookies(resp)
    if settings.AUTH_MODE == "dev_shim":
        request.session.pop("dev_user", None)
    return resp


@router.get("/login/mfa")
def mfa_form_placeholder(request: Request):
    """Placeholder for the multi-factor-auth step (not wired into login yet)."""
    return request.app.state.templates.TemplateResponse(
        request,
        "auth/mfa.html",
        {"request": request, "viewer": None},
    )
