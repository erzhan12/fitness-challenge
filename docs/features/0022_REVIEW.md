# Feature 0022 Code Review — Per-user reminder hours

## Findings

No blocking findings.

The implementation matches the plan's required cutover shape:

- `UserSettings.reminder_hours` and `last_reminder_sent_dates` use top-level callable defaults and model-level normalization from both `clean()` and `save()`.
- Migration `0010` is additive-only, and migration `0011` performs the data cutover before destructive drops.
- The cutover copies the singleton kill switch, singleton chat id, and authoritative legacy idempotency dates according to the plan, including the blocked migration path when a global chat id has no `telegram_user_id=0` owner.
- Reminder idempotency uses conditional SQLite JSON updates and preserves other hour keys.
- Scheduler wake calculation reads the union of active per-user reminder hours, falls back to `[13, 21, 22]` only for sleep timing, and keeps the locked due target before config re-evaluation.
- `send_evening_reminder()` is per-user, scopes active challenges by `user_id`, removes the global `TARGET_CHAT_ID` fallback, and contains per-user failures.
- The admin job accepts any hour `0-23`, including `0`.
- Django admin exposes editable `reminder_hours` and read-only `last_reminder_sent_dates`.

## Tests Reviewed

Coverage exists for the new model validation, SQLite JSON idempotency including concurrency, active-hour query filtering, migration `0010 -> 0011`, scheduler retargeting/due-send ordering, per-user send behavior, legacy reminder scoping, rest-day behavior, and admin-field cleanup.

Verification run:

```text
uv run pytest -q
457 passed, 1 warning in 2.05s
```

Residual risk: `get_users_for_reminder_hour()` and `get_distinct_active_reminder_hours()` intentionally use ORM prefiltering followed by Python-side JSON array membership because SQLite JSON array `contains` is unreliable. That is acceptable for the current app size and SQLite-only requirement, but it is the main place to revisit if the user/settings table grows substantially.
