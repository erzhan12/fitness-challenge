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

# Install dependencies (including dev/test deps)
RUN uv sync --frozen --no-install-project

# Copy application code
COPY . .

# Run tests
# If tests fail, the build fails.
RUN uv run pytest

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

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
