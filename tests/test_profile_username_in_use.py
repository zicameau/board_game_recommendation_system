"""Registration-time username availability (profiles.username)."""

from unittest.mock import MagicMock

from app.auth.deps import is_profile_username_in_use


def test_in_use_when_row_exists():
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = object()
    db.execute.return_value = result
    assert is_profile_username_in_use(db, "alice") is True


def test_free_when_no_row():
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    assert is_profile_username_in_use(db, "bob") is False
