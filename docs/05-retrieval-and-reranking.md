# 05. Retrieval and Reranking

## Goal

Maximize recall before generation, then improve precision and legal context without losing traceability. Retrieval is the primary intelligence path; generation explains selected evidence.

## Input and candidate contract

Input contains a Vietnamese question, optional short conversation context, optional effective date, and filters.

Every candidate passed beyond first-stage retrieval contains:

    unit_id
    document_id
    snapshot_id
    text
    unit_type
    validity
    source_url
    retriever ranks and scores

A candidate without unit ID and snapshot is invalid for QA.

Before any search, retrieval restricts candidates to the active snapshot and explicit user filters. When `effective_at` is available and validity can be determined from indexed metadata, a false candidate is excluded before ranking. `unknown` is retained only with its warning so the system can clarify or abstain rather than silently treating it as current.

## Query handling

### Validation

- Enforce length and message-count limits.
- Normalize Unicode and whitespace.
- Preserve legal document IDs, article/clause/point references, dates, vehicle types, and amounts.
- Detect empty, clearly out-of-domain, and prompt-injection-shaped input.
- Do not rewrite a precise identifier into prose.

### Rewrite and expansion

Conversation rewrite is used only when the newest question contains unresolved references. Search the original question as well when rewrite confidence is low.

Expansion is a measured candidate-recall feature, not an answer source. It may add common vehicle terminology, legal wording, or decomposed subqueries. It must preserve the original query and record its version. No expansion may invent a legal rule.

## Retrieval stages

### Exact lookup

If the question contains a document ID or provision reference, attempt deterministic lookup first. Exact lookup returns a source directly or contributes a high-confidence candidate; it does not bypass validity and citation checks.

### Lexical retrieval

Full-text or BM25 retrieval is mandatory because it handles document IDs, article numbers, rare terms, and legal phrasing well.

### Dense retrieval

Dense retrieval handles paraphrases between everyday Vietnamese questions and formal legal language. The chosen embedding model must be benchmarked on the project gold set, not selected from leaderboard reputation alone.

### Fusion

The initial hybrid default is Reciprocal Rank Fusion:

    RRF(d) = Σ 1 / (k + rank_r(d))

It is chosen because lexical and dense scores need not share a calibrated scale. Keep fusion configuration versioned with each run.

### Selective reranking

A cross-encoder reranks only a bounded candidate pool, maximum 50 in v1. It has a fallback to fused ranking. Reranking is not assumed to help; keep it only if the ablation improves the gold set within latency budget.

### Graph expansion

After ranking, retrieve only needed parent, child, sibling, and reviewed relation units. Expansion has fixed depth and count limits. Never insert an expanded unit into a claim unless it is included in the selected evidence set.

Validity is resolved before final context selection, so a structurally nearby but inapplicable provision cannot become evidence merely through graph expansion.

## Context selection

The final context:

- prioritizes direct evidence;
- groups units by document and hierarchy;
- keeps server-generated citation markers immutable;
- includes no more than ten evidence units by default;
- avoids mixing current and repealed material unless the question is explicitly temporal;
- carries validity warnings into generation.

## Confidence and abstention signals

No single score is treated as legal confidence. The policy combines top score, score margin, retriever agreement, exact-match signal, candidate count, validity knownness, and citation-verifier result.

A low signal results in clarification or abstention, not an invented answer.

## Required ablation matrix

| Run | Lexical | Dense | RRF | Rerank | Graph expansion | Validity |
|---|---:|---:|---:|---:|---:|---:|
| R0 | Yes |  |  |  |  |  |
| R1 |  | Yes |  |  |  |  |
| R2 | Yes | Yes | Yes |  |  |  |
| R3 | Yes | Yes | Yes | Yes |  |  |
| R4 | Yes | Yes | Yes | Yes | Yes |  |
| R5 | Yes | Yes | Yes | Yes | Yes | Yes |

All rows use the same snapshot and held-out questions. A comparison that changes multiple variables is not evidence for a component.

## Deferred complexity

Learning-to-rank, query decomposition by an LLM, and agentic retrieval are deferred. Introduce each only after error analysis identifies a failure that the simpler pipeline cannot address.
