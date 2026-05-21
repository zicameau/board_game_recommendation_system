"""Request-time logic that doesn't belong in routes or recommenders.

- `embeddings.py` — onboarding label → signed-weight mapping, cached-or-refit user vector.
- `recommendation_view.py` — turn `(game_idx, raw_score)` pairs into UI-ready dicts.
- `bundle_taxonomy.py` — category / mechanic option lists from the active bundle, plus
  the `plain_description` HTML-tag-and-entity cleaner.
- `seed_games.py` — deterministic 10-game onboarding picks, spread across complexity buckets.
- `play_context_field.py` — split/merge for the single 64-char `play_context` DB column.
"""
