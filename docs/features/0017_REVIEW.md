# 0017 Review — Telegram `/challenge` Command

## Scope and Method
- Reviewed implementation against [0017_PLAN.md](./0017_PLAN.md) and the checklist in [commands/code_review.md](../../commands/code_review.md).
- Inspected:
  - `app/models.py`
  - `app/services/challenge_flow.py`
  - `app/services/telegram_client.py`
  - `app/routers/telegram.py`
  - `app/services/workout_service.py`
  - `src/api/services.py`
  - test suite under `tests/`
- Executed:
  - `uv run pytest -q tests/api/test_challenges.py tests/services/test_workout_service.py` (91 passed)
  - `uv run pytest -q tests/services/test_registration_flow.py` (7 passed)
  - `uv run ruff check app/models.py app/services/challenge_flow.py app/services/telegram_client.py app/routers/telegram.py app/services/workout_service.py src/api/services.py` (1 lint finding)

## Findings (ordered by severity)

### [P2] New Telegram `/challenge` flow has no direct automated test coverage
- The plan explicitly required tests for:
  - `challenge_flow.py` state/expiry/rate-limit behavior.
  - `process_callback_query` confirm/cancel/expired branches.
  - `/challenge` command routing + awaiting-prompt interception.
  - Inline keyboard preview formatting.
- Current test suite does not contain these tests:
  - No `tests/services/test_challenge_flow.py`.
  - `tests/services/test_workout_service.py` ends at line 417 and does not cover `/challenge` or callback flow.
  - No tests reference `process_callback_query`, `challenge_flow`, or `/telegram/webhook`.
- Risk: regressions in callback/session logic and TTL/rate-limit behavior will be hard to detect.

### [P2] Callback confirmation is not bound to the original chat context
- Flow state stores `chat_id` at creation time: `app/services/challenge_flow.py:44-49`.
- Callback handler ignores `flow.chat_id` and uses inbound callback `chat_id` directly: `app/services/workout_service.py:1574-1606`.
- Impact: same user can confirm from a different chat context than where the flow started; success/error messages can be sent to the wrong chat, and the saved `chat_id` is effectively unused.

### [P3] Cancel callback does not follow the expired/missing-session behavior from plan
- Confirm path handles missing/expired flow with explicit session-expired callback message: `app/services/workout_service.py:1585-1590`.
- Cancel path always responds as cancelled, even when no active flow exists: `app/services/workout_service.py:1623-1629`.
- Plan expected missing/expired state to return a session-expired message.
- Impact: inconsistent UX and harder debugging of stale inline buttons.

### [P3] Plan item missing: inline keyboard models were not added to Telegram models
- Plan requested `InlineKeyboardButton` and `InlineKeyboardMarkup` in `app/models.py`.
- `app/models.py` adds callback-query models but no inline keyboard models (`app/models.py:49-60`).
- Keyboard payload is currently untyped dict constant: `app/services/workout_service.py:1513-1520`.
- Impact: lower schema consistency and weaker type-level validation for keyboard payload shape.

### [P3] Style/maintainability drift in `workout_service.py`
- `app/services/workout_service.py` is now 1631 lines, with challenge flow, callbacks, reminders, registration, and workout logging in one module.
- Ruff reports an unused import: `calculate_status_and_deficit` at `app/services/workout_service.py:44`.
- Impact: increasing maintenance cost and review/debug complexity.

## Plan-to-Implementation Check
- `app/models.py` callback query support: **Implemented**.
- `app/models.py` inline keyboard models: **Missing**.
- `app/services/challenge_flow.py` state + TTL + rate limit: **Implemented** (no direct tests).
- `app/services/telegram_client.py` keyboard send + callback answer: **Implemented**.
- `app/routers/telegram.py` callback query routing: **Implemented** (no direct tests).
- `app/services/workout_service.py` `/challenge` command + prompt intercept + callback handling: **Implemented**.
- `src/api/services.py` public `validate_and_prepare_challenge()` orchestrator: **Implemented**.

## Notes on Data Alignment
- No obvious snake_case/camelCase mismatch found in callback payload usage (`callback_data`, `callback_query_id`).
- Telegram `"from"` field aliasing appears correctly modeled via `from_` + `Field(..., alias="from")`.
