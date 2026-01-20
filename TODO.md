# Fitness Challenge Bot - TODO

Create manual step by step commands to check logs

## Quick Wins (High Impact, Low Effort)

### Streak Tracking
- [ ] Add `streaks` table to database (user_id, exercise_type_id, current_streak, longest_streak, last_log_date)
- [ ] Implement streak calculation logic in `src/api/services.py`
- [ ] Create `/api/v1/streaks` endpoint (GET by user/exercise)
- [ ] Display streak count in Telegram workout responses
- [ ] Add milestone messages (7, 30, 100 days)
- [ ] Add unit tests in `tests/api/test_stats.py`

### Personal Records (PRs)
- [ ] Add `personal_records` table (user_id, exercise_type_id, record_type, value, achieved_at)
- [ ] Implement PR calculation on log creation
- [ ] Create `/api/v1/stats/personal-records` endpoint
- [ ] Announce new PRs in Telegram with special formatting
- [ ] Add unit tests

### Weight Tracking
- [ ] Add `weight_logs` table (user_id, date, weight_kg, notes)
- [ ] Create `/api/v1/weight` endpoints (POST, GET with date range)
- [ ] Add Telegram command `/weight 75.5 [notes]`
- [ ] Calculate trends (7-day average, monthly change)
- [ ] Add unit tests

### Deterministic Input Parsing (Pre-LLM)
- [X] When a user enters workout text, try deterministic parsing first; only use LLM as fallback
- [X] Ensure `exercise_types.aliases` (list/array) is populated with variations (e.g., `["pushups","pushup","push-ups","push-up"]`) for matching
- [X] If input is just a number and there is exactly one active challenge, log it to that challenge
- [X] If input is `<number> <word>`, match `<word>` against active challenges using exercise type `name` + `aliases` (handle singular/plural and punctuation variations), then log it
- [X] If input contains multiple `<number> <word>` pairs, parse all pairs and log each to the matching active challenge
- [X] If deterministic parsing is ambiguous or fails, fall back to LLM parsing
- [X] Add unit tests covering ambiguous inputs and fallback-to-LLM behavior
- [X] Add validation check: if user entered any number that could be considered as 0 (e.g., 0, 0.0, 0.00, 0.1, 0.01, 0.001, or any value <= 0), don't log it, instead show message that it should be greater than 0 and integer

### Daily Challenge Completion Indicator
- [ ] Track completion status for each challenge per user per day
- [ ] Add logic to check if challenge target is met (in `src/api/services.py`)
- [ ] Display ✅ (green check mark) in Telegram workout response when daily target is completed
- [ ] Format: `✅ Push-ups: 50/50 reps` (show check mark before the challenge name when completed)
- [ ] Keep challenge in list even when completed, but highlight with green indicator
- [ ] Add visual distinction for completed vs pending challenges (emoji or styling)
- [ ] Update `/start` command to show completion status for the day
- [ ] Reset indicator at midnight for each timezone
- [ ] Add unit tests in `tests/api/test_services.py`

### LLM-Powered Exercise Type Creation
- [ ] Create `/api/v1/exercises/create-from-prompt` endpoint (POST) that accepts natural language text describing an exercise
- [ ] Create LLM parsing service to extract exercise details from natural language input
- [ ] Parse exercise description into JSON format with fields: name, aliases (array), description (optional), category (optional)
- [ ] Validate parsed data (check for duplicates, validate format)
- [ ] If exercise already exists, return existing exercise details or suggest similar exercises
- [ ] Save parsed exercise type to database via existing exercise creation endpoint
- [ ] Return created exercise details in response
- [ ] Handle error cases (invalid format, missing required fields, duplicate names)
- [ ] Add Pydantic models for request/response bodies (prompt text input, parsed exercise output)
- [ ] Add unit tests in `tests/services/test_openai_service.py` for LLM exercise parsing
- [ ] Add API endpoint tests in `tests/api/test_exercises.py`

