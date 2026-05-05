"""Regression: Set-Cookie must be on the same Response object as the 303 redirect."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


def test_login_post_attaches_auth_cookies_to_redirect_response():
    """Cookies were previously set on an unused Response; browser never stored them."""
    uid = uuid.uuid4()
    with patch.multiple(
        "app.api.auth_routes",
        sign_in_password=MagicMock(
            return_value={
                "access_token": "access-test-token",
                "refresh_token": "refresh-test-token",
                "expires_in": 3600,
                "user": {"id": str(uid), "email": "u@test.com"},
            }
        ),
        resolve_login_email=MagicMock(return_value=("u@test.com", None)),
        ensure_profile=MagicMock(
            return_value=SimpleNamespace(onboarding_completed_at=None)
        ),
    ):
        with TestClient(app) as client:
            r = client.post(
                "/login",
                data={"identifier": "u@test.com", "password": "pw"},
                follow_redirects=False,
            )
    assert r.status_code == 303
    assert r.cookies.get("bgg_access") == "access-test-token"
    assert r.cookies.get("bgg_refresh") == "refresh-test-token"
