"""Supabase Auth JSON → user-visible messages."""

from app.auth.supabase_client import _auth_error_message


def test_uses_msg_like_gotrue():
    data = {
        "code": 400,
        "error_code": "invalid_credentials",
        "msg": "Invalid login credentials",
    }
    assert _auth_error_message(data) == "Invalid login credentials"


def test_fallback_order():
    assert _auth_error_message({}) == "Request failed"
    assert _auth_error_message({"error_description": "OAuth style"}) == "OAuth style"
