# 01. Scope and Requirements

## Scope statement

The system answers road-traffic legal questions only within a reviewed `snapshot_id`. `Point` is the preferred evidence unit; use `Clause`, then `Article`, when the source has no lower level.

## Use cases

| ID | Use case | Minimum result |
|---|---|---|
| UC-01 | Ask a rule or situation | Answer, clarification, or abstention with evidence |
| UC-02 | Exact lookup | Normalized text, parent chain, citation, and source URL |
| UC-03 | Ask validity | `effective`, `not_effective`, or `unknown` at the requested date, with source status |
| UC-04 | Compare versions | Only verified relations with provenance |
| UC-05 | Curate and ingest | Operator searches portal, chooses GUID, and builds a draft snapshot |
| UC-06 | Evaluate | Run records snapshot, models, configuration, prompt, and metrics |

## Functional requirements

| ID | Requirement | Priority | Completion evidence |
|---|---|---:|---|
| FR-01 | Accept Vietnamese input through QA and search APIs | MUST | Contract and integration tests |
| FR-02 | Validate input while preserving identifiers and dates | MUST | Boundary tests |
| FR-03 | Retrieve only from the active traffic snapshot | MUST | Snapshot filter test |
| FR-04 | Ingest structured portal content from a reviewed GUID catalog | MUST | Fixture and live smoke test |
| FR-05 | Store raw response, normalized text, parsed hierarchy, and manifest separately | MUST | Hash and lineage test |
| FR-06 | Parse Part, Chapter, Section, Article, Clause, and Point deterministically | MUST | Parser fixtures |
| FR-07 | Provide lexical and dense retrieval independently | MUST | Retrieval benchmark |
| FR-08 | Fuse with RRF and rerank a bounded pool | SHOULD | Ablation report |
| FR-09 | Resolve hierarchy, relation, and validity before generation | MUST | Graph and temporal tests |
| FR-10 | Reject citations that do not resolve or are outside evidence | MUST | Citation tests |
| FR-11 | Clarify or abstain when evidence or validity is insufficient | MUST | Safety golden cases |
| FR-12 | Show operator ingestion reports and promotion state | SHOULD | CLI or internal API test |
| FR-13 | Trace a request to snapshot, index, model, and prompt | MUST | Trace inspection |
| FR-14 | Show answer, sources, warnings, and disclaimer in the UI | SHOULD | Manual acceptance |

## Non-functional requirements

### Correctness and safety

- No legal claim is returned without selected evidence.
- `unknown` validity is never presented as `current`.
- The LLM cannot invent unit IDs, alter legal text, or write legal data.
- An upstream schema change fails the run before parsing or promotion.

### Performance targets

These are benchmark targets, not achieved results:

- retrieval before generation: p95 below one second on the v1 corpus;
- end-to-end QA: p95 below 15 seconds in a single-node demo;
- reranker input: no more than 50 candidates;
- final context: no more than 10 evidence units within a token budget.

### Reproducibility record

Every ingestion and evaluation run persists:

```text
snapshot_id
catalog_version
portal_schema_version
parser_version
index_version
embedding_model
reranker_model
llm_model
prompt_version
git_commit
timestamp
```

## Explicit constraints

- A solo developer or small team has a few months: use a modular monolith.
- The v1 corpus has 15–30 reviewed document/version records; portal record count is not a project metric.
- Do not add a database, queue, or service until the relevant phase has measured a need.
- The product uses a single structured-content ingestion contract.

## Ready-for-code gate

The full Phase 1 data foundation opens only after all of the following exist: a seed catalog of about 12 verified portal GUIDs; 30 pilot questions with gold citations; sanitized HTML fixtures; and signed-off Phase 0 criteria. A single non-promoted technical smoke seed may validate the portal and parser contracts, but it does not satisfy this gate. See [12-roadmap.md](12-roadmap.md).
