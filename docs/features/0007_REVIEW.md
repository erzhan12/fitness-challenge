# Code Review: Feature 0007 - Migrate from Supabase to Django ORM

**Review Date:** 2026-01-09  
**Reviewer:** Codex CLI (GPT-5.2)  
**Plan Reference:** `docs/features/0007_PLAN.md`

---

## Executive Summary

⚠️ **NEEDS CHANGES** — The core migration (Django ORM models + repositories + service layer + migration script + test updates) is largely implemented, but there is one high-impact gap:

1. **Supabase is still required at runtime** via `app/config.py` and is instantiated eagerly in `app/dependencies.py`, which undermines “Supabase only for one-time migration”.

Until this is addressed, deployments/environments without Supabase credentials (or CI without secrets) are likely to break at import/startup time.

---

## 1. Plan Adherence

### ✅ Implemented (Matches Plan)

| Area | Status | Evidence |
|------|--------|----------|
| Django “ORM-only” setup | ✅ | `src/core/__init__.py`, `src/core/settings.py` |
| Django models + initial migration | ✅ | `src/core/models.py`, `src/core/migrations/0001_initial.py` |
| Repository layer (async via `sync_to_async`) | ✅ | `src/core/repositories.py` |
| Service migration away from Supabase | ✅ | `src/api/services.py` uses repositories + async |
| FastAPI startup initializes Django | ✅ | `app/main.py` calls `setup_django()` |
| Data migration script | ✅ | `scripts/migrate_data.py` |
| API tests migrated to repo mocking | ✅ | `tests/api/conftest.py`, `tests/api/test_*.py` |
| Local DB ignored | ✅ | `.gitignore` includes `data/db.sqlite3` |

### ⚠️ Deviations / Incomplete vs Plan Intent

| Area | Concern | Why it matters |
|------|---------|----------------|
| “Keep Supabase only for migration” | `app/config.py` still *requires* `SUPABASE_URL`/`SUPABASE_KEY`, and `app/dependencies.py` instantiates Supabase client at import-time | App startup can fail in environments that don’t (and shouldn’t) have Supabase secrets |
| Dependency injection via `app/dependencies.py` | Repository getters exist, but routers/services largely import singletons directly | Not wrong, but reduces testability/replaceability compared to DI plan framing |

---

## 2. High-Impact Issues (Bugs / Reliability)

### 2.1 Supabase client initialized eagerly (runtime dependency)

- **File:** `app/dependencies.py`  
  The module imports and constructs a Supabase client immediately:
  - `supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)`
- **File:** `app/config.py`  
  `Settings` requires `SUPABASE_URL` and `SUPABASE_KEY`.

**Impact**
- Breaks “SQLite-only runtime”: the app can crash on import/startup if Supabase env vars are absent.
- Makes local/dev/test environments unnecessarily require Supabase secrets.

**Recommendation**
- Make Supabase settings optional (or split into separate “migration-only settings”), and lazily construct the client only inside `scripts/migrate_data.py` (or a dedicated migration-only helper).

---

## 3. Data Alignment / Serialization Risks

### ✅ Good: FK serialization uses `*_id`

- **File:** `src/api/services.py`  
  `_model_to_dict()` uses `field.attname`, which correctly serializes relations as `exercise_type_id`, `challenge_id`, etc., avoiding the classic Django pitfall of embedding related objects.

### ⚠️ Mixed date/datetime representations across layers

- `_model_to_dict()` serializes `date`/`datetime` to ISO strings.
- Pydantic models in `src/api/models.py` declare `dt.date` and `dt.datetime`.

This usually works (Pydantic parses ISO strings), but be careful about:
- **Timezone awareness**: if a naive `datetime` slips in, API responses may become ambiguous.
- **Consistency**: some internal flows (Telegram) pass dicts with `start_date`/`end_date` as strings, others may be native `date` objects; `compute_exercise_stats()` partially guards this, but the pattern is spread across multiple helpers.

**Recommendation**
- Prefer passing native Python types internally (date/datetime) and only serialize at the boundary (FastAPI response). If keeping `_model_to_dict()`, consider not converting types there and letting Pydantic handle `from_attributes=True` directly.

---

## 4. Repository Layer Review

### ✅ Strengths

- Clear, thin repositories with predictable query shapes.
- Use of `select_related()` in challenge/log paths to avoid N+1 for common cases.
- Aggregations (`Sum`) for cumulative/today counts are straightforward.

### ⚠️ Minor issues

- **File:** `src/core/repositories.py`
  - Unused import: `Q` (can be removed).
  - `ExerciseChallengeRepository.get_active_for_type()` wraps `.filter(...).first()` in a `try/except DoesNotExist`, but `.first()` won’t raise `DoesNotExist`.
  - `UserStatsRepository.increment_total()` / `decrement_total()` are not truly “atomic” under concurrency (read-modify-write). It’s probably fine for a single-user bot, but if you expect concurrent writes, prefer `F()` expressions.

---

## 5. Service Layer Review (`src/api/services.py`)

### ✅ Strengths

- Major reduction in direct DB coupling; logic now composes repository calls.
- `_model_to_dict()` avoids common Django serialization issues for foreign keys.
- `compute_exercise_stats()` is now shareable across REST + Telegram paths.

### ⚠️ Behavioral/consistency concerns

- **User stats `last_logged_date`**: ✅ Fixed by centralizing the recompute logic in `UserStatsRepository.sync_last_logged_date()` and calling it from both API and Telegram delete flows.

### ⚠️ Scalability footgun in summary stats

- **Function:** `get_stats_summary()` in `src/api/services.py`  
  Uses `await log_repo.get_all(limit=10000)` to compute distinct active days.

**Impact**
- Inaccurate results beyond 10k logs; also a potentially expensive in-memory set build.

**Recommendation**
- Add a repository method to compute distinct dates at the DB level (or page through results deterministically).

---

## 6. Tests Review

### ✅ API tests (good shape)

- **Files:** `tests/api/test_*.py` + `tests/api/conftest.py`  
  - Tests are isolated (repository calls are mocked).
  - Naming is clear and covers happy paths + common errors (401/403/404/422).
  - `AsyncMock` usage correctly matches awaited service calls.

### ✅ Service tests (migrated)

- **File:** `tests/services/test_workout_service.py`  
  - Updated to mock repository calls (`log_repo.*`, `user_stats_repo.*`) and assert awaited interactions and formatted message outputs for `get_recent_logs()`, `delete_log_entry()`, and `undo_last_log()`.
  - Uses `asyncio.run(...)` so it runs without requiring `pytest-asyncio`.

---

## 7. Recommended Next Changes (Priority Order)

1. **Decouple runtime from Supabase**: make Supabase settings optional and remove eager client construction from `app/dependencies.py`.
