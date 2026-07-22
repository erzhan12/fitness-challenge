# Feature 0019 — Code Review

Feature: fix Habit Reward and the Telegram `✅ Day Complete!` banner firing on days where every active challenge is on an exception/rest day (GitHub issue #29).

Plan: `docs/features/0019_PLAN.md`
Branch: `feature/0019-habit-reward-rest-days`

## External review trail

**Engines:** OpenAI codex (`codex exec --sandbox read-only`) and Cursor agent (`agent -p --mode ask`), run independently against the same prompt built from `commands/code_review.md`.

**Rounds:** 1

**Findings:** raised 3, accepted 1 (fixed 1), rejected 0, P3 recorded-not-fixed 2. No P1 or P2 findings from either engine.

### codex

`NO P1/P2 FINDINGS`, no P3 findings. Independently confirmed the data-alignment question (review point 3): `exception_weekdays` is present on both the Telegram `list_current_active_challenges` → `_model_to_dict` path and the `notify_habit_reward_if_complete` path, explicit exception dates stay keyed by integer challenge id, and no `{data: {...}}` nesting is involved. Could not run pytest (read-only sandbox has no writable temp dir for pytest capture) — covered by the orchestrator's own run below.

### cursor

`NO P1/P2 FINDINGS` plus a 20-row verification log (19 MATCH, 1 deliberate MISMATCH). Confirmed line by line: early `return False` on empty input, batch fetches retained, `scheduled_seen` set only after the rest-day `continue`, `if is_today_exception: continue` preserved, `return scheduled_seen` replacing the unconditional `return True`, no `day_number == 0` guard added, all four tests matching their planned shapes, and both RULES.md notes.

Three P3s:

1. **`.gitignore:45-46` — `.worktrees/` ignore is outside Feature 0019.** ACCEPTED as a commit-scoping note, not a code fix. The identical change also sits uncommitted in the main worktree. Decide one home for it before committing; do not land it twice.
2. **`tests/services/test_reminders_rest_days.py:113-118` — negative-control docstring overclaims.** ACCEPTED and FIXED. The control (no rest day, cumulative `{1: 0}`) returns `False` just like the all-rest test, so it does not by itself isolate the rest-day branch. What actually discriminates is the banked `{1: 1000}` in `test_returns_false_when_all_challenges_are_rest_days`: that value clears `expected`, so only `scheduled_seen` staying `False` can produce `False` there. Docstring rewritten to say what the control really pins (the ordinary behind-schedule path) and to name the real discriminator.
3. **`docs/features/0019_PLAN.md` untracked.** ACCEPTED as a commit-scoping note. Include the plan (and this review) in the feature commit if the feature trail should be preserved.

**Rejected findings:** none. Both engines stayed within their evidence this round.

## Verification

- `uv run pytest tests/ -q` → **391 passed**, 1 pre-existing unrelated `slowapi` DeprecationWarning.
- `uv run ruff check app/services/workout_service.py tests/services/test_reminders_rest_days.py` → **All checks passed**.
- `uv run ruff check .` → 24 errors, **identical to the pre-existing baseline on `main`** (E402/F401 in files this diff does not touch). `make lint` is red on `main` too; this change introduces no new lint issues. That debt is separate cleanup.

## Orchestrator checks (beyond the engines)

- Traced both call sites of `_check_all_challenges_complete`. `process_incoming_message` (`app/services/workout_service.py:1328`) does not call `challenge_repo.get_current_active` directly — it goes through `list_current_active_challenges` (`src/api/services.py:264-274`), which delegates to the same repo method. `ChallengeRepository.get_current_active` (`src/core/repositories.py:442-446`) filters `start_date__lte=target_date, end_date__gte=target_date`, so `start_date <= today <= end_date` always holds and a non-exception challenge always has `day_number >= 1`. The plan's "do not add a `day_number == 0` guard" decision holds on the indirect path too.
- Same `today_local` feeds the challenge fetch (`:1129`) and the completion check (`:1328`) — no date skew between them.
- `_model_to_dict` renders dates as ISO strings on the Telegram path while the `notify_habit_reward_if_complete` path passes real `date` objects; `ensure_date()` absorbs both shapes.
- Gating chain covered end to end: the new helper test (all-rest → `False`) plus the existing `tests/services/test_habit_reward_client.py:566-582` ("when not all challenges complete, returns True without sending", asserting no claim and no API call).

## Result

Zero valid P1/P2 findings, tests and lint green. Ready to commit.
