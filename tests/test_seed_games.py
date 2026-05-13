"""Deterministic seed game selection across complexity buckets."""

import pandas as pd

from app.services.seed_games import (
    pick_seed_game_indices,
    SEED_GAME_COUNT,
    PER_BUCKET,
)


def test_pick_seed_no_usersrated_stable_order():
    """With no usersrated column, fall back to game_idx ascending."""
    df = pd.DataFrame(
        {
            "game_idx": [5, 2, 9, 1],
            "primary": ["E", "B", "D", "A"],
        }
    )
    assert pick_seed_game_indices(df) == [1, 2, 5, 9][:SEED_GAME_COUNT]


def test_pick_seed_below_threshold_falls_back():
    """Pool smaller than MIN_USERS_RATED — fall through to use the whole frame."""
    df = pd.DataFrame(
        {
            "game_idx": [0, 1, 2],
            "usersrated": [100, 200, 300],
            "boardgamecategory": [["A"], ["B"], ["C"]],
        }
    )
    out = pick_seed_game_indices(df)
    # Without averageweight, hits the legacy path: popularity desc, category diverse.
    assert out == [2, 1, 0]


def test_pick_seed_legacy_path_without_averageweight():
    """No averageweight column => legacy popularity + category diversity preserved."""
    rows = [
        {"game_idx": 10, "usersrated": 100_000, "boardgamecategory": ["Strategy", "City Building"]},
        {"game_idx": 20, "usersrated": 99_000, "boardgamecategory": ["Strategy"]},
        {"game_idx": 30, "usersrated": 98_000, "boardgamecategory": ["Party Game"]},
        {"game_idx": 40, "usersrated": 97_000, "boardgamecategory": ["Card Game"]},
        {"game_idx": 50, "usersrated": 96_000, "boardgamecategory": ["Abstract Strategy"]},
        {"game_idx": 60, "usersrated": 95_000, "boardgamecategory": ["Wargame"]},
        {"game_idx": 70, "usersrated": 94_000, "boardgamecategory": ["Family"]},
        {"game_idx": 80, "usersrated": 93_000, "boardgamecategory": ["Economic"]},
        {"game_idx": 90, "usersrated": 92_000, "boardgamecategory": ["Deduction"]},
        {"game_idx": 100, "usersrated": 91_000, "boardgamecategory": ["Fighting"]},
        {"game_idx": 110, "usersrated": 100_001, "boardgamecategory": ["Strategy"]},
    ]
    df = pd.DataFrame(rows)
    a = pick_seed_game_indices(df)
    b = pick_seed_game_indices(df)
    assert a == b == [110, 30, 40, 50, 60, 70, 80, 90, 100, 10]


def _row(game_idx: int, weight: float, usersrated: int = 50_000, cat: str = "Strategy") -> dict:
    return {
        "game_idx": game_idx,
        "usersrated": usersrated,
        "averageweight": weight,
        "boardgamecategory": [cat],
    }


def test_pick_seed_spans_complexity_buckets():
    """Selection must include games from each complexity bucket."""
    # 4 games in each of 5 buckets — plenty of supply.
    rows = []
    gi = 0
    bucket_centers = [1.5, 2.25, 2.75, 3.25, 4.0]
    for bucket_idx, center in enumerate(bucket_centers):
        for j in range(4):
            rows.append(
                _row(
                    game_idx=gi,
                    weight=center,
                    usersrated=100_000 - bucket_idx * 1000 - j,
                    cat=f"Cat{bucket_idx}{j}",
                )
            )
            gi += 1
    df = pd.DataFrame(rows)

    out = pick_seed_game_indices(df)
    assert len(out) == SEED_GAME_COUNT

    # Confirm coverage: each bucket contributes exactly PER_BUCKET picks.
    weights_by_idx = dict(zip(df["game_idx"], df["averageweight"]))
    bucket_hit_counts = {bi: 0 for bi in range(5)}
    for g in out:
        w = weights_by_idx[g]
        if w < 2.0:
            bucket_hit_counts[0] += 1
        elif w < 2.5:
            bucket_hit_counts[1] += 1
        elif w < 3.0:
            bucket_hit_counts[2] += 1
        elif w < 3.5:
            bucket_hit_counts[3] += 1
        else:
            bucket_hit_counts[4] += 1
    for bi in range(5):
        assert bucket_hit_counts[bi] == PER_BUCKET, (
            f"bucket {bi} got {bucket_hit_counts[bi]}, expected {PER_BUCKET}"
        )


def test_pick_seed_complexity_deterministic():
    """Same input -> same output across repeated calls."""
    rows = []
    gi = 0
    for center in [1.5, 2.25, 2.75, 3.25, 4.0]:
        for j in range(4):
            rows.append(_row(gi, center, usersrated=50_000 - j, cat=f"Cat{j}"))
            gi += 1
    df = pd.DataFrame(rows)
    a = pick_seed_game_indices(df)
    b = pick_seed_game_indices(df)
    assert a == b
    assert len(a) == SEED_GAME_COUNT


def test_pick_seed_complexity_diversity_within_bucket():
    """Within a bucket, prefer different first-categories before repeating."""
    # Single bucket (light) with 5 games — 2 will be picked. They should be
    # the top-2 popular games whose first categories differ.
    rows = [
        _row(1, weight=1.5, usersrated=100_000, cat="Party"),
        _row(2, weight=1.5, usersrated=99_000,  cat="Party"),   # same cat as #1 — should be skipped
        _row(3, weight=1.5, usersrated=98_000,  cat="Family"),  # picked: new cat
        _row(4, weight=1.5, usersrated=97_000,  cat="Family"),
        _row(5, weight=1.5, usersrated=96_000,  cat="Card"),
    ]
    # Pad other buckets so total fills to SEED_GAME_COUNT without overlap.
    pad_gi = 100
    for center in [2.25, 2.75, 3.25, 4.0]:
        for _ in range(2):
            rows.append(_row(pad_gi, center, usersrated=10_000, cat=f"Cat{pad_gi}"))
            pad_gi += 1
    df = pd.DataFrame(rows)
    out = pick_seed_game_indices(df)
    # Light-bucket picks should be 1 (Party, most popular) and 3 (Family, next new cat).
    light_picks = [g for g in out if g <= 5]
    assert light_picks == [1, 3]


def test_pick_seed_short_bucket_redistributes():
    """If one bucket has fewer than PER_BUCKET games, fall through to pool fill."""
    # Heavy bucket has 0 games; others have 3 each (15 - 3 = 12 candidates).
    rows = []
    gi = 0
    for center in [1.5, 2.25, 2.75, 3.25]:
        for j in range(3):
            rows.append(_row(gi, center, usersrated=100_000 - gi, cat=f"Cat{gi}"))
            gi += 1
    df = pd.DataFrame(rows)
    out = pick_seed_game_indices(df)
    # 4 buckets x 2 picks = 8 plus 2 fill-from-pool = 10.
    assert len(out) == SEED_GAME_COUNT


def test_pick_seed_empty_or_missing_columns():
    """Edge cases: empty df, missing game_idx."""
    assert pick_seed_game_indices(None) == []
    assert pick_seed_game_indices(pd.DataFrame()) == []
    assert pick_seed_game_indices(pd.DataFrame({"foo": [1, 2]})) == []
