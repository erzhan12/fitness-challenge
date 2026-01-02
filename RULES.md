# Development Rules and Guidelines

This file contains important patterns, conventions, and pitfalls to avoid when working on this codebase.

---

## REST API Convention

**CRITICAL RULE**: For any new business logic function that handles:
- Exercise operations (create, update, list, delete)
- Challenge operations
- Log operations
- Stats computations
- User operations
- Workout parsing or processing

You MUST also create a corresponding REST API endpoint under `/api/v1/`.

### Required Steps for New Functions:

1. **Implement business logic** in `src/api/services.py`
   - Keep logic independent of HTTP/Telegram specifics
   - Return structured data (not HTML strings)
   - Reuse existing domain helpers from `app/services/workout_service.py` where applicable

2. **Create REST API endpoint** in the appropriate router:
   - `src/api/routers/exercises.py` - Exercise type management
   - `src/api/routers/challenges.py` - Challenge management
   - `src/api/routers/logs.py` - Exercise log operations
   - `src/api/routers/stats.py` - Statistics and progress
   - `src/api/routers/workouts.py` - Workout parsing and AI features

3. **Define Pydantic models** in `src/api/models.py`:
   - Request models (e.g., `ExerciseLogCreate`, `ChallengeUpdate`)
   - Response models (e.g., `ExerciseStatsOut`, `LogCreateResponse`)
   - Include field descriptions and examples for OpenAPI docs

4. **Add unit tests** in `tests/api/`:
   - Happy path scenarios
   - Error cases (404, 400, 422)
   - Authentication/authorization (401, 403)
   - Edge cases (empty results, invalid input)
   - Use mocking to avoid hitting real Supabase

5. **Security and authentication**:
   - All POST/PATCH/DELETE endpoints MUST require API key authentication
   - GET endpoints are public (read-only access)
   - Use `require_api_key` dependency from `src/api/security.py`

6. **OpenAPI documentation**:
   - Add `summary` and `description` to endpoints
   - Use appropriate `tags` (Exercises, Challenges, Logs, Stats, Workouts)
   - Define `response_model` explicitly
   - Document error responses in `responses` parameter
   - Add docstrings explaining parameters and behavior

### Example Implementation:

```python
# In src/api/routers/challenges.py

@router.patch(
    "/challenges/{challenge_id}/archive",
    response_model=ChallengeOut,
    summary="Archive a challenge",
    description="Marks a challenge as inactive/archived",
    tags=["Challenges"],
    responses={
        200: {"description": "Challenge archived successfully"},
        401: {"description": "Missing or invalid API key"},
        404: {"description": "Challenge not found"},
    }
)
async def archive_challenge(
    challenge_id: int,
    api_key: str = Depends(require_api_key)
):
    """
    Archive a challenge by setting is_active to False.

    - **challenge_id**: ID of the challenge to archive

    Returns the updated challenge details.
    """
    return await services.archive_challenge(challenge_id)
```

### Exception: Internal Helpers

You do NOT need to create API endpoints for:
- Pure utility functions (date parsing, formatting, etc.)
- Internal Telegram-specific handlers
- Database migration helpers
- Cron job internals (unless exposing as admin endpoint)

---

## Project Structure

### Current Architecture

```
src/api/              # REST API layer (HTTP/JSON-first)
├── models.py         # Pydantic request/response models
├── security.py       # Authentication dependencies
├── services.py       # Business logic (database operations)
└── routers/          # HTTP endpoint definitions
    ├── exercises.py
    ├── challenges.py
    ├── logs.py
    ├── stats.py
    └── workouts.py

app/                  # Telegram bot layer
├── main.py           # FastAPI app + router registration
├── models.py         # Telegram-specific models
└── routers/          # Telegram webhook and admin endpoints
    ├── telegram.py   # Webhook handler
    └── admin.py      # Admin/cron jobs
└── services/         # Telegram-focused services
    ├── workout_service.py    # Core domain logic
    ├── openai_service.py     # LLM parsing
    └── telegram_client.py    # Telegram API client

tests/api/            # API endpoint tests
├── conftest.py       # Shared fixtures
├── test_exercises.py
├── test_challenges.py
├── test_logs.py
├── test_stats.py
├── test_security.py
└── test_workouts.py
```

