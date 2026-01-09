i# Supabase to Django ORM Migration Status

**Date:** 2026-01-09
**Migration Plan:** docs/features/0007_PLAN.md
**Target Database:** SQLite (data/db.sqlite3)

---

## ✅ Completed (Phases 1-6)

### Phase 1: Django Setup & Models (100% Complete)

#### ✅ Dependencies Added
- **File:** `pyproject.toml`
- Added `django>=5.1` and `asgiref>=3.8`
- Kept `supabase>=2.24.0` for data migration

#### ✅ Django Configuration Created
- **File:** `src/core/__init__.py`
  - Created `setup_django()` function
  - Handles Django initialization for FastAPI integration

- **File:** `src/core/settings.py`
  - Minimal Django settings for ORM-only usage
  - SQLite database at `data/db.sqlite3`
  - Timezone: `Asia/Almaty` (configurable via TZ env var)
  - Single app: `src.core`

#### ✅ Django Models Created
- **File:** `src/core/models.py` (91 lines)
- **Models:**
  - `ExerciseType` - Exercise definitions with aliases, emoji, unit
  - `ExerciseChallenge` - Time-bounded challenges with targets
  - `ExerciseLog` - Individual workout entries with stats
  - `UserStats` - Aggregated all-time statistics
- **Features:**
  - Proper foreign keys with CASCADE/SET_NULL
  - JSONField for aliases (SQLite compatible)
  - Custom `__str__` methods for admin readability
  - `db_table` meta to preserve existing table names

#### ✅ Management Command Setup
- **File:** `manage.py`
- Standard Django management script
- Executable permissions set
- Ready for `makemigrations`, `migrate`, etc.

---

### Phase 2: Repository Pattern (100% Complete)

#### ✅ Repository Classes Created
- **File:** `src/core/repositories.py` (331 lines)
- **Pattern:** Async wrappers using `sync_to_async`
- **Repositories:**
  1. **ExerciseTypeRepository**
     - `get_all(is_active)` - List with filtering
     - `get_by_id(id)` - Single lookup
     - `get_by_name(name)` - Name-based lookup
     - `create(data)` - Insert new
     - `update(id, data)` - Partial update
     - `get_by_ids(ids)` - Bulk lookup

  2. **ExerciseChallengeRepository**
     - `get_all(filters)` - List with filters (exercise_type_id, is_active, is_default)
     - `get_by_id(id)` - Single lookup
     - `get_active_for_type(exercise_type_id, target_date)` - Find active challenge for date
     - `get_current_active(target_date)` - All active challenges for date
     - `create(data)` - Insert new
     - `update(id, data)` - Partial update

  3. **ExerciseLogRepository**
     - `get_all(filters, limit, offset)` - Paginated list with filters
     - `get_by_id(id)` - Single lookup with relations
     - `get_cumulative_count(exercise_type_id, challenge_id, up_to_date)` - Sum aggregation
     - `get_today_count(exercise_type_id, date, challenge_id)` - Daily sum
     - `create(data)` - Insert new log
     - `delete(id)` - Remove log
     - `get_last_log(exercise_type_id)` - Most recent entry

  4. **UserStatsRepository**
     - `get_all()` - All stats with exercise_type relation
     - `get_by_exercise_type(exercise_type_id)` - Single lookup
     - `get_or_create(exercise_type_id)` - Upsert pattern
     - `update(id, data)` - Partial update
     - `increment_total(exercise_type_id, count, log_date)` - Atomic increment
     - `decrement_total(exercise_type_id, count)` - Atomic decrement

- **Global Singletons:**
  ```python
  exercise_type_repo = ExerciseTypeRepository()
  challenge_repo = ExerciseChallengeRepository()
  log_repo = ExerciseLogRepository()
  user_stats_repo = UserStatsRepository()
  ```

---

### Phase 3: Service Layer Migration (100% Complete)

#### ✅ API Services Rewritten
- **File:** `src/api/services.py` (599 lines, down from 770)
- **Changes:**
  - Removed all `get_supabase()` calls
  - Imported repository singletons
  - All functions now `async`
  - Added `_model_to_dict()` helper for Django model -> dict conversion
  - Preserved all business logic (stats computation, deficit calculation, etc.)

