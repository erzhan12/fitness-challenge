# Feature 0020 — Code Review

Feature: stop fake `Day 1/30 · 990` progress cards when no in-window challenge exists; auto-clear `is_active` on expired challenges.

## External review trail

- **Engines:** codex (`gpt-5.5`, read-only) + cursor agent (`ask` mode)
- **Rounds:** 1
- **Verdict:** both engines returned **NO P1/P2 FINDINGS**. Only P3 (non-blocking) items.
- **Verification:** `uv run pytest tests/` → **403 passed**; `uv run ruff check` → zero new errors (1 pre-existing E402 = `setup_django()` import pattern, baseline debt).

### Findings raised (all P3 — none blocking)

| # | Finding | file:line | Verdict |
|---|---|---|---|
| 1 | Dead `if not challenges_data` branch, unreachable after new early exit | `src/api/routers/workouts.py:133`, `app/services/workout_service.py:1178` | **Accepted gap** — harmless defensive guard; removal means dedenting the ~30-line multi-number block, churn not justified on a green branch |
| 2 | Inconsistent extra-space indentation in numbers-only block | `src/api/routers/workouts.py:133-167` | **Pre-existing** — format baseline debt predating 0020; `ruff format` would balloon the diff with unrelated reflow. Not introduced by this feature |
| 3 | Missing Telegram `"50 30"` multi-number regression test | `tests/services/test_workout_empty_challenges.py` | **Accepted gap** — plan mentioned it; REST equivalent (`test_parse_workout_multi_number_mapping`) is covered. Recommend a follow-up Telegram test |
| 4 | `test_services.py` missing deactivate→empty integration + explicit count-0/idempotent scenarios | `tests/api/test_services.py` | **Accepted gap** — ordering, fail-open, target_date, and user_id forwarding are covered; the extra scenarios are incremental |
| 5 | Reminder fail-open test only exercises the disabled early-return path | `tests/services/test_reminders.py:55` | **Accepted gap** — disabled path already proves the sweep error is swallowed; an enabled-path assertion would strengthen it |
| 6 | In-window challenge whose exercise types are all `is_active=False` → parses with `[]` types | `src/api/routers/workouts.py`, `app/services/workout_service.py:1150` | **Rejected** — pre-existing contradictory data state (active challenge referencing a deactivated type); feature yields a clean "can't map / no valid types" result, not fake cards. Out of scope, no regression |
| 7 | No-active-challenges copy duplicated across 3 sites | `workouts.py:32`, `workout_service.py:1138`, test constants | **Accepted gap** — strings identical today; `app/services` vs `src/api` are deliberately separated layers, so a shared constant is optional. Drift risk only |

### Fixes applied

None. Both engines found zero P1/P2 issues; all P3 items are either pre-existing baseline debt, out-of-scope, or non-blocking incremental gaps.

### Recommended follow-ups (optional, non-blocking)

- Add a Telegram `"50 30"` multi-number `process_incoming_message` regression test (finding 3).
- If the team wants zero dead code on this path, remove the now-unreachable `if not challenges_data` guards in a dedicated cleanup commit (finding 1) — kept separate from the feature to isolate the reflow.
