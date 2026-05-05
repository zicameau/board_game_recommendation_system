"""JWT extraction and Profile resolution."""

from __future__ import annotations

import logging
import os
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.cookies import clear_auth_cookies, set_auth_cookies
from app.auth.supabase_client import refresh_session
from app.auth.supabase_jwt import decode_access_token
from app.config import settings
from app.db.models.profile import Profile
from app.db.session import get_db

logger = logging.getLogger(__name__)


def _decode_access_token(token: str) -> dict:
    try:
        return decode_access_token(token)
    except ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="access_token_expired",
        ) from e
    except InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token") from e


def try_refresh_tokens(request: Request, response: Response) -> str | None:
    refresh_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not refresh_token:
        return None
    try:
        data = refresh_session(refresh_token)
    except Exception:
        return None
    access = data.get("access_token")
    refresh = data.get("refresh_token") or refresh_token
    expires_in = int(data.get("expires_in") or 3600)
    if access:
        set_auth_cookies(response, access, refresh, max_age_access=expires_in)
        return access
    return None


def decode_access_optional(request: Request, response: Response) -> dict | None:
    """Decode JWT from cookie; on any access-token failure, try refresh once."""
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "auth decode: has_access=%s has_refresh=%s",
            bool(request.cookies.get(settings.ACCESS_COOKIE_NAME)),
            bool(request.cookies.get(settings.REFRESH_COOKIE_NAME)),
        )
    token = request.cookies.get(settings.ACCESS_COOKIE_NAME)
    if token:
        try:
            return _decode_access_token(token)
        except HTTPException as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "access token decode failed (%s), attempting refresh",
                    e.detail,
                )
            # fall through — try refresh for expiry, bad signature, alg mismatch, etc.
    new_tok = try_refresh_tokens(request, response)
    if not new_tok:
        return None
    try:
        return _decode_access_token(new_tok)
    except HTTPException:
        return None


def resolve_login_email(db: Session, identifier: str) -> tuple[str | None, Profile | None]:
    ident = identifier.strip()
    if "@" in ident:
        stmt = select(Profile).where(Profile.email == ident.lower())
        prof = db.execute(stmt).scalar_one_or_none()
        return ident.lower(), prof
    stmt = select(Profile).where(Profile.username == ident)
    prof = db.execute(stmt).scalar_one_or_none()
    if prof:
        return prof.email, prof
    return None, None


def _normalize_username(desired: str) -> str:
    """Canonical display username from auth metadata (trim, default, DB String(64) cap)."""
    s = (desired or "").strip() or "user"
    return s[:64]


class ProfileUsernameUnavailableError(Exception):
    """Another profile row already uses this username — cannot match auth without a collision."""

    def __init__(self, username: str):
        self.username = username
        super().__init__(username)


def _profile_by_username(db: Session, username: str) -> Profile | None:
    return db.execute(select(Profile).where(Profile.username == username)).scalar_one_or_none()


def is_profile_username_in_use(db: Session, username: str) -> bool:
    """True if a `profiles` row already uses this display name (after the same normalization as auth)."""
    n = _normalize_username(username)
    return _profile_by_username(db, n) is not None


def _sync_profile_from_auth(
    db: Session,
    profile: Profile,
    email: str,
    username: str,
) -> None:
    """Keep email/username aligned with Supabase. Username must stay unique in `profiles`."""
    desired_email = email.strip()
    desired_username = _normalize_username(username)
    changed = False
    if profile.email != desired_email:
        profile.email = desired_email
        changed = True
    if profile.username != desired_username:
        holder = _profile_by_username(db, desired_username)
        if holder is not None and holder.id != profile.id:
            logger.error(
                "cannot sync profile username %r to user %s: already held by profile %s",
                desired_username,
                profile.id,
                holder.id,
            )
        else:
            profile.username = desired_username
            changed = True
    if changed:
        db.add(profile)
        db.commit()
        db.refresh(profile)


def ensure_profile(db: Session, user_id: uuid.UUID, email: str, username: str) -> Profile:
    desired_email = email.strip()
    desired_username = _normalize_username(username)

    profile = db.get(Profile, user_id)
    if profile is not None:
        _sync_profile_from_auth(db, profile, desired_email, desired_username)
        return profile

    # profiles.id FK → auth.users.id. With DATABASE_URL pointed at local Postgres while
    # Supabase Auth lives in the cloud, the stub auth.users table has no row yet — insert a
    # placeholder key so the profile insert succeeds. On Supabase-hosted Postgres the row
    # usually exists already; ON CONFLICT no-ops. If the DB role cannot insert into
    # auth.users, savepoint rollback leaves the session usable for the profile row.
    try:
        with db.begin_nested():
            db.execute(
                text(
                    "INSERT INTO auth.users (id) VALUES (CAST(:id AS uuid)) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"id": str(user_id)},
            )
    except Exception:
        pass

    holder = _profile_by_username(db, desired_username)
    if holder is not None and holder.id != user_id:
        raise ProfileUsernameUnavailableError(desired_username)

    profile = Profile(id=user_id, email=desired_email, username=desired_username)
    db.add(profile)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        profile = db.get(Profile, user_id)
        if profile is not None:
            _sync_profile_from_auth(db, profile, desired_email, desired_username)
            return profile
        other = _profile_by_username(db, desired_username)
        if other is not None and other.id != user_id:
            raise ProfileUsernameUnavailableError(desired_username) from None
        raise
    db.refresh(profile)
    return profile


def get_profile_optional(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Profile | None:
    if settings.AUTH_MODE == "dev_shim":
        from app.auth import dev_shim

        request.state.auth_claims = None
        profile = dev_shim.get_profile_for_dev_header(request, db)
        request.state.profile = profile
        return profile

    claims = decode_access_optional(request, response)
    if not claims:
        request.state.auth_claims = None
        return None
    request.state.auth_claims = claims
    uid = uuid.UUID(str(claims["sub"]))
    profile = db.get(Profile, uid)
    if profile is None:
        md = claims.get("user_metadata") or {}
        email = (claims.get("email") or md.get("email") or "").strip()
        if not email:
            email = f"user-{uid.hex[:12]}@profile.local"
        username = (md.get("username") or email.split("@")[0] or "user")[:64]
        profile = ensure_profile(db, uid, email, str(username))
    request.state.profile = profile
    return profile


def require_login(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Profile:
    """Redirect unauthenticated browsers to /login."""
    profile = get_profile_optional(request, response, db)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )
    _maybe_require_aal(claims=request.state.auth_claims or {})
    return profile


def _maybe_require_aal(claims: dict) -> None:
    """If STRICT_AAL=1 env and project uses MFA (aal2), enforce presence."""
    if os.environ.get("STRICT_AAL") != "1":
        return
    aal = claims.get("aal")
    if aal is None:
        return
    if str(aal) != "aal2":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="mfa_required",
        )


DependsProfileOptional = Annotated[Profile | None, Depends(get_profile_optional)]
DependsLogin = Annotated[Profile, Depends(require_login)]
