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
- **`src/core/utils.py`** - Shared utilities (progress calculations, date helpers)
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

## Active Challenges (Date Window) & Empty-Window Policy

**"Active for Telegram / parse"** means in the date window:
`is_active=True` AND `start_date ≤ today ≤ end_date`
(`ExerciseChallengeRepository.get_current_active` / `list_current_active_challenges`).

When the in-window set is empty, workout parse/log flows must **not** fall back to all exercise types or invent `Day 1/30 · 990` cards. Both Telegram (`process_incoming_message`) and REST (`POST /workouts/parse`) return the same copy and skip parsing/logging:

> No active challenges right now. Create one with /challenge or extend an existing challenge's dates.

Expired challenges (`end_date < today`) have their `is_active`/`is_default` flags cleared by a single best-effort sweep in `send_evening_reminder` (all users, fail-open, runs even when reminders are disabled).

**Do NOT sweep on the read path.** `list_current_active_challenges` must not call `deactivate_expired_challenges` — `get_current_active` already excludes expired rows by the date window, so clearing the stored flag is admin-only hygiene and a per-read DB write would add latency to the hot workout parse/log path for no functional gain.

Date-window filtering remains the source of truth for what is shown; auto-clear is admin/data hygiene.

**Pitfall to Avoid:**
Never thread a display/`target_date` into `deactivate_expired_challenges` — the production sweep uses real today only. Only unit tests pass an explicit cutoff date.

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

The application includes an automated evening reminder system that sends Telegram notifications at each user's configured reminder hours for incomplete challenges. Default schedule is 1pm, 9pm, and 10pm (`DEFAULT_REMINDER_HOURS = [13, 21, 22]` in `app/constants.py`).

### Components

**Data Layer:**
- `UserSettings` model (`src/core/models.py`) — per-user reminder configuration:
  - `is_reminder_active`: Boolean toggle for reminders
  - `telegram_chat_id`: Auto-captured from Telegram messages (required for send; no `TARGET_CHAT_ID` fallback)
  - `reminder_hours`: JSON list of ints `0–23` (default `[13, 21, 22]`; admin-editable; `[]` = opt-out)
  - `last_reminder_sent_dates`: JSON map `{"21": "2026-07-25", ...}` for per-hour idempotency
- `UserSettingsRepository` (`src/core/repositories.py`) — async repository with methods:
  - `get_users_for_reminder_hour()`, `get_distinct_active_reminder_hours()`, `try_mark_hour_sent()`, `clear_hour_sent()`
- `AppSettings` model — singleton retaining only `is_registration_open` (reminder fields removed in migration 0011)
- `AppSettingsRepository` — `get_singleton()`, `update()` for app-wide non-reminder settings only

**Reminder Logic (Cumulative Catch-Up):**
- `compute_evening_reminder()` (`app/services/workout_service.py`) - Determines incomplete challenges using **cumulative progress**:
  - Fetches `cumulative_total` per challenge (all logs up to today)
  - Computes `expected_progress` using `calculate_expected_progress(target_total, day_number, total_days, daily_target)` from `src/core/utils.py`
  - A challenge is "incomplete" when `cumulative_total < expected_progress` (not caught up)
  - Deficit shown as `need X more to catch up`
  - **Silent** when all challenges are caught up (no message sent)
  - Per-challenge: only behind challenges appear in the reminder
  - Returns combined HTML message with motivational text
- **Behavioral change (2026-02-06):** Previously reminders checked `today_total < daily_target` (daily activity). Now they check cumulative progress vs expected pace. This means a user who did a lot today but is still behind overall will still get a reminder, and a user who did nothing today but is ahead overall will NOT get a reminder.
- `send_evening_reminder()` (`app/services/workout_service.py`) - Sends reminders per user:
  - Iterates users with `is_reminder_active`, approved status, `telegram_chat_id`, and hour in `reminder_hours`
  - Atomic claim via `try_mark_hour_sent()` before send; clears claim on failure
  - Sends one combined message per user per hour listing incomplete challenges
  - No `TARGET_CHAT_ID` fallback when `telegram_chat_id` is missing
