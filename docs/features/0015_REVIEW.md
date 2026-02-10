# Feature 0015: Rich Habit Reward Telegram Messages — Code Review

**Review Date:** 2026-02-10  
**Reviewer:** Codex  
**Status:** Changes Requested

## Findings (ordered by severity)

### 1) [P2] Inconsistent API state can produce an incorrect user message
- **File:** `/Users/erzhan/DATA/PROJ/fitness-challenge/app/services/workout_service.py:219`
- Formatter logic uses `if response.got_reward and response.reward:` and otherwise falls back to `❌ No reward this time - keep going!`.
- If the API returns `got_reward=true` but `reward=null` (schema drift / transient backend issue), the user will incorrectly receive a “No reward” message.
- The model currently allows this state (`reward` is optional), so this path is reachable.

### 2) [P3] Client response-shape changes are not directly tested
- **Files:** `/Users/erzhan/DATA/PROJ/fitness-challenge/app/services/habit_reward_client.py:28`, `/Users/erzhan/DATA/PROJ/fitness-challenge/tests/services/test_habit_reward_client.py:66`
- Feature 0015 introduces a typed nested model (`RewardProgressResponse`) and a new `user_timezone` field on `HabitCompletionResponse`, but `TestSendHabitCompletion` still validates only a success response with `cumulative_progress=None`.
- There is no test proving `send_habit_completion()` correctly parses a real nested `cumulative_progress` object and preserves/defaults `user_timezone`.
- There is also no negative test for malformed `cumulative_progress` payloads to confirm failure is handled intentionally.

### 3) [P3] Test module has grown into a mixed-concern monolith
- **File:** `/Users/erzhan/DATA/PROJ/fitness-challenge/tests/services/test_habit_reward_client.py:1`
- The file is now 1089 lines and combines API-client unit tests, workout-service integration behavior, formatter tests, and repository method tests.
- This increases maintenance overhead and slows review/debug cycles. Splitting by concern (client vs formatter/service vs repository) would reduce coupling and keep future feature reviews tighter.

## Plan Compliance Check

- `RewardProgressResponse` model added in `/Users/erzhan/DATA/PROJ/fitness-challenge/app/services/habit_reward_client.py`.
- `HabitCompletionResponse.cumulative_progress` now uses typed model and `user_timezone` is added.
- `_format_habit_reward_message()` now adds reward progress bar and achieved message.
- Formatter behavior from the plan is implemented and covered by dedicated tests (`partial`, `full`, `exceeded`, `zero`, and `no-progress` cases).

## Test Validation

- Command run: `uv run pytest -q tests/services/test_habit_reward_client.py`
- Result: `34 passed in 0.48s`
- Command run: `uv run pytest -q`
- Result: `238 passed in 1.10s`
