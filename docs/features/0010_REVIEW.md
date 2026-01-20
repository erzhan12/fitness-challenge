# Code Review: Feature 0010 - Multi-User Support

**Review Date:** 2026-01-19  
**Reviewer:** Codex CLI (GPT-5)  
**Plan Reference:** `docs/features/0010_PLAN.md`

---

## Executive Summary

NEEDS CHANGES - Phase 4 Telegram auto-registration is partially implemented, but the approval workflow is incomplete, and core API endpoints are still unscoped. This leaves cross-user data exposure risks and prevents the approval flow from functioning as described in the plan.

---

## Plan Adherence (Current State)

### Implemented
- Telegram webhook extracts user identity and passes it into the workout service (`app/routers/telegram.py`:30-61).
- Auto-registration creates `AppUser` records and `UserSettings` on first contact (`app/services/workout_service.py`:453-468).
- Admin commands `/approve` and `/reject` exist and update user status (`app/services/workout_service.py`:590-688).

### Gaps / Deviations
- API routes and services are still global; they don't require or thread `X-Telegram-User-Id` or `user_id` (`src/api/routers/exercises.py`:1-129, `src/api/services.py`:78-169). This contradicts Phase 3 requirements.
- Telegram webhook still writes to singleton `AppSettings.telegram_chat_id` instead of per-user `UserSettings` (`app/routers/telegram.py`:42-47).
- No superuser notification is sent on new registrations, despite the plan requiring an approval request message (`app/services/workout_service.py`:453-468).
- FK fields remain nullable after backfill; the plan calls for non-nullable `user_id` columns (`src/core/models.py`:50-98).

---

## High-Impact Issues

### 1) API endpoints are not user-scoped (cross-user data exposure)
- **Where:** `src/api/routers/exercises.py`:1-129, `src/api/services.py`:78-169 (also applies to other routers/services)
- **Issue:** Endpoints do not use `get_current_user`, and service methods do not accept `user_id`. This returns or mutates data across all users.
- **Impact:** Any caller can see or modify other users' records, violating the multi-user boundary in Phase 3.
- **Recommendation:** Require `X-Telegram-User-Id` (or equivalent) on all user-facing endpoints and pass `user_id` into repository calls.

### 2) Telegram webhook still persists a global chat ID
- **Where:** `app/routers/telegram.py`:42-47
- **Issue:** `app_settings_repo.update_chat_id` writes a singleton chat ID, overwriting the last sender.
- **Impact:** Reminders/notifications may be sent to the wrong user; a later user can hijack the global chat target.
- **Recommendation:** Stop writing to `AppSettings` in the webhook. Instead update per-user `UserSettings.telegram_chat_id` after resolving the user.

### 3) New registrations do not notify any superuser for approval
- **Where:** `app/services/workout_service.py`:453-468
- **Issue:** The plan requires sending an approval request to a superuser. The current flow only creates the user and returns a pending message.
- **Impact:** No one is alerted to approve; new users can remain stuck in "pending" indefinitely.
- **Recommendation:** On `created=True`, send a notification to all `SUPERUSER_TELEGRAM_IDS` with the user's ID and approval instructions.

### 4) `/status` is unreachable for pending/rejected users
- **Where:** `app/services/workout_service.py`:470-488 and `app/services/workout_service.py`:562-588
- **Issue:** The approval gate returns early for non-approved users before command handling. `/status` never runs for pending/rejected users.
- **Impact:** Users cannot check status as documented; pending users receive only the generic pending message.
- **Recommendation:** Handle `/status` before gating, or allow that command to bypass the approval check.

### 5) Existing users never refresh `telegram_chat_id`
- **Where:** `app/services/workout_service.py`:462-467
- **Issue:** `telegram_chat_id` is only set when a user is created. If an existing user registered via API (or the chat ID changes), settings remain empty/outdated.
- **Impact:** Approval notifications may not deliver, and reminders can't target the correct chat.
- **Recommendation:** Ensure `UserSettings.telegram_chat_id` is updated for every incoming message (with validation).

---

## Tests Review

### Missing Coverage
- No tests for Telegram registration gating, `/status`, or admin approval/rejection commands.
- No tests covering superuser notifications or chat_id persistence in `UserSettings`.
- No API tests for `/api/v1/users` registration/profile/update endpoints.

---

## Optional Cleanups

- Consider updating existing user fields (`username`, `first_name`) on subsequent Telegram messages to avoid stale data (`app/services/workout_service.py`:453-468).
