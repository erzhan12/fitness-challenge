# Fitness-Challenge -> Habit Reward API Integration

## Current State

The integration already exists in `app/services/habit_reward_client.py` but has **3 bugs** that need fixing, plus 1 enhancement (REST API trigger).

---

## Bug Fixes Required

### Bug 1: Wrong URL path

**File:** `app/services/habit_reward_client.py:39`

The habit_reward API uses `/v1/` prefix, not `/api/v1/`.

```python
# WRONG (current)
url = f"{base_url}/api/v1/habits/{habit_id}/complete"

# CORRECT
url = f"{base_url}/v1/habits/{habit_id}/complete"
```

### Bug 2: Wrong auth header

**File:** `app/services/habit_reward_client.py:41-44`

The habit_reward API expects `X-API-Key` header for API key auth, not `Authorization: Bearer`. The Bearer scheme is for JWT tokens only.

```python
# WRONG (current)
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
}

# CORRECT
headers = {
    "X-API-Key": api_key,
    "Content-Type": "application/json",
}
```

### Bug 3: Wrong payload field name

**File:** `app/services/habit_reward_client.py:46-48`

The habit_reward API expects `target_date`, not `date`.

```python
# WRONG (current)
payload = {}
if completion_date:
    payload["date"] = completion_date.isoformat()

# CORRECT
payload = {}
if completion_date:
    payload["target_date"] = completion_date.isoformat()
```

---

## Fixed `habit_reward_client.py`

Replace the entire `send_habit_completion` function.

Note: `habit_id` and `api_key` are now read from the `UserSettings` DB record (per-user), while `base_url` remains from env config.

```python
async def send_habit_completion(
    user_id: int, completion_date: Optional[date] = None
) -> bool:
    """Send daily habit completion to Habit Reward API.

    Args:
        user_id: The AppUser ID (used to fetch per-user habit reward settings)
        completion_date: Date of completion (optional, for potential backdating)

    Returns:
        True if successful (200 response), False otherwise
    """
    user_settings = await user_settings_repo.get_by_user_id(user_id)
    if not user_settings:
        logger.debug("No user settings found, skipping habit reward")
        return False

    api_key = user_settings.habit_reward_api_key
    habit_id = user_settings.habit_reward_habit_id
    if not api_key or not habit_id:
        logger.debug("Habit Reward not configured for user, skipping")
        return False

    base_url = settings.HABIT_REWARD_BASE_URL

    url = f"{base_url}/v1/habits/{habit_id}/complete"

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
    }

    payload = {}
    if completion_date:
        payload["target_date"] = completion_date.isoformat()

    logger.info(f"Sending habit completion to {url}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url,
                json=payload if payload else None,
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            logger.info(f"Habit completion sent successfully: {response.status_code}")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Habit Reward API returned error: {e.response.status_code} - "
                f"{e.response.text[:200]}"
            )
            return False
        except httpx.RequestError as e:
            logger.error(f"Failed to send habit completion: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending habit completion: {e}")
            return False
```

---

## Enhancement: Trigger from REST API log creation

Currently, `notify_habit_reward_if_complete()` is only called from the Telegram bot flow (`workout_service.py:1151`). The REST API `POST /api/v1/logs` endpoint does NOT trigger it.

### Option A: Add check in `src/api/services.py` `create_log()`

After creating the log and computing stats, check if all challenges are complete:

```python
# In src/api/services.py create_log() function, after stats computation:
from app.services.workout_service import notify_habit_reward_if_complete

# Check if all challenges are complete for today (pass user_id for per-user settings)
await notify_habit_reward_if_complete(log_date, user_id=user_id)
```

### Option B: Add check in `src/api/routers/logs.py` endpoint

After successful log creation:

```python
@router.post("", ...)
async def create_new_log(data, ..., current_user: AppUser = Depends(get_current_user)):
    log, stats = await create_log(data, user_id=current_user.id)

    # Fire-and-forget: check if all daily challenges are now complete
    try:
        from app.services.workout_service import notify_habit_reward_if_complete
        await notify_habit_reward_if_complete(log.date, user_id=current_user.id)
    except Exception as e:
        logger.warning(f"Habit reward check failed: {e}")

    return ExerciseLogCreateResponse(log=log, stats=stats)
```

---

## Configuration

### Per-User Settings (stored in `user_settings` DB table)

These are per-user fields on the `UserSettings` model (`src/core/models.py`):

| Field | Type | Description |
|-------|------|-------------|
| `habit_reward_api_key` | `CharField(max_length=255, blank=True, default="")` | API key for Habit Reward. Generate via the habit_reward Telegram bot's API key feature. |
| `habit_reward_habit_id` | `IntegerField(null=True, blank=True)` | The habit ID to mark as complete. Find via `GET /v1/habits` with auth. |

The feature is **disabled** for a user if either field is empty/null.

Manageable via:
- Django admin panel (`/admin/`)
- REST API: `PATCH /api/v1/users/me/settings` with `{"habit_reward_api_key": "hrk_...", "habit_reward_habit_id": 54}`

### Environment Variable (shared, in `.env`)

```env
# Habit Reward Integration
HABIT_REWARD_BASE_URL=https://habitreward.org
```

- `HABIT_REWARD_BASE_URL`: Base URL of the habit_reward API (default: `https://habitreward.org`). Same for all users.

---

## Habit Reward API Reference

### Complete a habit
```
POST /v1/habits/{habit_id}/complete
```

**Headers:**
```
X-API-Key: hrk_your_api_key
Content-Type: application/json
```

**Body (optional):**
```json
{
  "target_date": "2026-02-01"
}
```
If `target_date` is omitted, defaults to today. Can be up to 7 days back.

**Success response (200):**
```json
{
  "habit_confirmed": true,
  "habit_name": "Complete Workout",
  "streak_count": 5,
  "got_reward": true,
  "total_weight_applied": 50.0,
  "reward": {
    "id": 17,
    "name": "reward_name",
    "pieces_required": 10
  },
  "cumulative_progress": {
    "pieces_earned": 6,
    "pieces_required": 10,
    "claimed": false,
    "progress_percent": 60.0
  }
}
```

**Error responses:**
- `401` - Invalid/missing API key
- `404` - Habit not found
- `409` - Already completed for that date
