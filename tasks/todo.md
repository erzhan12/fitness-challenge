# TODO

Track current and upcoming work items here.

## In Progress

## Upcoming

- [ ] Add retry logic with exponential backoff for LLM calls (`app/services/openai_service.py`)
- [ ] Implement per-user rate limiting instead of per-IP for `/challenges/create-from-prompt`
- [ ] Add more parametrized tests for LLM challenge creation edge cases (boundary values, mixed valid/invalid fields)
- [ ] Consider Redis/DB-backed session storage for `challenge_flow.py` (needed if deploying with multiple workers)
- [ ] Extract challenge flow out of `workout_service.py` (1640+ lines, growing maintenance cost)

## Done

- [x] Feature 0017: Telegram `/challenge` command for LLM-based challenge creation
  - `/challenge` command with two-step flow (prompt → preview → confirm/cancel)
  - Inline keyboard buttons for confirmation
  - In-memory conversation state with 5-min TTL (`app/services/challenge_flow.py`)
  - Rate limiting (10 LLM calls/hour per user)
  - Callback query handling in webhook router
  - Extracted `validate_and_prepare_challenge()` from `create_challenge_from_prompt()`
  - 33 tests (state management, expiry, rate limits, all callback/error paths)
  - Security hardening: input validation, approval checks, no error detail leakage
  - Reusable httpx client for connection pooling
  - `@botname` suffix stripping for all Telegram commands

## Follow-ups

### Real-DB test for `ExerciseChallengeRepository.deactivate_expired` (from PR #32 review)
The current repo test (`tests/core/test_repositories.py`) verifies query construction via ORM spies (Option B): it asserts the `filter(is_active=True, end_date__lt=…)` predicate (strict `<` boundary), the `update(is_active=False, is_default=False)` dual-field clear, and `user_id` scoping. It does not exercise real SQL. A stronger belt-and-suspenders test would add `pytest-django` + a `@pytest.mark.django_db` sqlite-in-memory test that creates rows and asserts actual model-state transitions. Deferred because it introduces the first DB-backed test in the suite (new dev dep + pytest django settings + FK fixtures) — worth its own PR rather than destabilizing the 0020 change set.
