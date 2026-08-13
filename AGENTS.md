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
| Validate retrieval gold set | `uv run traffic-legal-qa validate-gold-set --snapshot-id <id> --gold-set <file>` |
| Import graph | `uv run traffic-legal-qa import-graph --snapshot-id <id> [--relation-artifact <file>]` |
| Verify graph | `uv run traffic-legal-qa verify-graph --snapshot-id <id> [--relation-artifact <file>]` |
| Build lexical index | `uv run traffic-legal-qa build-lexical-index --snapshot-id <id>` |
| Search R0 lexical | `uv run traffic-legal-qa search-lexical --snapshot-id <id> --query <query>` |
| Evaluate R0 | `uv run traffic-legal-qa evaluate-r0 --snapshot-id <id> --gold-set <file> --split dev` |
| Build R1 dense index | `uv run traffic-legal-qa build-dense-index --snapshot-id <id>` |
| Search R1 dense | `uv run traffic-legal-qa search-dense --snapshot-id <id> --query <query>` |
| Evaluate R1 | `uv run traffic-legal-qa evaluate-r1 --snapshot-id <id> --gold-set <file> --split dev` |

## Ingestion Contract

- Ingest only a reviewed `document_id` from `data/catalog/`; never accept arbitrary URLs or search terms.
- Store exact raw bytes before validation; raw, receipt, normalized, parsed, manifest, and index artifacts stay out of Git.
- Do not mutate raw text. A correction needs literal text, exact match count, HTTPS primary-source evidence, and a reason in the catalog.
- A schema, identity, correction, parser, or validation failure must block promotion while retaining raw when available.
- Keep output deterministic for identical raw bytes, catalog, parser, and normalizer versions.

## Scope

- The implemented foundation is portal ingestion, artifacts, hierarchy parsing, reports, structural Neo4j projection, Phase 2B relation-artifact validation, Phase 2C retrieval-gold-set validation, Phase 2D R0 exact-plus-lexical retrieval/evaluation, and Phase 2E R1 BKAI+PyVi dense retrieval/evaluation. Hybrid, QA, cache, and UI remain target phases.
- `import-graph`, `verify-graph`, `build-lexical-index`, `search-lexical`, `evaluate-r0`, `build-dense-index`, `search-dense`, and `evaluate-r1` require `NEO4J_PASSWORD`; start the pinned `compose.yaml` service first. Build each index explicitly before search or evaluation; query paths never create indexes. R1 requires an import from this code version so Article/Clause/Point have the `LegalUnit` label, and rejects embeddings from any other snapshot because Neo4j 5.26 cannot filter its vector index by snapshot. An `AMENDS` edge requires an explicit approved relation artifact whose source, target, evidence, raw hash, URL, provenance, and reviewer all resolve.
- Do not scaffold a future service. Add retrieval, QA, cache, or UI only in its documented phase with its contract and focused check.
- `data/gold/` is tracked. A gold-set row must resolve its document and provision IDs through `validate-gold-set`; `source_verified` is not human legal approval and cannot authorize a temporal or validity conclusion.
- Update `docs/03-data-and-ingestion.md` and `docs/14-implementation-blueprint.md` when an artifact or pipeline contract changes.

## Commits

- Do not add `Co-Authored-By` lines.
