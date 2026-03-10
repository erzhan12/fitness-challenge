# Architecture Decisions

These are non-obvious conventions that can't be inferred from code alone.

**Package manager**: `uv` (not pip/poetry). Run everything via `uv run`.

**Framework**: FastAPI (`app/main.py`). Serves both Telegram webhook and REST API.

**Database**: Supabase. All DB ops go through `src/api/services.py`, never direct queries from handlers.

**REST API**: All new business logic MUST have a `/api/v1/` endpoint. See `.claude/CODE_RULES.md` for full convention.

**API Security**: POST/PATCH/DELETE require API key (`require_api_key` from `src/api/security.py`). GET endpoints are public.

**Telegram bot**: Webhook-based. Handlers in `app/routers/`, services in `app/services/`.

**Separation of concerns**:
- `src/api/` — HTTP/JSON-first, returns structured data
- `app/services/` — Can return HTML-formatted strings for Telegram
- Share domain logic via reusable helpers

## Environment Variables
- `TELEGRAM_BOT_TOKEN`, `SUPABASE_URL`, `SUPABASE_KEY`
- `API_KEY` (for REST API authentication)
- `OPENAI_API_KEY` (for LLM features)
- Optional: `WEBHOOK_URL`, `NGROK_AUTHTOKEN`