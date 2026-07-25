# Design: Per-user editable reminder hours + JSON idempotency

**Issue:** [#34](https://github.com/erzhan12/fitness-challenge/issues/34)  
**Date:** 2026-07-24  
**Status:** Draft for review

## Goal

Make reminder hours per-user and editable in Django admin (default `[13, 21, 22]`), store send idempotency as a flexible JSON map, and cut the live reminder path fully off the `app_settings` singleton onto `user_settings`.

## Decisions (locked)

| Topic | Choice |
|---|---|
| Edit surface | Django admin only |
| Hours storage | `UserSettings.reminder_hours` (per-user JSON list) |
| Default hours | `[13, 21, 22]` (23 dropped) |
| Empty hours list | No sends (no fallback to default) |
| Cutover | Full: send / claim / chat_id / `is_reminder_active` → `UserSettings` |
| Idempotency | JSON map `last_reminder_sent_dates` on `UserSettings` |
| Rejected | `ReminderDispatch` log table; hard-coded `last_reminder_13_date` columns |
| Scheduler | Wake on union of enabled users’ hours; per-user claim + send |
| Midday toggle | None — shares `is_reminder_active` |

## Current state

- Live path: `send_evening_reminder` uses `app_settings_repo` for toggle, chat id, and `try_mark_hour_sent` → `last_reminder_{21,22,23}_date` (filled in prod).
- `user_settings` has the same three date columns but they are empty (never written).
- Hours hard-coded: `REMINDER_HOURS = [21, 22, 23]` in `app/constants.py`.

## Data model

### `UserSettings`

- **Add** `reminder_hours`: `JSONField`, default `[13, 21, 22]`
  - Validate: list of ints in `0–23`, unique; normalize to sorted ascending on save
- **Add** `last_reminder_sent_dates`: `JSONField`, default `{}`
  - Shape: `{"13": "2026-07-24", "21": "2026-07-24"}` (hour as string key → ISO date)
- **Remove** `last_reminder_21_date`, `last_reminder_22_date`, `last_reminder_23_date`

### `AppSettings`

- **Remove** reminder fields: `is_reminder_active`, `telegram_chat_id`, `last_reminder_*`
- **Keep** global-only fields (e.g. `is_registration_open`)

### Migration

1. Add new JSON fields on `user_settings`.
2. Copy singleton `app_settings.last_reminder_{21,22,23}_date` into the default/legacy user’s `last_reminder_sent_dates`.
3. Set that user’s `reminder_hours` to `[13, 21, 22]` (and default for other users / new rows).
4. Drop old hour-specific date columns from both tables; drop reminder fields from `app_settings`.

## Runtime

### Constants

- Replace `REMINDER_HOURS` with `DEFAULT_REMINDER_HOURS = [13, 21, 22]`.
- Live schedule always reads each user’s `reminder_hours` (never assume the constant equals every user’s list).

### Scheduler (`reminder_scheduler.py`)

- Next wake = earliest upcoming local hour across users with `is_reminder_active` and non-empty `reminder_hours` (and ideally a chat id).
- If no such users: sleep using `DEFAULT_REMINDER_HOURS` for timing only (no sends until users exist).
- On wake at hour `H`: select users where `is_reminder_active` and `H ∈ reminder_hours`.

### Send path

- Refactor `send_evening_reminder(hour)` to iterate matching users (or split into per-user helper).
- Per user:
  1. Skip if no `telegram_chat_id`. **Do not** fall back to global `TARGET_CHAT_ID` (wrong under multi-user).
  2. Atomic claim: set `last_reminder_sent_dates[str(H)] = today` only if missing or not today (conditional update; same race semantics as `try_mark_hour_sent`).
  3. `compute_evening_reminder` for that user’s challenges; send; on Telegram failure or unexpected error, clear that hour’s claim for today so a later worker/run can retry.
  4. Stale JSON keys for hours no longer in `reminder_hours` (e.g. migrated `"23"`) are ignored and may remain.
- Expired-challenge sweep: once per wake, all users, fail-open (unchanged intent).

### Admin

- Editable: `reminder_hours`, `is_reminder_active`, `telegram_chat_id`
- Read-only or collapsed: `last_reminder_sent_dates`
- Invalid `reminder_hours` → validation error

### API

- No new fields for hours (admin-only).
- Existing settings endpoints continue for `is_reminder_active` / chat id as already exposed; do not add `reminder_hours` to PATCH in this feature.

## Testing

- Default `reminder_hours == [13, 21, 22]` on create / get_or_create
- Empty `reminder_hours` → user never selected for send
- JSON claim: first send wins; second same user/hour/day skipped; claim cleared on send failure
- Scheduler next-wake from union of two users with different hour lists
- User without hour `H` not messaged at `H`
- Migration data path: `app_settings` dates → legacy user JSON keys `"21"`, `"22"`, `"23"` as present

## Out of scope

- REST API to edit hours
- Separate midday on/off toggle
- `ReminderDispatch` table
- Per-minute custom times (hours only)

## Success criteria

- Admin can set a user’s hours to e.g. `[13, 21, 22]` or `[13, 21]` without a migration
- 13:00 fires for users who include `13`
- Idempotency works without hour-named columns
- `app_settings` no longer participates in reminder send/claim
- RULES.md documents the new model and default hours
