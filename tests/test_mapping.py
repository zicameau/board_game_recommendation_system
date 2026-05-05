"""Onboarding → signed triple mapping (§5.3.2)."""

from app.services.embeddings import map_game_ratings_to_signed


def test_maps_love_like_to_positives_weights():
    gr = [{"game_idx": 1, "label": "love"}, {"game_idx": 2, "label": "like"}]
    pos, neg, w = map_game_ratings_to_signed(gr)
    assert pos == [1, 2]
    assert neg == []
    assert w == [1.0, 0.5]


def test_skips_never_played():
    gr = [{"game_idx": 0, "label": "never_played"}, {"game_idx": 9, "label": "hate"}]
    pos, neg, w = map_game_ratings_to_signed(gr)
    assert pos == []
    assert neg == [9]
    assert w == [-1.0]


def test_hate_dislike_weights_negative():
    gr = [{"game_idx": 3, "label": "dislike"}, {"game_idx": 4, "label": "hate"}]
    _, neg, w = map_game_ratings_to_signed(gr)
    assert sorted(neg) == [3, 4]
    assert sorted(w, reverse=True) == [-0.5, -1.0]
