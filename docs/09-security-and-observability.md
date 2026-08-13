# 09. Security and Observability

## Threat model

| Threat | Impact | Required control |
|---|---|---|
| Prompt injection in query or legal text | Model ignores policy | Separate instruction from data; selected evidence only; output validation |
| Citation fabrication | Legal claim cannot be audited | Server-side resolver and evidence-membership check |
| Source poisoning or portal drift | Incorrect corpus artifact | Reviewed catalog, raw hash, schema fixture, promotion gate |
| Arbitrary graph access | Data exposure or denial of service | No public Cypher or model-controlled graph tools |
| Excessive requests | Cost and latency | Body, rate, concurrency, and timeout limits |
| Secret or personal-data leakage | Privacy and credential risk | Environment-only secrets, redacted structured logs |
| Stale snapshot | Outdated answer | Snapshot ID and age in every trace |
| Provider outage | Broken user experience | Timeout and safe retrieval-only fallback |

## Data integrity

- The raw portal response is immutable and SHA-256 addressed.
- A manifest includes only validated parsed content.
- Parser, normalizer, schema, catalog, and snapshot versions are recorded.
- Cross-document legal relations require provenance and review.
- Index build occurs outside the public request path.
- Promotion is atomic; the previous promoted snapshot remains rollbackable.

## Prompt safety

- Legal text, user questions, and conversation are treated as untrusted data.
- The model cannot invoke source fetch, graph write, or shell-like tools.
- Citation IDs are injected by the system and checked after generation.
- Include regression fixtures for malicious instructions, fake citations, malformed JSON, and ambiguous questions.

## Trace record

Every QA request logs structured fields:

    trace_id
    request_id
    timestamp
    query_hash
    snapshot_id
    index_version
    retrieval_config
    prompt_version
    model_name
    answer_mode
    abstain
    status

Stage timings:

    validation_ms
    exact_lookup_ms
    lexical_ms
    dense_ms
    fusion_ms
    rerank_ms
    graph_ms
    generation_ms
    citation_verify_ms
    total_ms

Raw questions and answers are not logged by default. Debug capture requires an explicit switch, redaction, and short retention.

## Metrics

- citation validation failure rate;
- abstention and clarification rate;
- source schema failure rate;
- parser validation failure rate;
- active snapshot age;
- retrieval candidate count and retriever agreement;
- p50/p95 timings and dependency errors;
- token usage and estimated cost;
- ingestion run status and promotion/rollback count.

## Safe degradation

| Failure | Response |
|---|---|
| LLM unavailable | Return selected sources with generation warning |
| Reranker unavailable | Use fused ranking |
| Dense retrieval unavailable | Use lexical and exact lookup with warning |
| Lexical retrieval unavailable | Use dense with warning |
| Graph unavailable | Do not generate validity or relation claims |
| Citation verifier unavailable | Do not return generated legal claims |
| Portal unavailable during ingest | Fail or retry the run; do not alter active snapshot |

## v1 boundary

Local structured logs and a metrics export are enough initially. Full SIEM, distributed tracing infrastructure, and a complex security platform are not required before a working snapshot and public API exist.