### LLM-Powered Challenge Creation
- [ ] Create `/api/v1/challenges/create-from-prompt` endpoint (POST) that accepts natural language text and uses LLM to parse and create challenge
- [ ] Create LLM parsing service to extract challenge details from natural language input
- [ ] Parse challenge description into JSON format with fields: exercise_type, duration_days, start_date, target_type (total/daily), target_value
  - LLM can extract either `target_total` (e.g., "2000 reps total") or `daily_target` (e.g., "50 pushups daily")
  - If only one is provided, calculate the other; if both provided, validate consistency
- [ ] Validate parsed data and check if exercise type exists in database
- [ ] If exercise type doesn't exist, return error response with message prompting user to choose from existing exercise types or create new using `/new_exercise` command
- [ ] Save parsed challenge to database via existing challenge creation endpoint
- [ ] Return created challenge details in response
- [ ] Handle error cases (invalid format, missing fields, date parsing errors, exercise type not found)
- [ ] Add Pydantic models for request/response bodies (prompt text input, parsed challenge output)
- [ ] Add unit tests in `tests/services/test_openai_service.py` for LLM challenge parsing
- [ ] Add API endpoint tests in `tests/api/test_challenges.py`

### Challenge Creation via Telegram
- [ ] Add Telegram command `/new_challenge` in `app/routers/telegram.py`
- [ ] Implement interactive flow: send prompt message asking user to describe challenge in natural language
- [ ] Format prompt message: "Please text a message in the following format: pushups challenge for 30 days starting from tomorrow (or another specific date) 2000 reps in total (or daily 50 pushups)"
- [ ] Call `/api/v1/challenges/create-from-prompt` endpoint with user's natural language input
- [ ] Handle response from LLM-powered endpoint (success, validation errors, exercise type not found)
- [ ] If exercise type doesn't exist, send message prompting user to choose from existing exercise types or create new using `/new_exercise` command
- [ ] Send confirmation message with challenge details
- [ ] Handle error cases (invalid format, LLM parsing failures, date parsing errors)
- [ ] Add integration tests for full Telegram flow

### Exercise Type Creation via Telegram
- [ ] Add Telegram command `/new_exercise` in `app/routers/telegram.py`
- [ ] Implement interactive flow: send prompt message asking user to describe exercise in natural language
- [ ] Format prompt message: "Please describe the exercise you want to create (e.g., 'pushups' or 'barbell bench press' or 'running 5km')"
- [ ] Call `/api/v1/exercises/create-from-prompt` endpoint with user's natural language input
- [ ] Handle response from LLM-powered endpoint (success, validation errors, duplicate detection)
- [ ] If exercise already exists, show existing exercise details and suggest using it
- [ ] Send confirmation message with created exercise details (name, aliases)
- [ ] Handle error cases (invalid format, LLM parsing failures)
- [ ] Add integration tests for full Telegram flow

### Challenge Target Fields Refactoring (Remove Redundant daily_target)
- [ ] Remove `daily_target` database field from `ExerciseChallenge` model
- [ ] Make `daily_target` a computed property based on `target_total` and `total_days`
- [ ] Calculation formula:
  - `daily_target = ceil(target_total / total_days)` for days 1 through (total_days - 1)
  - `last_day_target = target_total - daily_target * (total_days - 1)`
  - Example: 1000 total, 30 days → daily_target = 34, last day = 14
- [ ] Add computed property method `get_daily_target(day_number: int)` that returns:
  - `ceil(target_total / total_days)` for days 1 to (total_days - 1)
  - `target_total - ceil(target_total / total_days) * (total_days - 1)` for the last day
- [ ] Update database migration to remove `daily_target` column
- [ ] Update all code that reads/writes `daily_target` to use computed value
- [ ] Update `calculate_expected_progress()` function to use computed daily_target
- [ ] Update `calculate_status_and_deficit()` function to use computed daily_target
- [ ] Update API models (`ExerciseChallengeOut`, `ExerciseChallengeCreate`, `ExerciseChallengeUpdate`) to:
  - Remove `daily_target` from required/optional fields in create/update
  - Add `daily_target` as computed/read-only field in response models
