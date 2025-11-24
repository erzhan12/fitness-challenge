.PHONY: test lint

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check .
	uv run ruff format --check .

