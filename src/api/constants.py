"""Shared user-facing constants for the workout/challenge flows."""

# Shown on both surfaces (Telegram bot and REST /workouts/parse) when there is
# no in-window challenge. Kept here so the two call sites cannot drift apart.
NO_ACTIVE_CHALLENGES_MSG = (
    "No active challenges right now. Create one with /challenge "
    "or extend an existing challenge's dates."
)
