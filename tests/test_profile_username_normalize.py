"""Display username normalization for profile/auth alignment."""

from app.auth.deps import _normalize_username


def test_normalize_defaults_and_trim():
    assert _normalize_username("") == "user"
    assert _normalize_username("   ") == "user"
    assert _normalize_username("  ada  ") == "ada"


def test_normalize_truncates_to_64():
    long = "x" * 100
    assert len(_normalize_username(long)) == 64