### Separation of Concerns

- **`src/api/`** - Returns structured JSON data for REST API
- **`app/services/`** - Can return HTML-formatted strings for Telegram
- **Shared logic** - Extract pure computations into reusable helpers

**IMPORTANT**: Avoid duplicating business logic between Telegram and API layers. Extract shared computations into helper functions that both can use.

---

## Testing Standards

### Test File Organization

- One test file per router: `test_exercises.py`, `test_challenges.py`, etc.
- Group tests by endpoint using test classes
- Use descriptive test names: `test_create_log_unauthorized`, `test_list_challenges_filter_active`

### Required Test Coverage

For each new endpoint, test:
- ✅ Success cases (200, 201)
- ✅ Not found (404)
- ✅ Bad request (400)
- ✅ Validation errors (422)
- ✅ Unauthorized (401)
- ✅ Forbidden (403)
- ✅ Empty results
- ✅ Pagination (where applicable)
- ✅ Filters and query parameters

### Mock Pattern

Use the helper from `tests/api/conftest.py`:

```python
from unittest.mock import patch, Mock
from tests.api.conftest import create_mock_query

def test_create_exercise_success(client, auth_headers, mock_exercise_type_data):
    """Test successful creation of exercise type."""
    with patch("src.api.services.get_supabase") as mock_get_sb:
        mock_sb = Mock()
        mock_sb.table.return_value.insert.return_value = create_mock_query(
            [mock_exercise_type_data]
        )
        mock_get_sb.return_value = mock_sb

        response = client.post(
            "/api/v1/exercises",
            json={"name": "pushups", "display_name": "Push-ups", "emoji": "💪"},
            headers=auth_headers
        )

        assert response.status_code == 201
        assert response.json()["name"] == "pushups"
```

### Running Tests

```bash
# Run all API tests
pytest tests/api/

# Run specific test file
pytest tests/api/test_exercises.py

# Run with coverage
pytest tests/api/ --cov=src.api --cov-report=html
```

---

## Authentication & Security

### API Key Authentication

- Configured via `ADMIN_API_KEY` environment variable
- Implemented in `src/api/security.py` via `require_api_key` dependency
- Supports both `Bearer <token>` and raw token formats

### Endpoint Security Rules

| HTTP Method | Authentication Required | Notes |
|-------------|------------------------|-------|
| GET | ❌ No (public) | Read-only operations |
| POST | ✅ Yes | Creating resources |
| PATCH | ✅ Yes | Updating resources |
| PUT | ✅ Yes | Replacing resources |
| DELETE | ✅ Yes | Deleting resources |

**Example:**
```python
from src.api.security import require_api_key

@router.post("/logs")
async def create_log(
    log: ExerciseLogCreate,
    api_key: str = Depends(require_api_key)  # ✅ Requires auth
):
    ...

@router.get("/logs")
async def list_logs():  # ❌ No auth required (public read)
    ...
```

---

## Database Patterns (Supabase)

### Using the Supabase Client

Always use the dependency injection pattern:

```python
from app.dependencies import get_supabase

# In services
def get_exercise_types():
    sb = get_supabase()
    result = sb.table("exercise_types").select("*").eq("is_active", True).execute()
    return result.data
```

### Common Patterns

**Select with filters:**
```python
sb.table("exercise_logs")\
  .select("*, exercise_types(*)")\
  .eq("exercise_type_id", exercise_id)\
  .gte("date", start_date)\
  .lte("date", end_date)\
  .order("date", desc=True)\
  .execute()
```

**Insert:**
```python
sb.table("exercise_logs").insert({
    "exercise_type_id": 1,
    "count": 25,
    "date": "2024-01-15"
}).execute()
```

**Update:**
```python
sb.table("exercise_types")\
  .update({"is_active": False})\
  .eq("id", exercise_id)\
  .execute()
```

**Delete:**
```python
sb.table("exercise_logs")\
  .delete()\
  .eq("id", log_id)\
  .execute()
```

---

## Documentation

### Auto-Generated API Docs

FastAPI automatically generates interactive documentation:
- **`/docs`** - Swagger UI (for manual testing)
- **`/openapi.json`** - OpenAPI 3.0 specification

