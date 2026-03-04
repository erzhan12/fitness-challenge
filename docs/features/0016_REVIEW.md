# Feature 0016: LLM-Powered Challenge Creation — Re-review

**Review Date:** 2026-03-04  
**Reviewer:** Codex  
**Status:** Approved

## Findings (ordered by severity)

No open findings.

## Previously Reported Issues Re-check

- LLM outage mapping now correctly returns `503`:
  - `app/services/openai_service.py` raises `LLMUnavailableError`.
  - `src/api/routers/challenges.py` maps `LLMUnavailableError` to HTTP 503.
- Parsed payload validation is now enforced:
  - `src/api/services.py` validates `raw_parsed` via `ChallengePromptParsed`.
- Plan/model schema alignment is fixed:
  - `ChallengePromptParsed` now includes `is_valid` and `error_reason`.
- Test coverage gaps are addressed:
  - API tests now assert derived `daily_target` in create payload.
  - Alias fallback path is covered.
  - 503 behavior is covered.
- Lint/style issues from previous review are resolved:
  - Unused imports removed; targeted Ruff run passes.

## Plan Compliance Check

- `POST /api/v1/challenges/create-from-prompt` endpoint exists with auth + request model.
- LLM parsing function added with JSON mode and deterministic temperature.
- Orchestration validates parsed payload, resolves exercise type, and computes targets as planned.
- Error mapping behavior aligns with plan (`404`, `400`, `503`).
- Unit/API tests exist for happy paths and major edge cases for this feature.

## Test Validation

- Command run: `uv run ruff check src/api/services.py src/api/models.py src/api/routers/challenges.py app/services/openai_service.py tests/services/test_openai_service.py tests/api/test_challenges.py`
- Result: `All checks passed!`
- Command run: `uv run pytest -q tests/services/test_openai_service.py tests/api/test_challenges.py`
- Result: `38 passed in 0.20s`
- Command run: `uv run pytest -q`
- Result: `261 passed in 0.95s`

## Residual Risks / Gaps

- `src/api/services.py` remains a large mixed-concern module (existing architectural debt, not introduced by this patch).
