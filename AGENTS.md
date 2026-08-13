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
| Validate approved relations | `uv run traffic-legal-qa validate-relations --snapshot-id <id> --relation-artifact <file>` |
| Import graph | `uv run traffic-legal-qa import-graph --snapshot-id <id> [--relation-artifact <file>]` |
| Verify graph | `uv run traffic-legal-qa verify-graph --snapshot-id <id> [--relation-artifact <file>]` |

## Ingestion Contract

- Ingest only a reviewed `document_id` from `data/catalog/`; never accept arbitrary URLs or search terms.
- Store exact raw bytes before validation; raw, receipt, normalized, parsed, manifest, and index artifacts stay out of Git.
- Do not mutate raw text. A correction needs literal text, exact match count, HTTPS primary-source evidence, and a reason in the catalog.
- A schema, identity, correction, parser, or validation failure must block promotion while retaining raw when available.
- Keep output deterministic for identical raw bytes, catalog, parser, and normalizer versions.

## Scope

- The implemented foundation is portal ingestion, artifacts, hierarchy parsing, reports, structural Neo4j projection, and Phase 2B relation-artifact validation; retrieval, QA, cache, and UI remain target phases.
- `import-graph` and `verify-graph` require `NEO4J_PASSWORD`; start the pinned `compose.yaml` service first. An `AMENDS` edge requires an explicit approved relation artifact whose source, target, evidence, raw hash, URL, provenance, and reviewer all resolve.
- Do not scaffold a future service. Add retrieval, QA, cache, or UI only in its documented phase with its contract and focused check.
- Update `docs/03-data-and-ingestion.md` and `docs/14-implementation-blueprint.md` when an artifact or pipeline contract changes.

## Commits

- Do not add `Co-Authored-By` lines.
