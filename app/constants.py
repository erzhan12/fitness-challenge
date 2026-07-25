"""Application-wide constants."""

# Default/fallback reminder hours. Per-user reminder_hours (any hour 0-23) is
# the source of truth for scheduling; this is only used by the scheduler for
# sleep timing when no active user schedules exist yet.
DEFAULT_REMINDER_HOURS = [13, 21, 22]

# Upper-bound limits for LLM-created challenges
MAX_DURATION_DAYS = 365
MAX_DAILY_TARGET = 10_000

# How far from today a challenge start_date can be (past or future)
MAX_START_DATE_DRIFT_DAYS = 365
