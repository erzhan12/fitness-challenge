# Feature 0021 — Code Review

Feature: per-user `is_workout_motivation_active` toggle gating the LLM
motivational line appended to workout-log Telegram replies. Evening reminders
out of scope.

## External review trail

**Engines:** codex (`codex exec --sandbox read-only`) + cursor
(`agent -p --mode ask`), run in parallel.
**Rounds:** 1 (converged immediately).
**Change surface:** 10 files (6 source, 1 migration, 3 test).

### Round 1 verdict

Both engines independently returned **NO P1/P2 FINDINGS**. Cursor produced an
18-row verification log confirming every plan claim MATCH (model field,
migration dep/default, admin display/editable, API Out/Update models, service
mapping, router docstrings, `update_chat_id` capture, gate expression,
assembly append guard, reminder path left ungated, snake_case JSON, test
coverage, explicit non-truthy `update_chat_id` stub).

### Findings raised (4 × P3, none blocking)

| # | Finding | Verdict | Action |
|---|---|---|---|
| 1 | `is_workout_motivation_active` used `Field(True)` in `UserSettingsOut`/`SettingsOut` while sibling `is_reminder_active` uses `Field(...)` (required); OpenAPI marked it optional | ACCEPT | Fixed — changed both response models to `Field(...)`. All construction sites supply the value (services `SettingsOut(...)`, router `model_validate` on real model). |
| 2 | Enabled service test asserted marker presence but not the `<i>…</i>` wrap | ACCEPT | Fixed — assert `f"<i>{MOTIVATION_MARKER}</i>"` in sent text. |
| 3 | New test file duplicates `_base_patches` scaffold from `test_workout_empty_challenges.py` | ACCEPT (non-blocking gap) | Deferred — shared-fixture extraction is a broader refactor; both files intentionally self-contained for now. |
| 4 | Sibling `_base_patches` in `test_workout_empty_challenges.py` still uses a bare `AsyncMock` for `update_chat_id` (truthy attr keeps enabled path "by accident") | REJECT for this feature | Those tests don't assert on motivation and pass unchanged; the plan's caution applies to NEW gate tests, which use explicit stubs. Hardening the legacy helper is out of scope. |
| — | Gate comment slightly longer than nearby style (cursor) | REJECT | Comment is intentionally explanatory (documents the no-LLM/no-fallback behavior); no correctness impact. |

### Fixes applied

- `src/api/models.py` — `UserSettingsOut.is_workout_motivation_active` and
  `SettingsOut.is_workout_motivation_active` now `Field(...)` (required),
  matching `is_reminder_active`.
- `tests/services/test_workout_motivation_setting.py` — enabled case asserts
  the `<i>…</i>` wrapping explicitly.

### Verification (worktree `feature/0021-workout-motivation`)

- `uv run pytest tests/ -q` → **406 passed**, 0 failed.
- `uv run ruff check` on changed files → only pre-existing `E402`
  (`setup_django()` import-ordering convention shared by all service/api test
  modules); no new lint categories introduced.

**Result: SUCCESS** — zero valid P1/P2, tests + lint green.