- `generate_reminder_motivation()` (`app/services/openai_service.py`) - LLM-generated motivation:
  - Short (1-2 sentences), encouraging tone
  - Context-aware based on hour and remaining work
  - Fallback messages if LLM fails

**Scheduler:**
- `start_reminder_scheduler()` (`app/services/reminder_scheduler.py`) - Background task:
  - Wakes on union of enabled users' `reminder_hours` (any hour `0–23`)
  - Falls back to `DEFAULT_REMINDER_HOURS` for sleep timing only when no active schedules exist
  - Sleeps until target time, then triggers `send_evening_reminder(hour)`
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
  - `hour=<int>`: Evening reminder with combined message for that hour

**Django Admin:**
- `UserSettingsAdmin`: editable `reminder_hours`, `is_reminder_active`, `telegram_chat_id`; readonly `last_reminder_sent_dates`
- `AppSettingsAdmin`: `is_registration_open` only

### Files
- **Models:** `src/core/models.py` (UserSettings, AppSettings)
- **Repositories:** `src/core/repositories.py` (UserSettingsRepository, AppSettingsRepository)
- **Reminder Logic:** `app/services/workout_service.py` (compute_evening_reminder, send_evening_reminder)
- **Scheduler:** `app/services/reminder_scheduler.py`
- **LLM Integration:** `app/services/openai_service.py` (generate_reminder_motivation)
- **API:** `src/api/routers/settings.py`, `src/api/services.py`, `src/api/models.py`
- **Telegram:** `app/routers/telegram.py` (auto-capture chat_id)
- **Tests:** `tests/api/test_settings.py`
- **Migrations:** `0010_per_user_reminder_hours.py`, `0011_per_user_reminder_cutover.py`

**Last Updated:** Per-user reminder hours and JSON idempotency (Feature 0022, 2026-07-25)

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
- Does NOT show when every active challenge is on an exception/rest day today (no scheduled work — Feature 0019)
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

---

## Multi-User Support Architecture (Feature 0010)

The application is being migrated from single-user to multi-user support. This section documents the architecture decisions and implementation patterns.

### Phase Overview

**Phase 1 - Data Layer (COMPLETE):** Django models `AppUser` and `UserSettings` with migrations
**Phase 2 - Repository Layer (COMPLETE):** All repository methods accept optional `user_id` parameter
**Phase 3 - REST API (COMPLETE):** `/api/v1/users` endpoints + `get_current_user` dependency
**Phase 4 - Telegram Registration (COMPLETE):** Auto-registration + approval flow
**Phase 5 - User-Scoped Operations (TODO):** Stats, logs, challenges scoped per user
**Phase 6 - Testing & Docs (TODO):** Comprehensive tests + updated documentation

### Database Models

#### AppUser (`src/core/models.py`)
- Fields: `id`, `telegram_user_id` (unique), `username`, `first_name`, `timezone`, `status` (pending/approved/rejected), `created_at`, `approved_at`
- Uses `TextChoices` for status: `AppUser.Status.PENDING`, `AppUser.Status.APPROVED`, `AppUser.Status.REJECTED`
- Property: `is_approved` returns `status == Status.APPROVED`
- Auto-created with each user registration; status defaults to PENDING

#### UserSettings (`src/core/models.py`)
- One-to-One relationship with `AppUser`
- Fields: `user_id` (FK), `telegram_chat_id`, `is_reminder_active`, `reminder_hours` (default `[13, 21, 22]`), `last_reminder_sent_dates` (JSON idempotency map), `is_workout_motivation_active`, habit-reward fields
- `reminder_hours`: admin-editable list of ints `0–23`; empty list disables sends for that user
- `last_reminder_sent_dates`: keys are hour strings (`"21"`), values are ISO dates; replaces per-hour date columns

