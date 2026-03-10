# TODO

Track current and upcoming work items here.

## In Progress

## Upcoming

- [ ] Add retry logic with exponential backoff for LLM calls (`app/services/openai_service.py`)
- [ ] Implement per-user rate limiting instead of per-IP for `/challenges/create-from-prompt`
- [ ] Add more parametrized tests for LLM challenge creation edge cases (boundary values, mixed valid/invalid fields)
- [ ] Consider Redis backend for distributed rate limiting (needed if deploying multiple instances)

## Done
