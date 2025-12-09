# Feature Review: REST API Endpoints & OpenAPI Docs

Date: 2025-12-02  
Reviewer: GPT-5.1 Codex

## Scope
- `src/api` routers, models, services, and security layer
- `app/main.py` wiring plus existing Telegram workflow in `app/services/workout_service.py`
- Relevant tests under `tests/api`

## Findings

1. ❌ **`target_date` filtering is ignored in stats calculations**
   - The new stats helper accepts a `target_date`, but cumulative totals are computed over *all* logs for the exercise/challenge with no `date <= target_date` filter. Only the `today_total` query applies the date constraint.
   - Evidence:

```349:378:src/api/services.py
# Query cumulative total
query = sb.table("exercise_logs").select("count").eq("exercise_type_id", exercise_type_id)
...
logs_res = query.execute()
current_total = sum(r["count"] for r in logs_res.data)
new_cumulative = current_total + added_count
...
today_logs = (
    sb.table("exercise_logs")
    .select("count")
    .eq("exercise_type_id", exercise_type_id)
    .eq("date", today_local.isoformat())
    .execute()
)
```

   - Impact: `GET /api/v1/stats/exercises?target_date=2024-01-10` (and similar endpoints) will report cumulative totals, status, and catch-up values that include logs created *after* the requested date, defeating the purpose of the parameter.
   - Recommendation: gate the cumulative query with `.lte("date", today_local.isoformat())` (or equivalent) whenever `target_date` is supplied, and ensure the “day number” is clamped to the challenge window so historical snapshots are accurate.

2. ⚠️ **Business logic is still duplicated between Telegram and REST layers (plan gap)**
   - The feature plan explicitly required extracting the stats/log insertion/deletion logic from `get_exercise_stats_and_message` so both the Telegram bot and REST API share the same helper.

```119:142:docs/features/0003_PLAN.md
- **Exercise stats computation**
  - Extract the numerical/statistical logic currently embedded in `get_exercise_stats_and_message` into a new helper ...
  - Update `get_exercise_stats_and_message` to call this helper, then build the HTML message from the returned stats ...
```

   - The Telegram service still contains a full copy of the stats logic instead of calling `src.api.services.compute_exercise_stats`, so any bug fixes must be made twice and the two surfaces can drift.

```122:205:app/services/workout_service.py
def get_exercise_stats_and_message(...):
    ...
    logs_res = query.execute()
    current_total = sum(r["count"] for r in logs_res.data)
    new_cumulative = current_total + added_count
    ...
    today_logs = (
        sb.table("exercise_logs")
        .select("count")
        .eq("exercise_type_id", etype.id)
        .eq("date", today_local.isoformat())
        .execute()
    )
    ...
    return msg_part, stats
```

   - Impact: We now have two independent implementations of the same math and persistence rules, which undermines the goal of the REST layer and raises the risk of inconsistent behaviour between Telegram and API clients.
   - Recommendation: Refactor the Telegram service to call the shared helper(s) and thin orchestration functions in `src/api.services`, so there is a single source of truth for stats, log insertion, and deletion.

3. ⚠️ **`POST /api/v1/workouts/parse` breaks when there are no active challenges**
   - The parser fetches exercise definitions via `list_exercise_types(..., challenge_only=True)` with no fallback, so if the user temporarily has zero active challenges the list is empty and the prompt forbids every exercise.

```43:75:src/api/services.py
if challenge_only:
    challenges_res = (
        sb.table("exercise_challenges")
        .select("exercise_type_id")
        .eq("is_active", True)
        .execute()
    )
    active_type_ids = {c["exercise_type_id"] for c in challenges_res.data}
    exercise_types = [et for et in exercise_types if et.id in active_type_ids]
```

```68:85:src/api/routers/workouts.py
api_exercise_types = list_exercise_types(is_active=True, challenge_only=True)
exercise_types = [
    ExerciseType(
        id=et.id,
        name=et.name,
        ...
    )
    for et in api_exercise_types
]
result = parse_workout_message(data.text, exercise_types)
```

   - By contrast, the Telegram flow explicitly falls back to all active exercise types when `challenge_type_ids` is empty, so the bot keeps working for new users.

```454:499:app/services/workout_service.py
if not challenge_type_ids:
    ...
    exercise_types = await get_exercise_types()
    challenge_map = {}
else:
    ...
parsed_result = parse_workout_message(text, exercise_types)
```

   - Impact: The new REST endpoint refuses to parse any workout text unless at least one challenge is active, which makes it unusable during onboarding or between challenges.
   - Recommendation: Mirror the Telegram fallback—if `challenge_only` filtering would yield zero exercises, fall back to the full active exercise list (or expose a `challenge_only` flag on the endpoint so callers can choose).

## Overall assessment
- Not ready to release: the stats endpoints currently return incorrect historic data, and the parser endpoint silently stops working whenever the user has no active challenges. Addressing the findings above will bring the implementation in line with the feature plan and ensure consistent behaviour across clients.


