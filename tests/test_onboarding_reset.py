"""POST /onboarding/reset wipes user recommendation state and sends them back to welcome."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.auth.deps import require_login
from app.db.models.onboarding import OnboardingSelection
from app.db.models.user_embedding import UserEmbedding
from app.db.session import get_db
from app.main import app


def _make_fake_user(*, onboarding_completed_at: object = "set") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
        username="resettest",
        email="reset@test.com",
        onboarding_completed_at=onboarding_completed_at,
    )


def _make_fake_db(*, has_embedding: bool, has_selection: bool) -> MagicMock:
    db = MagicMock()
    emb_row = MagicMock(spec=UserEmbedding) if has_embedding else None
    sel_row = MagicMock(spec=OnboardingSelection) if has_selection else None

    def _get(model, _pk):
        if model is UserEmbedding:
            return emb_row
        if model is OnboardingSelection:
            return sel_row
        return None

    db.get.side_effect = _get
    db._fixtures = SimpleNamespace(emb=emb_row, sel=sel_row)
    return db


def test_reset_deletes_state_and_redirects_to_welcome():
    user = _make_fake_user()
    db = _make_fake_db(has_embedding=True, has_selection=True)

    app.dependency_overrides[require_login] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            r = client.post("/onboarding/reset", follow_redirects=False)
    finally:
        app.dependency_overrides.pop(require_login, None)
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 303
    assert r.headers.get("location") == "/onboarding/welcome"

    deleted = [c.args[0] for c in db.delete.call_args_list]
    assert db._fixtures.emb in deleted
    assert db._fixtures.sel in deleted
    assert len(deleted) == 2

    assert user.onboarding_completed_at is None
    db.commit.assert_called_once()


def test_reset_is_idempotent_when_rows_missing():
    """If a user has no embedding / no selection yet, reset still clears the timestamp and redirects."""
    user = _make_fake_user()
    db = _make_fake_db(has_embedding=False, has_selection=False)

    app.dependency_overrides[require_login] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            r = client.post("/onboarding/reset", follow_redirects=False)
    finally:
        app.dependency_overrides.pop(require_login, None)
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 303
    assert r.headers.get("location") == "/onboarding/welcome"
    db.delete.assert_not_called()
    assert user.onboarding_completed_at is None
    db.commit.assert_called_once()


def test_home_redirects_to_welcome_after_reset_clears_completion():
    """End-to-end gate: once onboarding_completed_at is None, GET /home bounces to /onboarding/welcome."""
    user = _make_fake_user(onboarding_completed_at=None)
    db = _make_fake_db(has_embedding=False, has_selection=False)

    app.dependency_overrides[require_login] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            r = client.get("/home", follow_redirects=False)
    finally:
        app.dependency_overrides.pop(require_login, None)
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 303
    assert r.headers.get("location") == "/onboarding/welcome"
