# STAGE 1: Builder & Tests
FROM python:3.12-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Install system dependencies if needed (e.g. git for some pip packages)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Copy dependency definitions
COPY pyproject.toml uv.lock ./

# Copy application code (needed for uv sync to install the project)
COPY . .

# Install dependencies and project (including test deps)
RUN uv sync --frozen --extra test

# Run tests
# If tests fail, the build fails.
# Set dummy environment variables for tests (actual values not needed as tests mock dependencies)
RUN TELEGRAM_BOT_TOKEN=test_token \
    TELEGRAM_SECRET_TOKEN=test_secret_token \
    LLM_API_KEY=test_llm_key \
    LLM_BASE_URL=https://api.test.com/v1 \
    LLM_MODEL=test-model \
    SUPABASE_URL=https://test.supabase.co \
    SUPABASE_KEY=test_supabase_key \
    ADMIN_API_KEY=test_admin_key \
    uv run pytest tests/ -v

# STAGE 2: Production
FROM python:3.12-slim-bookworm AS production

# Install system dependencies if needed (e.g. git for some pip packages)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Copy uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy dependency definitions
COPY pyproject.toml uv.lock ./

# Copy application code (needed for uv sync to install the project)
COPY ./app ./app
COPY ./src ./src
COPY ./manage.py ./manage.py
COPY ./deployment/scripts/entrypoint.sh ./entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Install only production dependencies (no test extras)
# uv sync will install the project itself since pyproject.toml is present
RUN uv sync --frozen

# Create a non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Change ownership of /app to appuser
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Add virtualenv to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Expose port (8001 to avoid conflicts with other services)
EXPOSE 8001

# Entrypoint runs migrations before starting the app
ENTRYPOINT ["/app/entrypoint.sh"]

# Run application using Python from venv directly
CMD ["/app/.venv/bin/python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