#### Updated Models
- `ExerciseType`: Added `user_id` FK (nullable for migration); unique constraint changed to `(user, name)`
- `ExerciseChallenge`: Added `user_id` FK (nullable for migration)
- `ExerciseLog`: Added `user_id` FK (nullable for migration)
- `UserStats`: Changed from `OneToOne(ExerciseType)` to `ForeignKey(ExerciseType)` + added `user_id` FK; unique constraint is `(user, exercise_type)`

### Repository Layer Pattern

All repositories in `src/core/repositories.py` follow this pattern:

**New Repositories:**
- `AppUserRepository`: User CRUD + approval/rejection
- `UserSettingsRepository`: Per-user settings (mirrors old AppSettingsRepository but scoped)

**Updated Methods:**
All existing repository methods accept optional `user_id` parameter (default `None` for backward compat):

```python
# Pattern: method signature
async def get_by_id(self, id: int, user_id: Optional[int] = None) -> Optional[Model]:
    queryset = Model.objects.filter(id=id)
    if user_id is not None:
        queryset = queryset.filter(user_id=user_id)  # Ownership verification
    return queryset.get()
```

**Key Repositories Updated:**
- `ExerciseTypeRepository`: `get_all()`, `get_by_id()`, `get_by_name()`, `update()`, `get_by_ids()` all accept optional `user_id`
- `ExerciseChallengeRepository`: `get_all()`, `get_by_id()`, `get_active_for_type()`, `get_current_active()`, `update()` accept optional `user_id`
- `ExerciseLogRepository`: All query methods accept optional `user_id` for filtering
- `UserStatsRepository`: `get_all()`, `get_by_exercise_type()`, `get_or_create()`, `increment_total()`, `decrement_total()`, `sync_last_logged_date()` accept optional `user_id`

**Ownership Verification:**
The `get_by_id()` and `delete()` methods verify user ownership when `user_id` is provided, preventing cross-user data access.

### REST API Layer

#### API Models (`src/api/models.py`)
- `UserOut` - User profile response with status, timezone, timestamps
- `UserCreate` - Registration request (telegram_user_id required)
- `UserUpdate` - Profile update (partial)
- `UserSettingsOut` - Settings with reminder flags
- `UserSettingsUpdate` - Settings update (partial)
- `UserWithSettingsOut` - Combined user + settings response

#### Authentication Dependency (`src/api/security.py`)
- `get_current_user()` - Extracts `X-Telegram-User-Id` header, verifies user exists and is approved (403 if not)
- `get_current_user_optional()` - Same but returns None if header missing (for public endpoints)

**Usage:**
```python
async def get_profile(current_user: AppUser = Depends(get_current_user)):
    # current_user.id, current_user.telegram_user_id, etc.
```

#### Users Router (`src/api/routers/users.py`)
- `POST /api/v1/users` - Register (auto-pending)
- `GET /api/v1/users/me` - Get profile + settings (requires X-Telegram-User-Id header)
- `PATCH /api/v1/users/me` - Update profile (requires X-Telegram-User-Id header)
- `GET/PATCH /api/v1/users/me/settings` - Settings management (requires X-Telegram-User-Id header)
- `GET /api/v1/users` - Admin: list all users (requires API key)
- `POST /api/v1/users/{id}/approve` - Admin: approve user (requires API key)
- `POST /api/v1/users/{id}/reject` - Admin: reject user (requires API key)

### Data Migration

**Migration Files:**
- `0003_add_multi_user_support.py` - Schema: creates AppUser + UserSettings, adds user_id FKs
- `0004_backfill_default_user.py` - Data: creates default user (telegram_user_id=0) and assigns all existing data to it

**Backfill Logic:**
1. Creates AppUser with telegram_user_id=0 (system user for legacy data)
2. Copies AppSettings singleton values to UserSettings for default user
3. Updates all ExerciseType/Challenge/Log/Stats rows to reference default user

### Key Architectural Decisions