- [ ] Update `ExerciseStatsOut` to compute `daily_target` dynamically
- [ ] Update LLM challenge parsing to accept either `target_total` or `daily_target` (or both):
  - If only `target_total` provided: calculate `daily_target = ceil(target_total / total_days)`
  - If only `daily_target` provided: calculate `target_total = daily_target * total_days`
  - If both provided: validate they're consistent (within rounding tolerance), use `target_total` as source of truth if mismatch
  - This allows LLM to provide whichever is more natural from user input (e.g., "50 pushups daily" vs "2000 reps total")
- [ ] Update Telegram commands and responses to use computed `daily_target`
- [ ] Update all services (`src/api/services.py`, `app/services/workout_service.py`) to compute daily_target
- [ ] Update completion logic to handle last day correctly (use `get_daily_target(day_number)`)
- [ ] Add validation: ensure `target_total > 0` and `total_days > 0`
- [ ] Add edge case handling: if `target_total < total_days`, ensure last day doesn't go negative
- [ ] Update all unit tests to use computed `daily_target` instead of stored value
- [ ] Add tests for `get_daily_target()` method with various scenarios:
  - Divisible totals (e.g., 900 total, 30 days → 30 per day)
  - Non-divisible totals (e.g., 1000 total, 30 days → 34 per day, last day 14)
  - Edge cases (small totals, single day challenges)
- [ ] Update integration tests in `tests/api/test_challenges.py`
- [ ] Update documentation (RULES.md) to reflect new calculation approach
- [ ] Create migration script to handle existing data (compute and validate before removing column)
- [ ] Add API endpoint tests to verify computed `daily_target` in responses

### Motivational Insights
- [ ] Create weekly aggregation function in `src/api/services.py`
- [ ] Implement OpenAI prompt for personalized summaries
- [ ] Create `/api/v1/insights/weekly` endpoint
- [ ] Add weekly cron job in `app/routers/admin.py`
- [ ] Add Telegram command `/recap [week]`
- [ ] Add unit tests

---

## Next Phase (High Impact, Medium Effort)

### Multi-User Support (Feature 0010)
**Branch:** `feat/0010-multi-user-phase-1-3`

#### Phase 1 - Data Layer ✅ COMPLETE
- [x] Design database schema (AppUser, UserSettings tables)
- [x] Add `AppUser` table (telegram_user_id, username, first_name, timezone, status, created_at, approved_at)
- [x] Add `UserSettings` table (1:1 with AppUser, telegram_chat_id, is_reminder_active, idempotency tracking)
- [x] Add `user_id` foreign key to ExerciseType, ExerciseChallenge, ExerciseLog, UserStats
- [x] Update unique constraints (ExerciseType(user, name), UserStats(user, exercise_type))
- [x] Create Django migrations and backfill script
- [x] Update Django admin with user model registration and filtering

#### Phase 2 - Repository Layer ✅ COMPLETE
- [x] Create AppUserRepository (CRUD, approve, reject, get_by_telegram_user_id)
- [x] Create UserSettingsRepository (per-user settings, idempotency tracking)
- [x] Update all repository methods with optional user_id parameter
- [x] Add ownership verification in get_by_id/delete operations
- [x] Maintain backward compatibility (user_id optional, defaults to None)

#### Phase 3 - REST API ✅ COMPLETE
- [x] Add Pydantic models (UserOut, UserCreate, UserUpdate, UserSettings*)
- [x] Create get_current_user dependency (X-Telegram-User-Id header validation)
- [x] Create `/api/v1/users` router with endpoints:
  - [x] POST /users (register, auto-pending)
  - [x] GET /users/me (profile + settings)
  - [x] PATCH /users/me (update profile)
  - [x] GET/PATCH /users/me/settings (settings management)
  - [x] GET /users, POST /users/{id}/approve|reject (admin)
- [x] Register router in app/main.py
- [x] Add OpenAPI documentation tags
- [x] Update RULES.md with comprehensive architecture section
- [x] All 174 tests pass, backward compatibility maintained

#### Phase 4 - Telegram Registration Flow ⏳ TODO
- [ ] Extract telegram_user_id in webhook (app/routers/telegram.py)
- [ ] Auto-register new users with pending status
- [ ] Create approval/rejection command handlers (/approve, /reject)
- [ ] Notify users on approval/rejection
- [ ] Add SUPERUSER_TELEGRAM_IDS configuration
- [ ] Integrate registration gating in workout_service.py

