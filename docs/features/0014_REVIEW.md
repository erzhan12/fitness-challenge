# Code Review: Feature 0014 - Re-review

## Findings
No open findings.

## Re-review Scope
- Verified the previous issues are fixed:
  - `PATCH /challenges/{id}` rejects explicit `{"daily_target": null}`.
  - OpenAPI examples now use computed `target_total` values (`33 * 31 = 1023`).
  - Cleanup items in `workout_service` and `utils` remain consistent.
- Re-checked implementation against the feature plan:
  - DB model drops `target_total` and requires `daily_target`.
  - Migration backfills null `daily_target`, then enforces non-null, then removes `target_total`.
  - Request models no longer accept `target_total`.
  - Response models still expose computed `target_total`.
  - Service and utility layers compute targets from `daily_target * total_days`.
  - Telegram/service paths use updated signatures and computed values.
  - Tests were updated for API and service behavior.

## Test Validation
- Command run: `uv run pytest -q`
- Result: `232 passed in 1.01s`

## Residual Risks / Gaps
- Migration fallback behavior (`daily_target = 1` for malformed legacy rows) is unchanged and appears intentional; if bad historical data exists, this is still a data-normalization tradeoff.
- Migration behavior is not covered by automated migration integration tests in this suite.
