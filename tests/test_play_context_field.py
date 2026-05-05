from app.onboarding_constants import PLAY_CONTEXT_OTHER_VALUE
from app.services.play_context_field import merge_play_context, split_play_context


def test_split_merge_roundtrip_preset_only():
    p, d = split_play_context("Solo mainly")
    assert p == "Solo mainly" and d == ""
    assert merge_play_context(p, d) == "Solo mainly"


def test_split_merge_preset_and_detail():
    combined = merge_play_context("Solo mainly", "evenings")
    assert combined == "Solo mainly · evenings"
    p, d = split_play_context(combined)
    assert p == "Solo mainly" and d == "evenings"


def test_merge_other_only_detail():
    assert merge_play_context(PLAY_CONTEXT_OTHER_VALUE, "mixed friends") == "mixed friends"
    p, d = split_play_context("mixed friends")
    assert p == PLAY_CONTEXT_OTHER_VALUE and d == "mixed friends"


def test_merge_empty():
    assert merge_play_context("", "") is None
    assert merge_play_context("", None) is None


def test_merge_truncates_to_64():
    long_d = "x" * 100
    out = merge_play_context("", long_d)
    assert out is not None and len(out) == 64
