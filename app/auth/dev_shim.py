"""Local-only auth shim that lets you work without a Supabase project.

Resolution order on every protected route (see `get_profile_for_dev_header`):

    1. `X-Dev-User` header  (CLI / API clients)
    2. `?dev_user=<name>` query parameter  (first browser visit)
    3. Signed-session `dev_user` key  (set by step 1 or 2 on first contact, then sticky)

The resolved name maps to a deterministic `uuid.uuid5(NAMESPACE_DNS, name)`, which is used
both as the `Profile.id` and as a placeholder `auth.users.id` (the FK target). This means
the same dev name always reproduces the same local user across runs.

Hard-gated by `assert_dev_shim_safe()` — any code path that touches a Profile via this
module will raise `RuntimeError` outside `ENVIRONMENT=local + AUTH_MODE=dev_shim`.
"""

from __future__ import annotations

import uuid

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.profile import Profile


def assert_dev_shim_safe() -> None:
    """Refuse to run dev-shim code paths outside `ENVIRONMENT=local + AUTH_MODE=dev_shim`."""
    if settings.ENVIRONMENT != "local" or settings.AUTH_MODE != "dev_shim":
        raise RuntimeError(
            "dev_shim forbidden outside ENVIRONMENT=local + AUTH_MODE=dev_shim"
        )



def _ensure_auth_stub_user(session: Session, user_id: uuid.UUID) -> None:
    """Insert a placeholder `auth.users` row so the `profiles.id` FK is satisfied locally."""
    session.execute(
        text(
            """
            INSERT INTO auth.users (id)
            VALUES (CAST(:id AS uuid))
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id": str(user_id)},
    )


def dev_shim_username_from_request(request: Request) -> str | None:
    """Resolve dev identity: ``X-Dev-User`` header, else ``dev_user`` query (browser-friendly)."""
    raw = request.headers.get("X-Dev-User") or request.query_params.get("dev_user")
    if not raw:
        return None
    u = raw.strip()
    return u[:128] if u else None


def dev_shim_resolve_username(request: Request) -> str | None:
    """Header/query wins; otherwise reuse last value from signed session (survives link navigation)."""
    u = dev_shim_username_from_request(request)
    if u:
        request.session["dev_user"] = u
        return u
    s = request.session.get("dev_user")
    if isinstance(s, str):
        t = s.strip()[:128]
        if t:
            return t
    request.session.pop("dev_user", None)
    return None


def get_profile_for_dev_header(request: Request, db: Session) -> Profile | None:
    """Resolve the dev identity, upsert its `Profile`, and return it (or `None` if no identity available)."""
    assert_dev_shim_safe()
    u = dev_shim_resolve_username(request)
    if not u:
        return None
    email = f"{u}@dev.local"
    namespace = uuid.NAMESPACE_DNS
    user_id = uuid.uuid5(namespace, u)
    _ensure_auth_stub_user(db, user_id)
    db.commit()

    profile = db.get(Profile, user_id)
    if profile is None:
        profile = Profile(id=user_id, email=email, username=u)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    elif profile.username != u:
        profile.username = u
        profile.email = email
        db.commit()
        db.refresh(profile)
    return profile