### Adding Good Documentation

```python
@router.get(
    "/exercises/{exercise_type_id}",
    response_model=ExerciseTypeOut,
    summary="Get exercise type by ID",
    description="Retrieves detailed information about a specific exercise type",
    tags=["Exercises"],
    responses={
        200: {"description": "Exercise type found"},
        404: {"description": "Exercise type not found"},
    }
)
async def get_exercise(exercise_type_id: int):
    """
    Get a single exercise type by its ID.

    - **exercise_type_id**: Unique identifier for the exercise type

    Returns the exercise type details including name, emoji, unit, and aliases.
    """
    ...
```

---

## Git Workflow

### Commit Messages

Use clear, descriptive commit messages:
- `feat: add archive challenge endpoint`
- `fix: handle missing exercise type in log creation`
- `test: add pagination tests for logs endpoint`
- `docs: update API documentation for stats endpoint`
- `refactor: extract stats computation to shared helper`

### Before Committing

1. Run tests: `pytest tests/api/`
2. Verify API docs: Check `/docs` endpoint
3. Ensure no linting errors
4. Test manually in development

---

## Common Pitfalls to Avoid

### 1. Don't Duplicate Business Logic

❌ **Wrong:**
```python
# In telegram handler
def handle_log(count):
    sb = get_supabase()
    sb.table("exercise_logs").insert(...)
    # Calculate stats here

# In API endpoint
def create_log(log):
    sb = get_supabase()
    sb.table("exercise_logs").insert(...)
    # Calculate stats here again (duplicated!)
```

✅ **Correct:**
```python
# In src/api/services.py
def create_exercise_log(exercise_type_id, count, date):
    """Shared function used by both Telegram and API."""
    sb = get_supabase()
    # Insert log and calculate stats
    return log, stats

# In telegram handler
def handle_log(count):
    log, stats = create_exercise_log(...)
    send_telegram_message(format_as_html(stats))

# In API endpoint
def create_log(log):
    log, stats = create_exercise_log(...)
    return {"log": log, "stats": stats}
```

### 2. Don't Return HTML from API Endpoints

API endpoints should return JSON, not HTML strings.

❌ **Wrong:**
```python
@router.get("/stats")
async def get_stats():
    return {"message": "<b>Total: 100</b>"}  # HTML in JSON
```

✅ **Correct:**
```python
@router.get("/stats")
async def get_stats():
    return {"total": 100, "unit": "reps"}  # Structured data
```

### 3. Always Mock Supabase in Tests

Never hit the real database in unit tests.

❌ **Wrong:**
```python
def test_create_log(client):
    # This will try to connect to real Supabase!
    response = client.post("/api/v1/logs", json={...})
```

✅ **Correct:**
```python
def test_create_log(client):
    with patch("src.api.services.get_supabase") as mock_get_sb:
        mock_sb = Mock()
        mock_sb.table.return_value.insert.return_value = create_mock_query([...])
        mock_get_sb.return_value = mock_sb

        response = client.post("/api/v1/logs", json={...})
```

### 4. Don't Forget Authentication on Write Endpoints

All POST/PATCH/DELETE endpoints must require authentication.

❌ **Wrong:**
```python
@router.post("/challenges")
async def create_challenge(challenge: ChallengeCreate):
    # Missing authentication!
```

✅ **Correct:**
```python
@router.post("/challenges")
async def create_challenge(
    challenge: ChallengeCreate,
    api_key: str = Depends(require_api_key)  # ✅
):
```

---

## Key Files Reference

- **`app/main.py`** - FastAPI app initialization, router registration
- **`src/api/models.py`** - API request/response Pydantic models
- **`src/api/services.py`** - Business logic functions
- **`src/api/security.py`** - Authentication dependencies
- **`src/api/routers/`** - REST API endpoint definitions
- **`app/services/workout_service.py`** - Core domain logic (stats, logs, challenges)
- **`app/dependencies.py`** - Supabase client injection
- **`tests/api/conftest.py`** - Test fixtures and helpers
- **`docs/features/0003_PLAN.md`** - REST API architecture plan

---

## Telegram Bot Patterns

### Typing Indicator for Long-Running Operations

When processing messages that involve LLM calls or heavy computation, show a "typing..." indicator to improve user experience.

