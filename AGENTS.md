# Agent Instructions

## Package Manager

- Use `uv`; install with `uv sync --all-groups`.

## Fast Checks

| Task | Command |
|---|---|
| Format | `uv run ruff format --check src tests` |
| Lint | `uv run ruff check src tests` |
| Type check | `uv run mypy src tests` |
| One test file | `uv run pytest tests/unit/test_parser.py` |
| All unit tests | `uv run pytest tests/unit` |
| Snapshot | `uv run traffic-legal-qa validate-snapshot --snapshot-id <id>` |
| Snapshot report | `uv run traffic-legal-qa report-snapshot --snapshot-id <id> --catalog <catalog>` |
| Rebuild parsed snapshot | `uv run traffic-legal-qa rebuild-snapshot --snapshot-id <id> --catalog <catalog>` |

## Ingestion Contract

- Ingest only a reviewed `document_id` from `data/catalog/`; never accept arbitrary URLs or search terms.
- Store exact raw bytes before validation; raw, receipt, normalized, parsed, manifest, and index artifacts stay out of Git.
- Do not mutate raw text. A correction needs literal text, exact match count, HTTPS primary-source evidence, and a reason in the catalog.
- A schema, identity, correction, parser, or validation failure must block promotion while retaining raw when available.
- Keep output deterministic for identical raw bytes, catalog, parser, and normalizer versions.

## Scope

- The implemented foundation is portal ingestion, artifacts, hierarchy parsing, catalog curation, and reports; graph, retrieval, QA, cache, and UI remain target phases.
- Do not scaffold a future service. Add a graph, retrieval, QA, cache, or UI module only in its documented phase with its contract and focused check.
- Update `docs/03-data-and-ingestion.md` and `docs/14-implementation-blueprint.md` when an artifact or pipeline contract changes.

## Commits

- Do not add `Co-Authored-By` lines.
