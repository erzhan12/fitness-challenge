"""Application-wide constants."""

# Reminder hours (9pm, 10pm, 11pm in 24-hour format)
REMINDER_HOURS = [21, 22, 23]

# Upper-bound limits for LLM-created challenges
MAX_DURATION_DAYS = 365
MAX_DAILY_TARGET = 10_000

# How far from today a challenge start_date can be (past or future)
MAX_START_DATE_DRIFT_DAYS = 365
