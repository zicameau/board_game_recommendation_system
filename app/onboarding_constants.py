"""UI-facing constants shared between onboarding templates, routes, and services.

Length caps mirror the SQL `String(64)` columns on `onboarding_selections` so the form
never lets users save more than the DB will keep. `PLAY_CONTEXT_MAIN_OPTIONS` is the
authoritative list of chip choices rendered on `/onboarding/play_context`; removing or
renaming an entry here removes/renames the corresponding chip — and also changes how
`split_play_context` parses stored values, so update tests accordingly.
"""

SEED_GAME_COUNT = 10

# profiles / onboarding string fields (SQL String(64))
PROFILE_TAG_MAX_LEN = 64
PLAY_CONTEXT_DB_MAX_LEN = 64

# Stored value layout: optional preset, or preset + separator + extra (total ≤ PLAY_CONTEXT_DB_MAX_LEN).
PLAY_CONTEXT_DETAIL_SEPARATOR = " · "
# Form sentinel for the "Something else" radio button (the detail text becomes the entire stored value).
PLAY_CONTEXT_OTHER_VALUE = "__OTHER__"

PLAY_CONTEXT_MAIN_OPTIONS: list[str] = [
    "Partner or household",
    "Small group (regulars)",
    "Large group (5+)",
    "Mostly online",
    "FLGS / public meetups",
    "Mix of everything",
]
