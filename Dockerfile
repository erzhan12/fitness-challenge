FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Install system dependencies if needed (e.g. for psycopg2 or others, though asyncpg is pure python)
# RUN apt-get update && apt-get install -y --no-install-recommends ...

# Copy dependency definitions
COPY pyproject.toml uv.lock ./

# Sync dependencies
RUN uv sync --frozen --no-install-project

# Copy application code
COPY ./app ./app

# Expose port
EXPOSE 8000

# Run
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

