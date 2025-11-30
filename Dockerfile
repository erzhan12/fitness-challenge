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

# Create a non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy the virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY ./app ./app

# Add virtualenv to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user
USER appuser

# Expose port (8001 to avoid conflicts with other services)
EXPOSE 8001

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