**Pattern:**
```python
async def process_incoming_message(text: str, chat_id: int):
    # Send typing action immediately before any processing
    await send_chat_action(chat_id, "typing")

    # Start background loop to keep typing alive (refreshes every 4s)
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(chat_id, stop_typing))

    try:
        # Do your processing here (LLM calls, DB queries, etc.)
        result = await process_heavy_operation()

        # Send final response
        await send_telegram_message(chat_id, result)
    finally:
        # Always stop typing indicator
        stop_typing.set()
        await typing_task
```

**Key Points:**
- Send typing action **immediately** at the start (before any processing)
- Start background task to refresh typing every 4 seconds (Telegram's typing indicator expires after 5 seconds)
- Use `try-finally` to ensure typing indicator always stops
- Background task prevents typing from disappearing during long operations

**Files:**
- `app/services/telegram_client.py` - `send_chat_action()` function
- `app/services/workout_service.py` - `keep_typing()` helper and usage example in `process_incoming_message()`

---

## Exercise Count Validation

All exercise count inputs (via Telegram or API) must be positive integers greater than 0. The system rejects:
- Zero values (0, 0.0, 0.00)
- Decimal values (0.1, 0.5, 1.5, .25)
- Negative values (handled by LLM post-processing)

**Implementation:**
1. **Deterministic Parser** (`app/services/deterministic_parser.py`):
   - `_is_valid_count()` - Helper function validates count > 0
   - Early rejection of decimal numbers via regex: `r'(\b\d*\.\d+\b|^\.\d+)'`
   - Validates all parsed counts before creating entries
   - Returns error: "Count must be greater than 0 and should be an integer."

2. **LLM Parser** (`app/services/openai_service.py`):
   - System prompt instructs LLM to validate counts
   - Post-processing validation catches any LLM mistakes
   - Same error message for consistency

**Error Message:**
```
"Count must be greater than 0 and should be an integer."
```

**Files:**
- `app/services/deterministic_parser.py` - Validation logic for deterministic parsing
- `app/services/openai_service.py` - LLM prompt and post-processing validation
- `tests/services/test_count_validation.py` - Comprehensive test suite (17 tests)

**Pitfall to Avoid:**
Don't accept decimal or zero counts anywhere in the codebase. Always use the validation helpers to ensure counts are valid positive integers.

---

## Default Challenge Selection

When a user sends a message with only a number (e.g., "25"), the system attempts to infer the exercise type from active challenges.

**Selection Logic:**
1. **Single Active Challenge:** Use that challenge's exercise type.
2. **Multiple Active Challenges:**
   - Check for challenges with `is_default=True`.
   - If found, use the one with the **lowest `challenge_id`** (deterministic tiebreaker).
   - If none found, fallback to "pushups".
3. **No Active Challenges:** Fallback to "pushups".

**Implementation:**
- Logic encapsulated in `determine_default_exercise` in `app/services/workout_service.py`.
- `is_default` field in `exercise_challenges` table.

---

## Multi-Number Challenge Selection

When a user sends a numbers-only message with multiple numbers (e.g., "50 30"), the system deterministically maps each number to an active challenge.

**Mapping Logic:**
1. **Fetch Active Challenges:** All active challenges valid for today.
2. **Order Challenges:**
   - First: The "default" challenge (marked `is_default=True`; if multiple, lowest ID wins).
   - Then: Remaining challenges sorted by increasing `id`.
3. **Map Numbers:**
   - 1st number -> 1st ordered challenge
   - 2nd number -> 2nd ordered challenge
   - ...and so on.
   - Extra numbers are ignored.

**Implementation:**
- `get_numbers_from_message` (`app/services/deterministic_parser.py`): Detects valid multi-number input.
- `get_ordered_challenges` (`src/api/services.py`): Sorts challenges according to the rule.
- Applied in both `process_incoming_message` (Telegram) and `/api/v1/workouts/parse` (REST).

**Pitfall to Avoid:**
Do not rely on `challenge_map` (keyed by exercise type) when processing these entries, as multiple challenges might target the same exercise type. Use explicit index-based mapping where available.

---

**Last Updated:** Added multi-number challenge mapping rules (2026-01-03)
