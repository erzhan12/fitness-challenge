# 0018 Review - Challenge Exception Days

## Scope and Method

- Reviewed implementation against [0018_PLAN.md](./0018_PLAN.md) and the checklist in [commands/code_review.md](../../commands/code_review.md).
- Inspected the exception-day changes in:
  - `src/core/models.py`, `src/core/repositories.py`, `src/core/utils.py`, `src/core/validators.py`, `src/core/admin.py`
  - `src/api/models.py`, `src/api/services.py`, `src/api/routers/challenges.py`, `src/api/routers/exception_days.py`
  - `app/main.py`, `app/services/openai_service.py`, `app/services/workout_service.py`, `app/services/challenge_flow.py`
  - new/updated tests under `tests/api/`, `tests/core/`, and `tests/services/`
- Executed:
  - `uv run pytest -q tests/api/test_challenges.py tests/api/test_exception_days.py tests/api/test_services_exception_stats.py tests/services/test_exception_command.py tests/services/test_reminders_rest_days.py tests/core/test_utils.py` -> 137 passed
  - `uv run pytest -q` -> 386 passed
  - `uv run ruff check app/main.py app/services/challenge_flow.py app/services/openai_service.py app/services/workout_service.py src/api/models.py src/api/services.py src/core/admin.py src/core/models.py src/core/repositories.py src/core/utils.py src/core/validators.py tests/api/conftest.py tests/api/test_challenges.py tests/core/test_utils.py tests/api/test_exception_days.py tests/api/test_services_exception_stats.py tests/services/conftest.py tests/services/test_exception_command.py tests/services/test_reminders_rest_days.py` -> 1 finding, an unused `datetime` import in `src/core/repositories.py` that was already present in `HEAD`
  - `uv run ruff check` -> fails on existing repo-wide lint debt, mostly E402 imports after `setup_django()` in tests/scripts plus unused imports

## Findings (ordered by severity)

No open feature findings.

## Resolved Findings

- Stats response schema still documents the old calendar-day target math: fixed by updating `ExerciseStatsOut.day_number`, `total_days`, and `target_total` descriptions to say stats use scheduled/effective days and that challenge `total_days` remains calendar-based.
- Regression coverage is too loose/missing: fixed by tightening the effective-day target-cap regression fixture (`100_000 / 30` calendar under cap, `100_000 / 5` effective over cap) and adding direct rest-day tests for `_check_all_challenges_complete()`, `compute_evening_reminder()`, and `check_daily_reminders(hour=None)` in `tests/services/test_reminders_rest_days.py`.
- Target-only LLM challenges can bypass the daily target cap after exceptions: fixed by moving the `MAX_DAILY_TARGET` check after effective-day target derivation in `_build_challenge_data()`.
- `/exception add` relative dates use the host date: fixed by passing `today=datetime.now(TZ).date()` from `_handle_exception_prompt()` into `parse_exception_prompt()`.
- Challenge creation is not atomic across parent row and one-off exception rows: fixed by adding `ExerciseChallengeRepository.create_with_exception_dates()` with `transaction.atomic()` and using it from `create_challenge()`.
- Updating a challenge window can leave stored exception dates outside the new window: fixed by trimming existing one-off rows when the window changes without an explicit `exception_dates` replacement.
- LLM challenge creation silently drops out-of-window exception dates: fixed by rejecting out-of-window parsed exception dates instead of filtering them out.

## Plan-to-Implementation Check

- Data layer: model field, child model, migration, admin registration, and validators are implemented.
- Repository: one-off exception repository and singleton are implemented, with extra `replace_dates()` and atomic `create_with_exception_dates()` helpers.
- Pydantic/API models: challenge, stats, exception-day, and prompt models are implemented with exception-aware field descriptions.
- Stats math: effective total/day number, rest-day flag, banked cumulative reps, and bulk exception prefetch are implemented.
- Logging: log snapshots use the computed effective `day_number` and status.
- REST endpoints: `/api/v1/challenges/{challenge_id}/exception-days` is implemented and mounted. Challenge create/update list/detail hydration is implemented.
- Telegram UX: challenge preview includes rest days/effective totals; `/exception list/add/remove/clear` and confirm/cancel flow are implemented.
- LLM parser: challenge parser includes exception fields; `/exception add` parser exists, but returns a raw dict rather than the `ExceptionPromptParsed` model described in the plan.
- Maintainability: `app/services/workout_service.py` is now 2188 lines and owns workout logging, challenge creation, exception management, reminders, and Habit Reward coordination. This is not a functional blocker, but the new `/exception` command would be a good candidate for extraction after the correctness fixes.

## Notes on Data Alignment

- API JSON names use snake_case consistently (`exception_weekdays`, `exception_dates`, `effective_total_days`, `is_today_exception`).
- No nested `{data: ...}` response-shape mismatch was found in the new REST endpoints.
- The prior `/exception add` relative-date alignment issue is fixed by passing an app-local `today` into the parser.

## Residual Notes

- `uv run ruff check` still fails on pre-existing repo-wide lint debt. The only targeted lint finding inside the feature-touched file set is the pre-existing unused `datetime` import in `src/core/repositories.py`.
- `app/services/workout_service.py` remains large at over 2000 lines and now owns workout logging, challenge creation, exception management, reminders, and Habit Reward coordination. This is not a release blocker for feature 0018, but the `/exception` command remains a good candidate for extraction.
