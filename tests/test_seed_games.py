"""Deterministic seed game selection."""

import pandas as pd

from app.services.seed_games import pick_seed_game_indices, SEED_GAME_COUNT


def test_pick_seed_no_usersrated_stable_order():
    df = pd.DataFrame(
        {
            "game_idx": [5, 2, 9, 1],
            "primary": ["E", "B", "D", "A"],
        }
    )
    assert pick_seed_game_indices(df) == [1, 2, 5, 9][:SEED_GAME_COUNT]


def test_pick_seed_popularity_diversity_deterministic():
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


def test_pick_seed_below_threshold_falls_back():
    df = pd.DataFrame(
        {
            "game_idx": [0, 1, 2],
            "usersrated": [100, 200, 300],
            "boardgamecategory": [["A"], ["B"], ["C"]],
        }
    )
    out = pick_seed_game_indices(df)
    assert out == [2, 1, 0]
