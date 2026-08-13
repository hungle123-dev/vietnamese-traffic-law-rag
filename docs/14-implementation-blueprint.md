# 14. Implementation Blueprint

## Purpose

This is the file-by-file plan for the first coding phase. It prevents premature scaffolding and keeps the implementation aligned with the architecture.

The repository is intentionally documentation-only now. Do not create these files until the Phase 0 data-readiness gate passes.

## Phase 1 implementation order

### Step 1: Minimal project boundary

Create only the runtime and quality tooling required for ingestion:

    pyproject.toml
    README update with runnable commands
    src/traffic_legal_qa/
    tests/fixtures/
    tests/unit/

Use Python 3.12 or later, uv, Ruff, mypy, and pytest. Phase 1 runtime dependencies are only Pydantic for boundary models and Typer for the curator command. Use the Python standard library for HTTP and HTML parsing unless a concrete limitation appears. Add the Neo4j driver and embedding dependencies in Phase 2; add FastAPI and Uvicorn in Phase 3; add Pydantic Settings only when the runtime configuration boundary exists.

A root package initializer is optional and should exist only if it exposes a public version. Subdirectories do not need initializer files unless they define an explicit public package surface. Do not add empty files merely to make the tree look conventional.

### Step 2: Portal contract first

Implement in this order:

    ingestion/models.py
    ingestion/portal.py
    tests/fixtures/portal_detail_valid.json
    tests/unit/test_portal.py

Models define the canonical metadata and parsed unit schema. The portal client has one concrete job: fetch and validate a reviewed GUID. It validates the current `success`/`data` detail envelope before mapping `data.docIdentity`, `data.docName`, and `data.docContent`. It uses normal TLS verification, a timeout, byte limit, expected response fields, and explicit error types.

Tests use saved portal fixtures. A live portal smoke test is opt-in and cannot be the only test.

### Step 3: Artifacts and parser

Implement:

    ingestion/normalize.py
    ingestion/parser.py
    ingestion/storage.py
    ingestion/pipeline.py
    tests/fixtures/traffic_sample_normalized.txt
    tests/unit/test_normalize.py
    tests/unit/test_parser.py
    tests/unit/test_pipeline.py

Order inside pipeline:

    fetch response
    → store raw JSON in quarantine
    → validate schema
    → normalize HTML
    → parse hierarchy
    → validate units
    → write parsed document
    → update draft manifest

Store raw response immediately after the bounded fetch. It stays quarantined if schema validation fails and becomes corpus input only after schema, metadata, and hierarchy validation pass. Manifest update happens only after all validation passes.

### Step 4: Curator command

Implement only after the pipeline passes fixtures:

    cli.py
    tests/unit/test_cli.py

Commands are deliberately small:

    search-portal
    fetch-portal
    validate-snapshot

Search prints candidates for human review. Fetch accepts a GUID already present in the catalog. It never accepts an arbitrary URL or bulk search phrase as an ingest target.

## Phase 2 implementation order

Only after Phase 1 gate passes, add:

    graph/importer.py
    graph/validity.py
    retrieval/lexical.py
    retrieval/dense.py
    retrieval/fusion.py
    retrieval/service.py
    evaluation/datasets.py
    evaluation/metrics.py
    evaluation/runner.py

Add the Neo4j driver and embedding dependencies only at this phase. Build lexical and dense baselines separately before fusion. Do not add reranking before R0–R2 results exist.

Import deterministic hierarchy first, then import only approved records from `relations/{snapshot_id}.json`. A relation candidate, portal hint, or unresolved source/target must fail the draft snapshot gate rather than create a public graph edge.

## Phase 3 implementation order

Only after a retrieval configuration is selected, add:

    retrieval/rerank.py
    qa/citations.py
    qa/prompts.py
    qa/service.py
    api/schemas.py
    api/routes.py
    api/app.py

The citation resolver is implemented before the generator endpoint. The QA route is thin: validate request, call service, return schema. No business logic belongs in route handlers.

## Phase 4 implementation order

Add UI, operator API, readiness, structured tracing, deployment configuration, and rollback only after QA works against a promoted snapshot.

## Design rules for code

- One concrete portal client and one concrete graph store in v1.
- Prefer a small function or dataclass/Pydantic model over a one-method abstraction.
- Inject I/O dependencies only where tests need a boundary; do not build a global service container.
- Keep legal hierarchy and validity deterministic.
- Version every persisted artifact that affects reproducibility.
- Validate external input at ingress: portal responses, CLI arguments, and HTTP requests.
- Every non-trivial parser, transformation, or citation rule gets the smallest focused test.
- Preserve existing project behavior outside the requested change; do not rewrite unrelated modules.

## Explicitly do not build yet

- Generic source-provider interfaces.
- Repository and unit-of-work layers.
- Event buses, queues, worker frameworks, or scheduled crawlers.
- Separate vector, full-text, metadata, and graph services.
- LLM-driven parsing, relation extraction, or arbitrary Cypher.
- Agent orchestration or multi-agent frameworks.
- UI before retrieval and citation contracts are stable.

## Completion check for each pull request

1. Scope maps to a phase and requirement.
2. Minimal affected modules are changed.
3. Focused tests fail before the change and pass after it.
4. Formatter, linter, type checker, and relevant tests pass.
5. Documentation changes when a contract or decision changes.
6. No generated raw artifacts, credentials, or model indexes enter Git.
