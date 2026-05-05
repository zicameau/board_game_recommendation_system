"""Recommendation list enrichment (scores + copy)."""

from unittest.mock import MagicMock

import pandas as pd

from app.services.recommendation_view import (
    explain_recommendation,
    normalize_match_scores,
    thumbnail_url_from_row,
)
from unittest.mock import MagicMock


def test_normalize_match_scores_min_max():
    out = normalize_match_scores([3.0, 3.5, 4.0])
    assert len(out) == 3
    assert out[0]["match_pct"] == 0
    assert out[0]["match_10"] == 1.0
    assert out[2]["match_pct"] == 100
    assert out[2]["match_10"] == 10.0


def test_normalize_ties_all_identical():
    out = normalize_match_scores([2.0, 2.0, 2.0])
    assert all(x["match_pct"] == 100 for x in out)
    assert all(x["match_10"] == 10.0 for x in out)


def test_thumbnail_protocol_relative():
    row = pd.Series({"thumbnail": "//cf.geekdo-images.com/foo.jpg"})
    assert thumbnail_url_from_row(row).startswith("https:")


def test_explain_embedding_fallback():
    sel = MagicMock()
    sel.liked_categories = []
    sel.liked_mechanics = []
    sel.disliked_categories = []
    sel.disliked_mechanics = []
    row = pd.Series({"boardgamecategory": None, "boardgamemechanic": None})
    text = explain_recommendation(sel, row)
    assert "embedding" in text.lower() or "onboarding" in text.lower()
