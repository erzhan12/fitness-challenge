# Project Coding Rules

## REST API Convention

**IMPORTANT**: For any new business logic function that handles:
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

## Code Organization

### Project Structure
```
src/api/              # REST API layer
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
├── routers/          # Telegram webhook and admin endpoints
└── services/         # Existing Telegram-focused services
```

### Separation of Concerns
- **`src/api/`** - HTTP/JSON-first, returns structured data
- **`app/services/`** - Can return HTML-formatted strings for Telegram
- Share domain logic by extracting pure computations into reusable helpers

## Testing Standards

### Test File Organization
- One test file per router: `test_exercises.py`, `test_challenges.py`, etc.
- Group tests by endpoint using test classes
- Use descriptive test names: `test_create_log_unauthorized`, `test_list_challenges_filter_active`

### Required Test Coverage
- ✅ Success cases (200, 201)
- ✅ Not found (404)
- ✅ Bad request (400)
- ✅ Validation errors (422)
- ✅ Unauthorized (401)
- ✅ Forbidden (403)
- ✅ Empty results
- ✅ Pagination
- ✅ Filters and query parameters

### Mock Pattern
```python
from unittest.mock import patch, Mock
from tests.api.conftest import create_mock_query

def test_create_exercise_success(client, auth_headers, mock_exercise_type_data):
    with patch("src.api.services.get_supabase") as mock_get_sb:
        mock_sb = Mock()
        mock_sb.table.return_value.insert.return_value = create_mock_query(
            [mock_exercise_type_data]
        )
        mock_get_sb.return_value = mock_sb

        response = client.post(
            "/api/v1/exercises",
            json={...},
            headers=auth_headers
        )

        assert response.status_code == 201
```

## Documentation

### Code-Level Documentation
Primary documentation lives in the code:
- FastAPI endpoint decorators (summary, description, tags, responses)
- Function docstrings
- Pydantic model field descriptions

### Auto-Generated Docs
FastAPI automatically generates:
- `/docs` - Swagger UI (interactive testing)
- `/openapi.json` - OpenAPI 3 specification

### High-Level Docs
- `docs/features/0003_PLAN.md` - Architecture and design decisions
- This file (`.claude/CODE_RULES.md`) - Development conventions

## Git Workflow

When adding new endpoints:
1. Create feature branch from `main`
2. Implement endpoint + tests
3. Run tests: `pytest tests/api/`
4. Verify docs at `http://localhost:8000/docs`
5. Commit with descriptive message
6. Create PR for review

---

**Remember**: Every new business function should be accessible via the REST API. The API is the primary interface for all operations.
