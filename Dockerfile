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

# Copy uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy dependency definitions
COPY pyproject.toml uv.lock ./

# Copy application code
COPY ./app ./app

# Install only production dependencies (no test extras)
RUN uv sync --frozen --no-dev

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

# Run application using uv run
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
