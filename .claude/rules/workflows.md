# Development Workflows

## Run
```bash
make api               # FastAPI server on :8001 with reload
make dev               # Webhook dev mode (ngrok + server)
make ngrok             # ngrok tunnel to :8001
```

## Lint
```bash
make lint              # ruff check + ruff format --check
```

## Test
```bash
make test              # uv run pytest tests/ -v
uv run pytest tests/api/ -v   # API tests only
```