import logging
from fastapi import FastAPI
from app.routers import telegram, admin

# Import API routers
from src.api.routers import exercises, challenges, logs, stats, workouts

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

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
        "name": "Jobs",
        "description": "Internal job triggers (admin only).",
    },
    {
        "name": "Telegram",
        "description": "Telegram bot webhook (internal).",
    },
]

app = FastAPI(
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

# Include existing routers (Telegram bot & admin jobs)
app.include_router(telegram.router)
app.include_router(admin.router)

# Include REST API routers under /api/v1 prefix
app.include_router(exercises.router, prefix="/api/v1")
app.include_router(challenges.router, prefix="/api/v1")
app.include_router(logs.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")
app.include_router(workouts.router, prefix="/api/v1")


@app.get("/", tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