#### Phase 5 - User-Scoped Operations ⏳ TODO
- [ ] Thread user_id through all API services (src/api/services.py)
- [ ] Update all routers to use get_current_user dependency
- [ ] Make stats calculations user-scoped
- [ ] Make log operations user-scoped
- [ ] Update reminder scheduler for per-user iteration
- [ ] Update reminder idempotency (per-user, not singleton)

#### Phase 6 - Testing & Documentation ⏳ TODO
- [ ] Add user fixtures to tests/api/conftest.py
- [ ] Create multi-user isolation tests
- [ ] Add integration tests for approval flow
- [ ] Update existing tests to use user context
- [ ] Update README.md with multi-user setup instructions
- [ ] Update docs/features/0010_REVIEW.md with completion report
- [ ] Document X-Telegram-User-Id header usage in docs

### Leaderboards
- [ ] Create `/api/v1/leaderboards` endpoint with filters
- [ ] Implement query logic for rankings (total reps, streaks, challenges)
- [ ] Add caching layer (5-15 minute TTL)
- [ ] Support multiple leaderboard types (all-time, monthly, challenge-specific)
- [ ] Add Telegram command `/leaderboard [exercise] [period]`
- [ ] Add unit tests

### Achievements & Badges
- [ ] Add `achievements` table (id, name, description, icon, criteria_type, criteria_value)
- [ ] Add `user_achievements` table (user_id, achievement_id, earned_at)
- [ ] Create achievement checking logic
- [ ] Create `/api/v1/achievements` endpoints (GET available, GET earned)
- [ ] Seed database with initial achievements
- [ ] Implement achievement unlock notifications in Telegram
- [ ] Add unit tests

### User Preferences & Settings
- [ ] Add settings JSON column to `users` table
- [ ] Create `/api/v1/users/{user_id}/settings` endpoints (GET, PATCH)
- [ ] Add Telegram commands (`/settings`, `/timezone`, `/notifications`)
- [ ] Use settings in workout parsing and formatting
- [ ] Add unit tests

---

## Long-Term Features (High Impact, High Effort)

### Web Dashboard
- [ ] Choose frontend framework (React/Vue or Jinja2 templates)
- [ ] Design authentication strategy (Telegram login widget, JWT)
- [ ] Create frontend project structure
- [ ] Implement pages: Dashboard, Challenges, Logs, Stats, Profile, Settings
- [ ] Add charts and visualizations (Chart.js/Recharts)
- [ ] Integrate with existing REST API
- [ ] Add authentication endpoints in `src/api/routers/auth.py`
- [ ] Deploy frontend (separate or integrated with FastAPI)
- [ ] Add end-to-end tests

### Team Challenges
- [ ] Add `teams` table (id, name, created_by, created_at)
- [ ] Add `team_members` table (team_id, user_id, joined_at, role)
- [ ] Add `team_challenges` table
- [ ] Create `/api/v1/teams` CRUD endpoints
- [ ] Implement team stats aggregation
- [ ] Add Telegram commands (`/team create`, `/team join`, `/team stats`)
- [ ] Add unit tests

### Nutrition Tracking
- [ ] Add `nutrition_logs` table (user_id, date, meal_type, food_description, calories, protein, carbs, fat)
- [ ] Research nutrition API integration (USDA FoodData, Nutritionix)
- [ ] Enhance OpenAI prompt for food parsing
- [ ] Create `/api/v1/nutrition` endpoints
- [ ] Add Telegram parsing for meal descriptions
- [ ] Add `/nutrition today` command
- [ ] Add unit tests

### Fitness Device Integration
- [ ] Research OAuth for Strava, Apple Health, Fitbit
- [ ] Add `integrations` table (user_id, platform, access_token, refresh_token, expires_at)
- [ ] Create `/api/v1/integrations` endpoints
- [ ] Implement OAuth flow for each platform
- [ ] Create background sync job
- [ ] Map external activities to internal exercises
- [ ] Add token encryption
- [ ] Add unit tests

---

## Additional Features (Consider Based on Feedback)