1. **Optional user_id parameters:** All repository methods accept optional `user_id` to maintain backward compatibility during migration. Once user_id is required in models, we can gradually enforce it in services/routers.

2. **Separate AppUser model:** We use a dedicated `AppUser` model instead of extending Django's `auth_user` to avoid custom auth migrations and keep user management clean.

3. **X-Telegram-User-Id header:** Uses explicit header for user context (not JWT/tokens yet) to align with Telegram bot integration. Can be extended to JWT later.

4. **Per-user idempotency:** `UserSettingsRepository` replaces the singleton `AppSettingsRepository` pattern for reminder operations, using `last_reminder_sent_dates` JSON and `try_mark_hour_sent()` conditional SQLite updates.

5. **Approval flow:** Users start in `pending` status and must be manually approved by admin. This prevents unauthorized access during beta.

### Files to Update in Next Phases

**Phase 4 - Telegram Integration:**
- `app/routers/telegram.py` - Extract telegram_user_id from webhook
- `app/services/workout_service.py` - Registration gating + user context
- `app/config.py` - Add SUPERUSER_TELEGRAM_IDS config

**Phase 5 - User-Scoped Operations:**
- `src/api/services.py` - Thread user_id through all functions
- `src/api/routers/*.py` - Add get_current_user dependency to endpoints
- `app/services/reminder_scheduler.py` - Per-user reminder iteration

**Phase 6 - Testing & Docs:**
- `tests/api/conftest.py` - Add user fixtures
- `README.md`, `docs/features/0010_*.md` - Update documentation
- Comprehensive multi-user isolation tests

### Testing Notes

During Phase 1-3, backward compatibility is maintained:
- All 174 existing tests continue to pass
- user_id parameters are optional
- Legacy single-user queries work without user_id
- Migration backfill ensures existing data is accessible

**For future tests:** Use `X-Telegram-User-Id` header for authenticated endpoints. Mock `get_current_user` in test fixtures to inject test users.

### Telegram Registration Flow (Phase 4)

**Auto-Registration (`app/routers/telegram.py`, `app/services/workout_service.py`):**

When a user sends a message to the Telegram bot:
1. Webhook extracts `telegram_user_id`, `first_name`, `username` from `update.message.from_`
2. These are passed to `process_incoming_message(text, chat_id, telegram_user_id, first_name, username)`
3. Function calls `app_user_repo.get_or_create_by_telegram_user_id()` to auto-register new users
4. If new user created, `UserSettings` is also created with the `telegram_chat_id`
5. New users default to `status=PENDING`

**Registration Gating:**

After auto-registration, the bot checks `user.is_approved`:
- If `status == "pending"`: Shows "Registration Pending" message with telegram_user_id
- If `status == "rejected"`: Shows "Access Denied" message
- If `status == "approved"`: User proceeds to normal bot functionality
- Non-approved users cannot use any bot features except `/status`

**Superuser Commands:**

Configuration: Add comma-separated telegram user IDs to `.env`:
```
SUPERUSER_TELEGRAM_IDS=123456789,987654321
```

Available commands:
- `/status` - Any user can check their registration status (shows status, telegram_user_id, username, registration date, approval date)
- `/approve <telegram_user_id>` - **Superuser only.** Approves a user by telegram_user_id. Notifies the approved user.
- `/reject <telegram_user_id>` - **Superuser only.** Rejects a user by telegram_user_id. Notifies the rejected user.

**Notification Flow:**

When a superuser approves/rejects a user:
1. The target user's `UserSettings.telegram_chat_id` is retrieved
2. A notification message is sent to the user's chat
3. Approved users receive a welcome message with instructions
4. Rejected users receive an access denied message

**Key Files Modified:**
- `app/config.py` - Added `SUPERUSER_TELEGRAM_IDS` field with validator
- `app/routers/telegram.py` - Extract telegram_user_id and pass to service
- `app/services/workout_service.py` - Auto-registration, gating, command handlers

