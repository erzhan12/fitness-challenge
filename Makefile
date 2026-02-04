.PHONY: test lint api dev ngrok

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check .
	uv run ruff format --check .

api:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

dev:
	./scripts/start_webhook_dev.sh

ngrok:
	ngrok http 8001
