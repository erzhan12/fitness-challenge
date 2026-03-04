# ruff: noqa: E402

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from a2wsgi import WSGIMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Configure Django ORM before importing modules that touch Django models.
from src.core import setup_django
setup_django()

# Import Django WSGI application for admin
from django.core.wsgi import get_wsgi_application
from django.conf import settings

from app.routers import telegram, admin

# Import API routers
from src.api.routers import exercises, challenges, logs, stats, workouts, settings as settings_router, users

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Module-level variable to track scheduler task
_scheduler_task: Optional[asyncio.Task] = None

# OpenAPI tags metadata
openapi_tags = [
    {
        "name": "Exercises",
        "description": "Manage exercise types - the different exercises that can be tracked.",
    },
    {
        "name": "Challenges",
        "description": "Manage fitness challenges - time-bounded goals for exercises.",
    },
    {
        "name": "Logs",
        "description": "Record and query exercise log entries.",
    },
    {
        "name": "Stats",
        "description": "View progress statistics and summaries.",
    },
    {
        "name": "Workouts",
        "description": "Parse workout messages into structured data.",
    },
    {
        "name": "Settings",
        "description": "Application settings and preferences.",
    },
    {
        "name": "Users",
        "description": "User registration, profile, and settings management.",
    },
    {
        "name": "Jobs",
        "description": "Internal job triggers (admin only).",
    },
    {
        "name": "Telegram",
        "description": "Telegram bot webhook (internal).",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    global _scheduler_task

    # Startup
    logger.info("Application starting up...")

    # Start scheduler (optionally gated by env var for testing/dev)
    if os.getenv("ENABLE_REMINDER_SCHEDULER", "true").lower() == "true":
        from app.services.reminder_scheduler import start_reminder_scheduler
        _scheduler_task = asyncio.create_task(start_reminder_scheduler())
        logger.info("Evening reminder scheduler started")
    else:
        logger.info("Reminder scheduler disabled via ENABLE_REMINDER_SCHEDULER=false")

    yield

    # Shutdown
    logger.info("Application shutting down...")
    if _scheduler_task is not None:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            logger.info("Scheduler task cancelled successfully")


app = FastAPI(
    lifespan=lifespan,
    title="Fitness Challenge API",
    description="""
A REST API for tracking fitness challenges and workout progress.

## Features

- **Exercise Types**: Define and manage different exercises (pushups, squats, etc.)
- **Challenges**: Create time-bounded fitness challenges with targets
- **Logs**: Record workout entries and track progress
- **Stats**: View detailed statistics and progress towards goals
- **Workouts**: AI-powered parsing of natural language workout messages

## Authentication

Protected endpoints require an API key via the `Authorization` header:
- `Authorization: Bearer <your-api-key>`
- `Authorization: <your-api-key>`

Read-only endpoints (GET) are accessible without authentication.
""",
    version="0.1.0",
    openapi_tags=openapi_tags,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# Rate limiter (keyed by remote IP)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Mount static files for Django admin FIRST (more specific route)
# This must come before mounting /admin so /admin/static/... requests are handled here
static_root = Path(settings.STATIC_ROOT)
if static_root.exists():
    app.mount("/admin/static", StaticFiles(directory=str(static_root)), name="static")

# Mount Django admin at /admin/ (less specific, catches everything else under /admin)
# This allows access to Django admin panel through FastAPI
django_wsgi = get_wsgi_application()
app.mount("/admin", WSGIMiddleware(django_wsgi))

# Include existing routers (Telegram bot & admin jobs)
app.include_router(telegram.router)
app.include_router(admin.router)

# Include REST API routers under /api/v1 prefix
app.include_router(exercises.router, prefix="/api/v1")
app.include_router(challenges.router, prefix="/api/v1")
app.include_router(logs.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")
app.include_router(workouts.router, prefix="/api/v1")
app.include_router(settings_router.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")


@app.get("/", tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


@app.get("/health/scheduler", tags=["Health"])
async def scheduler_health():
    from app.services import reminder_scheduler as scheduler

    last_heartbeat = scheduler.last_scheduler_heartbeat
    if last_heartbeat is None:
        return {"status": "not_started"}

    now = datetime.now(scheduler.TZ)
    age_seconds = (now - last_heartbeat).total_seconds()
    status = "healthy" if age_seconds <= 300 else "stale"
    return {
        "status": status,
        "last_heartbeat": last_heartbeat.isoformat(),
        "age_seconds": age_seconds,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