**Last Updated:** Implemented Phases 1-4 of multi-user support (2026-01-19)

---

## Input Validation for Telegram IDs

All user-supplied Telegram user IDs (especially in admin commands) must be validated to prevent invalid or malicious input.

### Validators (`src/core/validators.py`)

**Available Validators:**
- `validate_telegram_chat_id(chat_id: int)` - Validates chat IDs (range: -10^15 to 10^15)
- `validate_telegram_user_id(user_id: int)` - Validates user IDs (range: 0 < user_id <= 10^12)

**When to Use:**
- Any admin command that accepts telegram_user_id as user input (e.g., `/approve`, `/reject`)
- API endpoints that accept Telegram IDs in request body or query parameters
- Before database lookups using user-supplied IDs

**Pattern:**
```python
from src.core.validators import validate_telegram_user_id

try:
    target_telegram_user_id = int(parts[1])
    validate_telegram_user_id(target_telegram_user_id)  # Validates range
    # Proceed with database operations
    user = await app_user_repo.get_by_telegram_user_id(target_telegram_user_id)
except ValueError as e:
    # Show user-friendly error with validation message
    await send_telegram_message(chat_id, f"❌ Invalid input: {str(e)}")
```

**What Gets Validated:**
- ✅ Positive integers only (user IDs cannot be negative or zero)
- ✅ Upper bound check (prevents excessively large values)
- ❌ Rejects: 0, negative numbers, values > 10^12

**Key Files:**
- `src/core/validators.py` - Validation functions
- `app/services/workout_service.py:706` - `/approve` command validation
- `app/services/workout_service.py:765` - `/reject` command validation

**Pitfall to Avoid:**
Don't trust user input from Telegram commands without validation. Always validate Telegram IDs before using them in database queries, even when protected by permission checks.

**Last Updated:** Added input validation for telegram_user_id in admin commands (2026-01-20)

---

## Habit Reward Integration (Feature 0011)

When all daily exercises are completed, the system can optionally send a POST request to an external habit tracking app (habitreward.org) to mark the fitness habit as done. Triggered from both the Telegram bot and REST API `POST /api/v1/logs`.

### Configuration

**Per-user** (stored in `user_settings` DB table, managed via Django admin or `PATCH /api/v1/users/me/settings`):
- `habit_reward_api_key` — API key for Habit Reward (generate via the habit_reward Telegram bot)
- `habit_reward_habit_id` — The habit ID to mark as complete

**Shared** (environment variable):
```bash
HABIT_REWARD_BASE_URL=https://habitreward.org  # Optional, defaults to this
```

The feature is disabled for a user if either `habit_reward_api_key` or `habit_reward_habit_id` is empty/null.

### How It Works

