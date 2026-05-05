"""decode_access_optional: refresh fallback when access JWT fails (any reason)."""

from __future__ import annotations

from unittest.mock import patch

from fastapi import HTTPException, status
from starlette.responses import Response

from app.auth import deps
from app.config import settings


def _fake_request(cookies: dict):
    class R:
        pass

    r = R()
    r.cookies = cookies
    return r


def test_decode_access_optional_refreshes_when_access_invalid():
    """Bad access cookie + working refresh yields claims from new access token."""
    request = _fake_request(
        {
            settings.ACCESS_COOKIE_NAME: "bad_access",
            settings.REFRESH_COOKIE_NAME: "refresh_secret",
        }
    )
    response = Response()

    with patch.object(deps, "try_refresh_tokens", return_value="new_access") as tr:
        with patch.object(deps, "_decode_access_token") as dec:
            dec.side_effect = [
                HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token"),
                {"sub": "00000000-0000-4000-8000-000000000042", "email": "t@example.test"},
            ]
            out = deps.decode_access_optional(request, response)
    assert out is not None
    assert out["sub"] == "00000000-0000-4000-8000-000000000042"
    dec.assert_any_call("bad_access")
    dec.assert_any_call("new_access")
    tr.assert_called_once_with(request, response)


def test_decode_access_optional_returns_claims_on_valid_access_without_refresh():
    request = _fake_request({settings.ACCESS_COOKIE_NAME: "good_access"})
    response = Response()

    with patch.object(deps, "try_refresh_tokens") as tr:
        with patch.object(deps, "_decode_access_token") as dec:
            dec.return_value = {
                "sub": "11111111-1111-4111-8111-111111111111",
                "email": "ok@example.test",
            }
            out = deps.decode_access_optional(request, response)
    assert out is not None
    assert out["sub"] == "11111111-1111-4111-8111-111111111111"
    dec.assert_called_once_with("good_access")
    tr.assert_not_called()


def test_decode_access_optional_none_when_invalid_and_refresh_fails():
    request = _fake_request(
        {
            settings.ACCESS_COOKIE_NAME: "bad",
            settings.REFRESH_COOKIE_NAME: "ref",
        }
    )
    response = Response()

    with patch.object(deps, "try_refresh_tokens", return_value=None):
        with patch.object(deps, "_decode_access_token") as dec:
            dec.side_effect = HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid_token",
            )
            out = deps.decode_access_optional(request, response)
    assert out is None
