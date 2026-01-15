# Code Review: Feature 0008 - Evening reminders (9pm/10pm/11pm) + persistent reminder setting (Re-review)

**Review Date:** 2026-01-14  
**Reviewer:** Codex CLI (GPT-5.2)  
**Plan Reference:** `docs/features/0008_PLAN.md`

---

## Executive Summary

NEEDS CHANGES — The earlier issues around scheduler lifecycle and Telegram failure handling are fixed, and reminder tests were added. However, there are still a couple of correctness gaps and a test isolation bug that will cause the new test suite to fail.

Top issues to address:
1. **Reminder tests patch async functions with `MagicMock` instead of `AsyncMock`**, which will raise `TypeError: object MagicMock can't be used in 'await'`.
2. **Idempotency is still not atomic in the reminder send path** — `try_mark_hour_sent()` was added but is not used, so duplicate sends are still possible under multi-worker races.
3. **Legacy reminder flow still ignores `is_reminder_active`**; if `/jobs/daily-reminder` is called without an hour, it can send reminders even when disabled.

---

## Plan Adherence (Current State)

### ✅ Implemented and Fixed Since Last Review
- **Telegram failure handling** now gates `mark_hour_sent()` on successful send (`result is not None`).
- **Scheduler lifecycle** now uses a FastAPI lifespan handler, with cancellation on shutdown and env gating via `ENABLE_REMINDER_SCHEDULER`.
- **Admin job endpoint** now accepts `hour=21/22/23` and forwards to the evening reminder flow.
- **Reminder test coverage** added in `tests/services/test_reminders.py`.
- **LLM context unit mixing** resolved by using `remaining_summary` with per-unit totals.

### ⚠️ Remaining Gaps vs Plan Intent
- **Atomic idempotency is still not wired into the send path**.
- **Legacy mode still bypasses `is_reminder_active`**, which conflicts with “respect reminder setting” guidance.

---

## High-Impact Issues

### 1) Reminder tests will fail due to `MagicMock` on awaited calls
- **Where**:
  - `tests/services/test_reminders.py` patches async call sites with default `patch(...)` (e.g., `send_telegram_message`, `compute_evening_reminder`).
- **Why**:
  - These functions are awaited in production code, but `patch()` without `new_callable=AsyncMock` produces a `MagicMock` that is not awaitable.
- **Impact**:
  - Test suite raises `TypeError` when these patched functions are awaited.
- **Recommendation**:
  - Use `new_callable=AsyncMock` for `send_telegram_message` and `compute_evening_reminder` patches; optionally set `return_value` on the `AsyncMock`.

### 2) Idempotency still not atomic (race risk in multi-worker)
- **Where**: `app/services/workout_service.py::send_evening_reminder`
- **Why**:
  - The flow still does `check_already_sent()` then `mark_hour_sent()` separately.
  - `try_mark_hour_sent()` exists in `src/core/repositories.py` but is not used.
- **Impact**:
  - Two workers can send the reminder simultaneously and both mark “sent”.
- **Recommendation**:
  - Replace the check/mark pair with `try_mark_hour_sent()` (or wrap in a transaction with `select_for_update`) so only one worker wins.

### 3) Legacy reminder path ignores `is_reminder_active`
- **Where**: `app/services/workout_service.py::check_daily_reminders` (hour=None path)
- **Impact**:
  - `/jobs/daily-reminder` (without `hour`) can still send “missing you” reminders even if reminders are disabled in settings.
- **Recommendation**:
  - Short-circuit legacy reminders when `is_reminder_active` is `False`, or clearly separate legacy reminders into a different endpoint and update docs accordingly.

---

## Tests Review (Updated)

### ✅ Good
- `tests/services/test_reminders.py` includes coverage for:
  - disabled reminders
  - no chat id
  - idempotency
  - incomplete vs complete challenges
  - `daily_target is None` behavior
  - mixed units in LLM context
  - Telegram failure not marked as sent

### ⚠️ Needs Fix
- Async mocks for awaited functions (see issue #1 above).

---

## Optional Cleanups

- `AppSettingsRepository.try_mark_hour_sent()` is currently unused; if you adopt it in the send path, keep it. Otherwise, consider removing to avoid dead code.