1. User logs exercises via Telegram or REST API
2. Both call `notify_habit_reward_if_complete(date, user_id)` which internally:
   - Fetches active challenges for the user
   - Checks if all are on track (`_check_all_challenges_complete()`)
     - A challenge whose today is an exception/rest day never blocks Habit Reward (Feature 0018)
     - If **every** active challenge is on an exception/rest day today, the day is not completable: `_check_all_challenges_complete` returns `False`, so no Habit Reward and no `✅ Day Complete!`, even when reps were banked ahead (Feature 0019 / issue #29)
   - If not all complete, returns True (not an error, just not ready)
3. If all complete:
   - Atomically claims the date (prevents concurrent requests from double-sending)
   - POSTs to `{base_url}/v1/habits/{habit_id}/complete` with `X-API-Key` header
   - On 200 response, keeps the claim; on failure, clears claim to allow retry

### Idempotency (Atomic Claim Pattern)

Uses `UserSettings.last_habit_reward_sent_date` (per-user) with an atomic claim pattern to prevent race conditions under concurrent requests:

**Pattern:**
1. **Atomic claim**: Attempt to set `last_habit_reward_sent_date = today` using `filter().exclude(last_habit_reward_sent_date=today).update()`
2. If claim succeeds (rows updated > 0): proceed to send API request
3. If claim fails (rows updated = 0): another request already claimed this date, skip
4. **Rollback on failure**: If API call fails, clear the claim to allow retry

**Key Methods in `UserSettingsRepository`:**
- `try_claim_habit_reward_date(user_id, date)` - Returns True if claim successful (atomic conditional update)
- `clear_habit_reward_claim(user_id, date)` - Clears claim on API failure

**Why not check-then-mark?**
A simple check-then-mark pattern is non-atomic: two concurrent requests could both pass the check before either marks the date, causing duplicate sends. The atomic claim pattern prevents this by using Django's `filter().exclude().update()` which is a single atomic database operation.

### Error Handling

- Fire-and-forget: API failures don't block user experience
- Errors are logged but not shown to users
- If API call fails, field is not updated (allows retry on next completion)

### Key Files

- `app/config.py` - `HABIT_REWARD_BASE_URL` shared env var
- `app/services/habit_reward_client.py` - HTTP client (`send_habit_completion(user_id, date)`)
- `app/services/workout_service.py` - Integration (`notify_habit_reward_if_complete(date, user_id)`)
- `src/core/models.py` - `UserSettings.habit_reward_api_key`, `habit_reward_habit_id`, `last_habit_reward_sent_date`
- `src/core/repositories.py` - `UserSettingsRepository.try_claim_habit_reward_date`, `clear_habit_reward_claim`
- `src/api/routers/logs.py` - REST API trigger after log creation
- `src/api/models.py` - `UserSettingsOut`/`UserSettingsUpdate` include habit reward fields
- `tests/services/test_habit_reward_client.py` - Unit tests

**Last Updated:** Fixed REST API to check all challenges complete before sending; added atomic claim pattern (2026-02-03)

---

## LLM-Powered Resource Creation Pattern

When adding LLM-powered "create from prompt" endpoints, follow this pattern:

### Structure

1. **LLM parser function** in `app/services/openai_service.py`:
   - Takes `text`, a list of domain objects (e.g. exercise types), and contextual args (e.g. `today`)
   - Calls LLM with `response_format={"type": "json_object"}`, `temperature=0`
   - Returns a dict with `is_valid: bool` and `error_reason: str | null`
   - On LLM exception, returns `{"is_valid": False, "error_reason": "AI parsing failed..."}`

2. **Import at module level** in `src/api/services.py`:
   - Import the LLM parser at the **top of the file** (not inside the function), so tests can patch it as `src.api.services.parse_challenge_prompt`
   - ❌ Wrong: `from app.services.openai_service import parse_challenge_prompt` inside function body
   - ✅ Correct: at module level in `src/api/services.py`

3. **Service orchestration function** in `src/api/services.py`:
   - Fetches prerequisite data (exercise types, today's date)
   - Calls LLM parser
   - Validates output, raises `ValueError` for bad input
   - Raises custom `SomethingNotFoundError(name, available_names)` when a referenced resource doesn't exist
   - Delegates final DB write to existing `create_*()` function

4. **Endpoint** in `src/api/routers/`:
   - Catches `SomethingNotFoundError` → 404 with available names in detail
   - Catches `ValueError` → 400
   - Catches generic `Exception` → 503 if LLM-related, else 400

### Test Patching

Always patch at the import site (`src.api.services.parse_challenge_prompt`), NOT at the definition site (`app.services.openai_service.parse_challenge_prompt`). The mock only works where the name is looked up.

### Files
- `app/services/openai_service.py` — `parse_challenge_prompt()`
- `src/api/services.py` — `create_challenge_from_prompt()`, `ExerciseTypeNotFoundError`
- `src/api/routers/challenges.py` — `POST /challenges/create-from-prompt`
- `tests/services/test_openai_service.py` — unit tests for LLM parser
- `tests/api/test_challenges.py` — `TestCreateChallengeFromPrompt`

**Last Updated:** Added LLM-powered challenge creation pattern (2026-03-04)