### Workout Templates
- [ ] Add `workout_templates` table (id, user_id, name, description, is_public)
- [ ] Add `template_exercises` table (template_id, exercise_type_id, target_count, order)
- [ ] Create `/api/v1/templates` CRUD endpoints
- [ ] Add Telegram commands (`/template create`, `/template log <name>`)
- [ ] Enhance AI parsing to recognize template names
- [ ] Add unit tests

### Data Export & Visualization
- [ ] Create `/api/v1/exports/logs` endpoint (CSV, JSON formats)
- [ ] Implement CSV generation (pandas or csv library)
- [ ] Add chart generation (matplotlib/plotly)
- [ ] Set up cloud storage for charts (DigitalOcean Spaces)
- [ ] Add Telegram command `/export [format]`
- [ ] Add unit tests

### Rest Day Tracking
- [ ] Add `rest_days` table (user_id, date, reason)
- [ ] Create `/api/v1/rest-days` endpoints
- [ ] Add Telegram command `/rest [reason]`
- [ ] Show rest days in calendar views
- [ ] Factor into streak calculations (optional setting)
- [ ] Add unit tests

### Challenge Invitations & Sharing
- [ ] Add `challenge_invites` table (id, challenge_id, invite_code, created_by, max_uses, expires_at)
- [ ] Create `/api/v1/challenges/{id}/invites` endpoints
- [ ] Add `/start <invite_code>` handler in Telegram
- [ ] Track invite usage and attribution
- [ ] Add unit tests

### Scheduled Workouts & Reminders
- [ ] Add `scheduled_workouts` table (user_id, template_id, scheduled_time, recurrence_pattern, timezone)
- [ ] Create background job for sending reminders
- [ ] Create `/api/v1/schedules` CRUD endpoints
- [ ] Add Telegram commands (`/remind`, `/schedule list`)
- [ ] Support recurrence patterns
- [ ] Add unit tests

### Points & Levels System
- [ ] Add `user_progress` table (user_id, total_points, current_level, points_to_next_level)
- [ ] Define point award rules
- [ ] Implement level calculation (exponential curve)
- [ ] Update points on log creation
- [ ] Create `/api/v1/stats/progress` endpoint
- [ ] Show level in Telegram profile
- [ ] Add unit tests

### Webhooks for Custom Integrations
- [ ] Add `webhooks` table (user_id, url, secret, events, is_active)
- [ ] Create `/api/v1/webhooks` CRUD endpoints
- [ ] Implement webhook delivery system
- [ ] Add HMAC signature verification
- [ ] Add retry logic with exponential backoff
- [ ] Log delivery status
- [ ] Add unit tests

### User Analytics Dashboard (Admin)
- [ ] Create `/api/v1/admin/analytics` endpoint
- [ ] Implement metrics: DAU, total logs, retention rate
- [ ] Add admin web UI or export to Google Sheets
- [ ] Add unit tests

### Automated Challenge Rotation
- [ ] Add `challenge_templates` table
- [ ] Create cron job for challenge generation
- [ ] Create `/api/v1/admin/challenge-templates` endpoints
- [ ] Send Telegram announcements for new challenges
- [ ] Add unit tests

---

## Infrastructure & DevOps

- [ ] Set up Redis for caching (leaderboards, analytics)
- [ ] Add rate limiting middleware to API endpoints
- [ ] Implement background job queue (Celery or similar)
- [ ] Add database indexes for performance optimization
- [ ] Set up monitoring and alerting (Sentry, DataDog)
- [ ] Add load testing
- [ ] Document API with more examples
- [ ] Create user documentation/help guide

---

## Notes

- Follow REST API conventions from RULES.md for all features
- All POST/PATCH/DELETE endpoints require API key authentication
- Add Pydantic models for all request/response bodies
- Write unit tests with Supabase mocking
- Update OpenAPI documentation for all endpoints
- Test manually in development before committing
- Update RULES.md with new patterns and lessons learned

---

**Last Updated:** 2026-01-19
**Current Work:** Feature 0010 Phases 1-3 complete (branch: feat/0010-multi-user-phase-1-3)
**Next Phase:** Phase 4 - Telegram Registration Flow
