"""§5-style contract checks on popularity recommender."""

from pathlib import Path

import numpy as np
import pytest

from app.recommenders.popularity import PopularityRecommender

_FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "bundles" / "popularity-v1-fixture"


@pytest.fixture(scope="session")
def pop_rec() -> PopularityRecommender:
    if not _FIXTURE_ROOT.is_dir():
        pytest.skip("fixture bundle not present")
    return PopularityRecommender.load(_FIXTURE_ROOT)


def test_top_k_length_sorted_desc_exclude(pop_rec: PopularityRecommender):
    emb = np.zeros(8)
    exclude = {0, 5}
    out = pop_rec.top_k(emb, exclude=exclude, k=10)
    assert len(out) == 10
    scores = [s for _, s in out]
    assert scores == sorted(scores, reverse=True)
    idxs = {i for i, _ in out}
    assert idxs.isdisjoint(exclude)
    assert len(idxs) == 10


def test_top_k_no_duplicate_indices(pop_rec: PopularityRecommender):
    out = pop_rec.top_k(np.zeros(8), exclude=set(), k=min(50, len(pop_rec.games_meta)))
    idxs = [i for i, _ in out]
    assert len(idxs) == len(set(idxs))


def test_top_k_finite_scores(pop_rec: PopularityRecommender):
    emb = np.zeros(8)
    for _, sc in pop_rec.top_k(emb, set(), k=5):
        assert np.isfinite(sc)


def test_fit_raises_on_empty_inputs(pop_rec: PopularityRecommender):
    with pytest.raises(ValueError, match="at least one"):
        pop_rec.fit_user_embedding([], [], [])


def test_healthcheck_keys(pop_rec: PopularityRecommender):
    h = pop_rec.healthcheck()
    assert h["model_type"] == "popularity"
    assert "version" in h and "n_items" in h
