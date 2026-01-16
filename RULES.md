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
- Applied consistently in both:
  - Telegram flow (`app/services/workout_service.py::process_incoming_message`)
  - REST API (`src/api/routers/workouts.py::parse_workout`)
- The REST API computes `default_exercise_name` using `determine_default_exercise()` and passes it to `parse_workout_message()` to ensure single-number inputs (e.g., "50") behave the same as Telegram.

**Pitfall to Avoid:**
Always pass `default_exercise_name` to `parse_workout_message()` - don't rely on the default "pushups" parameter. This ensures consistent behavior between Telegram and REST endpoints.

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

---

## Evening Reminders System

The application includes an automated evening reminder system that sends Telegram notifications at 9pm, 10pm, and 11pm for incomplete challenges.

### Components

**Data Layer:**
- `AppSettings` model (`src/core/models.py`) - Singleton table storing:
  - `is_reminder_active`: Boolean toggle for reminders
  - `telegram_chat_id`: Auto-captured from Telegram messages
  - `last_reminder_21_date`, `last_reminder_22_date`, `last_reminder_23_date`: Idempotency tracking
- `AppSettingsRepository` (`src/core/repositories.py`) - Async repository with methods:
  - `get_singleton()`, `set_is_reminder_active()`, `update_chat_id()`, `mark_hour_sent()`, `check_already_sent()`

**Reminder Logic:**
- `compute_evening_reminder()` (`app/services/workout_service.py`) - Determines incomplete challenges:
  - Challenges with `daily_target`: incomplete if `today_total < daily_target`
  - Challenges without `daily_target`: incomplete only if `today_total == 0`
  - Returns combined HTML message with motivational text
- `send_evening_reminder()` (`app/services/workout_service.py`) - Sends reminders:
  - Checks `is_reminder_active` flag
  - Implements idempotency to avoid duplicate sends
  - Sends one combined message per hour listing all incomplete challenges
- `generate_reminder_motivation()` (`app/services/openai_service.py`) - LLM-generated motivation:
  - Short (1-2 sentences), encouraging tone
  - Context-aware based on hour and remaining work
  - Fallback messages if LLM fails

**Scheduler:**
- `start_reminder_scheduler()` (`app/services/reminder_scheduler.py`) - Background task:
  - Calculates next reminder time (21:00/22:00/23:00 in `settings.TZ`)
  - Sleeps until target time
  - Triggers reminder via `send_evening_reminder()`
  - Handles errors gracefully with retry logic
- Started automatically in `app/main.py` startup event

**Settings API:**
- `GET /api/v1/settings` - Read current reminder settings (public)
- `PATCH /api/v1/settings` - Toggle `is_reminder_active` (requires API key)
- Models: `SettingsOut`, `SettingsUpdate` (`src/api/models.py`)
- Services: `get_settings()`, `update_settings()` (`src/api/services.py`)
- Router: `src/api/routers/settings.py`

**Auto-capture:**
- Telegram webhook (`app/routers/telegram.py`) automatically saves `chat_id` to settings when user sends messages

**Legacy Compatibility:**
- `check_daily_reminders()` updated to support optional `hour` parameter:
  - `hour=None`: Legacy simple reminder (sends per-challenge messages)
  - `hour=21/22/23`: New evening reminder with combined message

### Files
- **Models:** `src/core/models.py` (AppSettings)
- **Repositories:** `src/core/repositories.py` (AppSettingsRepository)
- **Reminder Logic:** `app/services/workout_service.py` (compute_evening_reminder, send_evening_reminder)
- **Scheduler:** `app/services/reminder_scheduler.py`
- **LLM Integration:** `app/services/openai_service.py` (generate_reminder_motivation)
- **API:** `src/api/routers/settings.py`, `src/api/services.py`, `src/api/models.py`
- **Telegram:** `app/routers/telegram.py` (auto-capture chat_id)
- **Tests:** `tests/api/test_settings.py`
- **Migration:** `src/core/migrations/0002_add_app_settings.py`

**Last Updated:** Added evening reminders system (2026-01-11)

---

## Django Admin Panel

The application includes a Django admin panel for managing database records through a web interface.

### Access

- **URL:** `http://localhost:8001/admin/` (when FastAPI server is running)
- **Authentication:** Requires Django superuser account (see setup below)

### Setup

1. **Create a superuser:**
```bash
python manage.py createsuperuser
```

2. **Start the FastAPI server:**
```bash
# The admin panel will be available at /admin/
uvicorn app.main:app --reload
```

### Admin Features

All models are registered with customized admin interfaces:

- **ExerciseType**: List display with name, display_name, emoji, unit, is_active. Filterable by is_active and unit. Searchable by name, display_name, and aliases.

- **ExerciseChallenge**: List display with challenge details, dates, targets, and flags. Filterable by is_active, is_default, and dates. Date hierarchy for easy navigation.

