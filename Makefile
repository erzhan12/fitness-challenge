.PHONY: test lint api

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check .
	uv run ruff format --check .

api:
	uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

