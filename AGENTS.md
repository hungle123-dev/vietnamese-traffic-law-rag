# Agent Instructions

## Package Manager

- Use **uv** for dependencies and commands.
- Read the relevant file in `docs/` before changing behavior.
- Keep the v1 scope to Vietnamese traffic-law ingestion, retrieval and grounded QA.

## Quality Gates

```text
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -q
```

## File-Scoped Commands

| Task | Command |
|---|---|
| Test one file | `uv run pytest -q tests/path/test_file.py` |
| Lint one file | `uv run ruff check path/to/file.py` |
| Format one file | `uv run ruff format path/to/file.py` |
| Typecheck | `uv run mypy src/traffic_legal_qa` |

## Key Conventions

- Use Python type hints, Pydantic models at boundaries, and small single-purpose functions.
- Keep API/routes, domain logic, storage and parsing separate.
- Legal hierarchy parsing is deterministic; do not use an LLM to invent article IDs or validity.
- Every legal unit keeps a stable `unit_id`, parent relationship and source/snapshot metadata.
- Do not add a dependency or abstraction without a current use case.
- Do not implement Agentic RAG, UI or extra databases unless the current task explicitly requires it.
- Add or update tests with every behavior change; test behavior, not implementation details.
- Never commit secrets, raw personal data, generated indexes or local `.env` files.