- **ExerciseLog**: List display with exercise, challenge, date, count, and stats. Filterable by exercise_type, status, and dates. Read-only fields for computed stats (cumulative_total, day_number, status).

- **UserStats**: List display with all-time totals, streaks, and best counts. Read-only fields as stats are computed automatically.

### Integration

The admin panel is integrated with FastAPI using WSGI middleware:
- Django admin is mounted at `/admin/` in `app/main.py`
- Uses `WSGIMiddleware` from `a2wsgi` (replaces deprecated `fastapi.middleware.wsgi`)
- Django settings configured in `src/core/settings.py`
- Admin registrations in `src/core/admin.py`
- URL routing in `src/core/urls.py`

### Files

- `src/core/admin.py` - Model admin registrations and customizations
- `src/core/urls.py` - Django URL configuration
- `src/core/settings.py` - Django settings (includes admin apps)
- `app/main.py` - FastAPI integration with WSGI middleware

**Last Updated:** Added Django admin panel setup (2026-01-09)

---

## Visual Completion Indicators

The application displays visual indicators for challenge and daily completion status.

### Progress Bar Display

**Progress Bar Format:**
- Filled blocks (█) for completed portions
- Light shade blocks (░) for remaining work
- Example: `[████░░░░░░] 40%`
- Bar always uses the same visual style regardless of completion status

**Per-Challenge Checkmark:**
- Each challenge shows a ✅ checkmark before its emoji when caught up
- Checkmark appears when `cumulative_total >= expected_progress` for that specific challenge
- Example: `✅ 🔥 Push-ups: +50` means this challenge has no deficit

### Completion Logic

**Individual Challenge Completion:**
- A challenge is "complete" when cumulative progress is on track or ahead of expected progress
- Expected progress = `(target_total / total_days) * day_number` (or `daily_target * day_number` if daily_target is set)
- Complete when `cumulative_total >= expected_progress`
- This means you need to catch up any deficit before a challenge is considered complete

**Daily Completion (All Challenges):**
- Shows `✅ Day Complete!` on first line when ALL active challenges are on track or ahead
- Does NOT show if any challenge is behind schedule
- Each challenge must have caught up to expected cumulative progress

### Implementation Details

**Files Modified:**
- `app/services/workout_service.py`:
  - `_is_daily_complete()` - Check if cumulative progress is on track (compares cumulative_total vs expected_progress)
  - `_check_all_challenges_complete()` - Check if all challenges are on track with cumulative progress
  - Updated `get_exercise_stats_and_message()` - Generate simple progress bar using █ and ░ characters

- `src/api/services.py`:
  - `compute_exercise_stats()` - Compute `is_daily_complete` flag based on cumulative progress vs expected

- `src/api/models.py`:
  - `ExerciseStatsOut` - Added `is_daily_complete: bool` field (True when cumulative_total >= expected_progress)

### Example Telegram Messages

**When Both Challenges Behind (No Checkmarks, No "Day Complete"):**
```
💪 Push-ups: +111
Day 10/30 • Today: 111 • Total: 232/1500
[█░░░░░░░░░] 15%
Need 268 more to catch up!

🧑‍💻 app: +10
Day 15/31 • Today: 10 • Total: 35/90
[███░░░░░░░] 38%
Need 10 more to catch up!
```
*Note: No checkmarks because both challenges are still behind expected cumulative progress*

**When One Challenge Caught Up (Partial Completion):**
```
✅ 💪 Push-ups: +268
Day 10/30 • Today: 268 • Total: 500/1500
[███░░░░░░░] 33%
You're doing great — you're on track!

🧑‍💻 app: +2
Day 15/31 • Today: 2 • Total: 37/90
[████░░░░░░] 41%
Need 8 more to catch up!
```
*Note: Push-ups has checkmark (caught up), but no "Day Complete" header yet because app is still behind*

**When All Challenges Caught Up:**
```
✅ Day Complete!

✅ 💪 Push-ups: +50
Day 10/30 • Today: 50 • Total: 500/1500
[███░░░░░░░] 33%
You're doing great — you're on track!

✅ 🧑‍💻 app: +8
Day 15/31 • Today: 8 • Total: 45/90
[█████░░░░░] 50%
You're doing great — you're on track!
```
*Note: All challenges have checkmarks AND "Day Complete" header shows because all are caught up*

### API Response

The REST API returns the `is_daily_complete` flag in `ExerciseStatsOut`:
```json
{
  "exercise_type_id": 1,
  "exercise_type_name": "Push-ups",
  "cumulative_total": 500,
  "target_total": 1500,
  "day_number": 10,
  "total_days": 30,
  "daily_target": 50,
  "is_daily_complete": true,
  ...
}
```
*Note: `is_daily_complete: true` means cumulative_total (500) >= expected_progress (500), indicating the challenge is on track*

**Last Updated:** Added per-challenge checkmarks when caught up; completion logic checks cumulative progress (2026-01-16)