- **Migrated Functions (27 total):**

  **Exercise Types:**
  - `list_exercise_types()` ✅
  - `get_exercise_type()` ✅
  - `create_exercise_type()` ✅
  - `update_exercise_type()` ✅

  **Challenges:**
  - `list_challenges()` ✅
  - `get_challenge()` ✅
  - `get_active_challenge_for_type()` ✅
  - `list_current_active_challenges()` ✅
  - `create_challenge()` ✅
  - `update_challenge()` ✅
  - `get_ordered_challenges()` ✅ (pure logic, no DB)
  - `_enrich_challenge()` ✅ (helper)

  **Stats:**
  - `compute_exercise_stats()` ✅
  - `get_all_exercise_stats()` ✅
  - `calculate_expected_progress()` ✅ (pure logic)
  - `calculate_status_and_deficit()` ✅ (pure logic)

  **Logs:**
  - `list_logs()` ✅
  - `get_log()` ✅
  - `create_log()` ✅
  - `delete_log()` ✅

  **User Stats:**
  - `list_user_stats()` ✅
  - `get_stats_summary()` ✅

---

### Phase 4: Application Integration (100% Complete)

#### ✅ FastAPI Startup Hook Added
- **File:** `app/main.py`
- Added `@app.on_event("startup")` decorator
- Calls `setup_django()` on application start
- Django ORM initialized before any requests

#### ✅ Dependencies Updated
- **File:** `app/dependencies.py` - **COMPLETED**
- Kept `get_supabase()` for migration script
- Added repository getters:
  - `get_exercise_type_repo()`
  - `get_challenge_repo()`
  - `get_log_repo()`
  - `get_user_stats_repo()`

#### ✅ API Routers Updated
- **Files:** All 5 router files - **COMPLETED**
  - `src/api/routers/exercises.py` - Added `await` to 4 service calls
  - `src/api/routers/challenges.py` - Added `await` to 5 service calls
  - `src/api/routers/logs.py` - Added `await` to 5 service calls
  - `src/api/routers/stats.py` - Added `await` to 3 service calls
  - `src/api/routers/workouts.py` - Added `await` to 2 service calls
- **Total:** 19 `await` keywords added

#### ✅ Telegram Service Updated
- **File:** `app/services/workout_service.py` - **COMPLETED**
- Removed all Supabase (`get_supabase()`) usage
- Uses Django repositories for:
  - Exercise type lookup (`exercise_type_repo`)
  - Active challenges (`list_current_active_challenges`)
  - Log create/delete (`log_repo`)
  - Stats updates (`user_stats_repo`)
- Updated async flow to `await` the migrated service functions (`compute_exercise_stats`, `list_current_active_challenges`)
- Adds a small `_ensure_orm()` guard to initialize Django when invoked outside FastAPI startup

---

### Phase 5: Test Migration (100% Complete)

#### ✅ Test Fixtures Updated
- **File:** `tests/api/conftest.py` - **COMPLETED**
- Removed Supabase mocking helpers (`create_mock_query`, `patch_supabase`)
- Added `mock_repos` fixture (AsyncMock-based) for repository instances
- Added small model factory helpers for returning Django model instances without hitting the DB

#### ✅ API Tests Updated
- **Files:** `tests/api/test_*.py` (6 files) - **COMPLETED**
- Removed all `get_supabase()` patching
- Updated to set repository return values and (where useful) patch `compute_exercise_stats` with `AsyncMock`

#### ✅ Router Async Fixes (Required for Tests)
- **File:** `src/api/routers/logs.py` - Fixed missing `await` in `delete_single_log()`
- **File:** `src/api/routers/workouts.py` - Fixed missing `await` for `list_current_active_challenges()`

---

### Phase 6: Data Migration Script

#### ✅ Migration Script Created
- **File:** `scripts/migrate_data.py` - **COMPLETED**
- Supports batched `exercise_logs` migration (`--batch-size`) and optional verification (`--no-verify`)
- Loads `SUPABASE_URL` / `SUPABASE_KEY` from `.env` (via python-dotenv) and initializes Django ORM

---

## 🟡 In Progress (Phase 7)

---

### Phase 7: Database Setup

