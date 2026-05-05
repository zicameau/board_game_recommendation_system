"""Onboarding UI constants — aligned with DB column sizes where applicable."""

SEED_GAME_COUNT = 10

# profiles / onboarding string fields (SQL String(64))
PROFILE_TAG_MAX_LEN = 64
PLAY_CONTEXT_DB_MAX_LEN = 64

# Stored: optional preset, or preset + separator + extra (total ≤ PLAY_CONTEXT_DB_MAX_LEN).
PLAY_CONTEXT_DETAIL_SEPARATOR = " · "
# Form sentinel for "Something else" (freeform in detail only).
PLAY_CONTEXT_OTHER_VALUE = "__OTHER__"

PLAY_CONTEXT_MAIN_OPTIONS: list[str] = [
    "Solo mainly",
    "Partner or household",
    "Small group (regulars)",
    "Large group (5+)",
    "Mostly online",
    "FLGS / public meetups",
    "Mix of everything",
]
