# Fitness Challenge Bot - TODO

Add SSH settings to PyCharm
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

### Motivational Insights
- [ ] Create weekly aggregation function in `src/api/services.py`
- [ ] Implement OpenAI prompt for personalized summaries
- [ ] Create `/api/v1/insights/weekly` endpoint
- [ ] Add weekly cron job in `app/routers/admin.py`
- [ ] Add Telegram command `/recap [week]`
- [ ] Add unit tests

---

## Next Phase (High Impact, Medium Effort)

### Multi-User Support
- [ ] Design database schema (users, user_settings tables)
- [ ] Add `users` table (telegram_user_id, username, first_name, timezone, created_at, settings)
- [ ] Add `user_id` foreign key to exercise_logs, exercise_challenges
- [ ] Create `/api/v1/users` endpoints (POST register, GET profile, PATCH update)
- [ ] Implement user registration flow in Telegram
- [ ] Update all stats calculations to be user-scoped
- [ ] Add user context to all API endpoints
- [ ] Create database migration scripts
- [ ] Add comprehensive unit tests
- [ ] Update existing tests to work with multi-user

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

**Last Updated:** 2025-12-10