#### ✅ Django Migrations Created (Files Added)
- **Files:** `src/core/migrations/__init__.py`, `src/core/migrations/0001_initial.py`
- **Note:** `makemigrations` was not executed here; migration file was created to match `src/core/models.py`.

#### ⏳ Database Not Created (Command Not Run)
- **Command:** `uv run python manage.py migrate`
- **Will create:** `data/db.sqlite3` with schema

#### ✅ .gitignore Updated
- **File:** `.gitignore`
- Added `data/db.sqlite3`

---

## 📊 Overall Progress

### By Phase
- ✅ **Phase 1:** Django Setup & Models (100%)
- ✅ **Phase 2:** Repository Pattern (100%)
- ✅ **Phase 3:** Service Layer Migration (100%)
- ✅ **Phase 4:** Application Integration (100%)
- ✅ **Phase 5:** Test Migration (100%)
- ✅ **Phase 6:** Data Migration Script (100%)
- 🟡 **Phase 7:** Database Setup (partial)

### By File Count
- **Completed:** 19 files
- **Partially complete:** 0 files
- **Not started:** 0 files
- **Total:** 19 files

### By Code Lines
- **Written:** ~1,100 lines
- **Modified:** ~600 lines
- **Estimated remaining:** ~400 lines

---

## 🚧 Critical Blockers

### Cannot Run Application Yet
The application will crash if started because:

1. **Database tables do not exist yet**
   - Django migrations have not been applied (`migrate`)
   - Any ORM query will fail until Phase 7 is completed

### Cannot Migrate Data Yet
Data migration cannot run yet because:
- Need to run `uv run python manage.py migrate` first (create tables)
- Need Supabase credentials in `.env` (`SUPABASE_URL`, `SUPABASE_KEY`)

---

## 🎯 Next Steps (Priority Order)

### High Priority (Critical Path)
1. **Run Django migrations**
   ```bash
   uv run python manage.py makemigrations
   uv run python manage.py migrate
   ```

2. **Run data migration script**
   ```bash
   uv run python scripts/migrate_data.py
   ```

### Medium Priority (Required for Full Migration)
3. **Run data migration**
   - Requires Supabase credentials
   - One-time operation

### Low Priority (Nice to Have)
4. **Update test fixtures and tests**
   - Can delay if not running tests immediately

5. **Update .gitignore**
   - Add `data/db.sqlite3`

---

## 🔍 Testing Strategy

### Before Full Migration
1. **Create empty database:** `python manage.py migrate`
2. **Test with empty DB:** Start app, try API calls (will have no data)
3. **Manually insert test data:** Use Django shell or API

### After Data Migration
1. **Verify counts:** Compare Supabase vs SQLite record counts
2. **Spot check data:** Compare specific records
3. **Test Telegram bot:** Send test messages
4. **Test API endpoints:** Try all CRUD operations
5. **Run test suite:** `pytest tests/`

---

## 📝 Rollback Plan

If migration fails:
1. **Code rollback:** `git reset --hard HEAD` (or revert commits)
2. **No DB cleanup needed:** SQLite file can be deleted
3. **Supabase still works:** Client still in `pyproject.toml`
4. **Zero downtime risk:** Can test locally before deploying

---

## 💡 Notes

### Architecture Decisions
- **Why SQLite?** Simpler for local/single-server deployment, no external DB needed
- **Why repositories?** Matches habit-reward pattern, clean abstraction, easy to test
- **Why async?** FastAPI is async-first, repositories use `sync_to_async` for Django ORM
- **Why not remove Supabase?** Needed for one-time data migration

### Performance Considerations
- **SQLite limitations:** Single writer, but sufficient for this use case
- **File locking:** SQLite uses file-level locking (acceptable for low concurrency)
- **Backup strategy:** Simple file copy of `data/db.sqlite3`

### Development Tips
- **Django shell:** `python manage.py shell` for interactive DB queries
- **Reset DB:** Delete `data/db.sqlite3` and re-run migrations
- **Inspect schema:** Use `python manage.py dbshell` or SQLite browser

---

## 📚 References

- **Migration Plan:** `docs/features/0007_PLAN.md`
- **Reference Repo:** https://github.com/erzhan12/habit-reward
- **Django ORM Docs:** https://docs.djangoproject.com/en/5.1/topics/db/
- **Supabase Docs:** https://supabase.com/docs (for data migration)
