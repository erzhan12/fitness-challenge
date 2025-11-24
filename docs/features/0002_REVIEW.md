# Feature Review: Show Catch-Up Reps When Behind

Date: 2025-11-24  
Reviewer: GPT-5.1 Codex

## Scope
- Verified implementation in `app/services/workout_service.py`.
- Reviewed helper script `test_catchup.py`.

## Findings

1. ✅ **Plan implemented as specified**
   - Catch-up logic calculates the expected total using the same formula as `calculate_status`, rounds the deficit up, and injects the new line into the Telegram message only when status is `behind`, matching the plan requirements.
   - Reference:

```
107:143:app/services/workout_service.py
# 4. Catch-up calculation
catch_up_reps = 0
if status == "behind":
    expected = daily_target * day_number if daily_target else (target_total / total_days) * day_number
    deficit = expected - new_cumulative
    if deficit > 0:
        catch_up_reps = math.ceil(deficit)
...
if catch_up_reps > 0:
    msg_part += f"Need {catch_up_reps} more to catch up!\n"
```

2. ⚠️ **Manual test script is not part of the automated suite**
   - `test_catchup.py` reproduces the calculations with print-based verification, but it is not wired into `pytest` or any CI workflow, so regressions in catch-up logic would go unnoticed.
   - Recommendation: move these scenarios into an automated test (e.g., `tests/services/test_workout_service.py`) with assertions so they run with the rest of the suite.

3. ⚠️ **Duplicated expected-progress calculation**
   - The catch-up block re-implements the same expected-value math that already lives in `calculate_status`. While correct today, it increases the risk of divergence if the status logic ever changes (e.g., different threshold rules).
   - Recommendation: extract a helper that returns both status and deficit, or reuse the existing calculation output to avoid duplication.

## Overall assessment
- No blocking issues detected for releasing the feature.
- Addressing the two ⚠️ items above would reduce future maintenance and testing risk.

