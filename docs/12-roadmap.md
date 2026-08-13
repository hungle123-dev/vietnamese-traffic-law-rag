# 12. Roadmap

The roadmap is gate-based. A phase does not advance because a feature looks interesting; it advances when its exit evidence exists.

## Phase 0: Research and data freeze

### Deliverables

- This documentation set approved as the implementation blueprint.
- Seed catalog of about 12 reviewed portal GUIDs.
- For each seed: manually verify identifier, title, readable HTML, public URL, and expected source metadata.
- Thirty pilot Vietnamese questions with gold document/unit citations.
- A reviewed relation artifact covering every pilot question that depends on amendment, repeal, replacement, or temporal validity.
- Sanitized portal response fixtures and a curator review checklist.

### Exit gate

- One source can be traced manually from portal page to GUID, detail response, expected hierarchy, and citation.
- Corpus boundary is approved.
- No unreviewed document is described as current.
- No candidate portal relation is treated as a legal fact without relation evidence.
- Product, data, architecture, and acceptance documents agree.

## Phase 1: Data foundation

### Deliverables

- Minimal Python project bootstrap.
- Concrete portal client, response schema validation, raw artifact storage, HTML normalization, deterministic parser, manifest, and CLI.
- Unit fixtures plus one opt-in live portal smoke test.
- Data quality report for the seed catalog.

### Exit gate

- Identical raw response rebuilds to identical legal unit IDs.
- Twelve seed records ingest from structured portal responses.
- Schema, parse, and validation failure preserve raw artifact but block promotion.
- No query, graph, or LLM feature exists yet.

## Phase 2: Graph and retrieval baseline

### Deliverables

- Neo4j import with constraints and snapshot tagging.
- Exact lookup, lexical retrieval, dense retrieval, and retrieval-only API.
- Evaluation runner for R0, R1, and R2.

### Exit gate

- Search returns candidate IDs, snapshot, scores, and source locator.
- Gold pilot results identify whether failures are data, parser, lexical, or dense.
- A snapshot/index mismatch is detected by readiness checks.

## Phase 3: Grounded Hybrid GraphRAG

### Deliverables

- RRF, optional reranker, bounded graph expansion, deterministic validity service.
- QA service with structured generation, citation verifier, clarification, abstention, and provider fallback.
- R3 through R5 ablations.

### Exit gate

- No displayed citation fails resolution or evidence membership.
- Validity-unknown cases produce warnings rather than confident claims.
- Generation can fail without making retrieval unavailable.

## Phase 4: Product hardening

### Deliverables

- API contract tests, internal operator endpoints, trace logs, rate limits, health/readiness, and rollback.
- Minimal web UI that shows answer, sources, snapshot date, warnings, and disclaimer.
- Reproducible dev, eval, and demo paths.

### Exit gate

- A clean environment can run the demo against a promoted snapshot.
- Operator can inspect a failed ingest run and roll back a promotion.
- Latency and cost report exists.

## Phase 5: Portfolio release

### Deliverables

- 300–500 reviewed questions, final ablation report, manual error analysis, architecture diagram, and demo walkthrough.
- README setup, limitations, responsible-use statement, and reproducibility instructions.

### Exit gate

- Another developer can reproduce an evaluation run from recorded versions.
- The demo includes direct answer, temporal case, ambiguity, abstention, and multi-document examples.
- Claims about quality match published measurements.

## Optional Phase 6: Bounded agentic retrieval experiment

Run only if Phase 3 error analysis proves a fixed pipeline misses meaningful multi-hop cases.

The experiment has a small planner with only exact lookup, hybrid search, graph traversal, and validity tools; a maximum of three retrieval rounds; a fixed budget and stop condition; and an ablation against the fixed pipeline. It does not replace the default path without a documented quality/cost win.

## Suggested sequence

    Week 1: Phase 0 catalog, fixtures, pilot questions
    Week 2: Phase 1 portal client, artifacts, parser
    Week 3: Phase 1 validation and seed snapshot
    Week 4: Phase 2 lexical and dense baseline
    Week 5: Phase 2 evaluation and error analysis
    Week 6: Phase 3 fusion, graph context, validity
    Week 7: Phase 3 grounded QA and citation verifier
    Week 8: Phase 4 API, UI, and observability
    Week 9: Phase 5 evaluation, demo, and release materials
