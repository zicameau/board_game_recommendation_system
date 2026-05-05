"""Pure parsing for dev shim identity (no DB)."""

from unittest.mock import MagicMock

from app.auth.dev_shim import dev_shim_resolve_username, dev_shim_username_from_request


def test_header_wins_over_query():
    r = MagicMock()
    r.headers.get = lambda key, default=None: "alice" if key == "X-Dev-User" else default
    r.query_params.get = lambda key, default=None: "bob" if key == "dev_user" else default
    assert dev_shim_username_from_request(r) == "alice"


def test_query_used_when_no_header():
    r = MagicMock()
    r.headers.get = lambda key, default=None: None
    r.query_params.get = lambda key, default=None: "carol" if key == "dev_user" else default
    assert dev_shim_username_from_request(r) == "carol"


def test_blank_returns_none():
    r = MagicMock()
    r.headers.get = lambda key, default=None: "   " if key == "X-Dev-User" else default
    r.query_params.get = lambda key, default=None: None
    assert dev_shim_username_from_request(r) is None


def test_truncates_long_value():
    r = MagicMock()
    long_name = "x" * 200
    r.headers.get = lambda key, default=None: long_name if key == "X-Dev-User" else default
    r.query_params.get = lambda key, default=None: None
    assert len(dev_shim_username_from_request(r) or "") == 128


def test_resolve_writes_session_from_header():
    r = MagicMock()
    r.headers.get = lambda key, default=None: "zed" if key == "X-Dev-User" else default
    r.query_params.get = lambda key, default=None: None
    r.session = {}
    assert dev_shim_resolve_username(r) == "zed"
    assert r.session["dev_user"] == "zed"


def test_resolve_reads_session_when_no_header_or_query():
    r = MagicMock()
    r.headers.get = lambda key, default=None: None
    r.query_params.get = lambda key, default=None: None
    r.session = {"dev_user": "persisted"}
    assert dev_shim_resolve_username(r) == "persisted"


def test_resolve_clears_whitespace_only_session():
    r = MagicMock()
    r.headers.get = lambda key, default=None: None
    r.query_params.get = lambda key, default=None: None
    sess = {"dev_user": "  \t  "}
    r.session = sess
    assert dev_shim_resolve_username(r) is None
    assert "dev_user" not in sess


def test_query_updates_stale_session_value():
    r = MagicMock()
    r.headers.get = lambda key, default=None: None
    r.query_params.get = lambda key, default=None: "new" if key == "dev_user" else None
    r.session = {"dev_user": "old"}
    assert dev_shim_resolve_username(r) == "new"
    assert r.session["dev_user"] == "new"
