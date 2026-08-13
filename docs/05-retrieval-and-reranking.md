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

Metadata is a **gate**, not a claim that vector search is unnecessary: a natural-language traffic question normally uses lexical and dense recall after the gate narrows the correct snapshot, status, date, and explicit filter scope.

## Request path and cache

```text
normalize query → exact-safe cache → snapshot/status/filter gate → exact locator
→ lexical + dense in parallel → RRF → rerank small pool → graph expansion
→ select 5–10 evidence units → cited generation → verify → cache safe result
```

- The answer cache is used only for a canonical, context-free request whose snapshot, effective date, retrieval configuration, prompt version, and safety policy match exactly.
- The retrieval cache stores candidate IDs for the same scoped key. It never stores a result across snapshots.
- Cache miss is normal; cache is a latency/cost optimization, never an authority or a replacement for citation verification.

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

#### Current R0 contract

R0 is implemented with one Neo4j full-text index named `legal_units_fts_v1` over `snapshot_id`, `document_id`, `title`, and `text` on legal-unit labels `Part` through `Point`. The Lucene query constrains `snapshot_id` and any recognized document identifier before ranking; Cypher checks both again after retrieval. `build-lexical-index` is an offline command: it waits for `ONLINE`, validates the fixed labels/properties/analyzer/consistency contract, and checks the projected unit count against the frozen parsed snapshot. The request-facing `search-lexical` command only verifies the already-built index; it never creates or rebuilds one.

R0 normalizes Unicode/whitespace and rejects blank, overlong queries. When the query contains a known document identifier plus Điều/Khoản/Điểm, deterministic lookup returns that provision first; Neo4j full-text retrieval then fills the remaining bounded candidate list. Each result records exact rank (when present), lexical rank/score, `unit_id`, `document_id`, snapshot, source URL, unit type, title/text, and `validity: unknown`. R0 intentionally has no dense retrieval, validity decision, cache, graph expansion, reranker, or answer generation.

### Dense retrieval

Dense retrieval handles paraphrases between everyday Vietnamese questions and formal legal language. The chosen embedding model must be benchmarked on the project gold set, not selected from leaderboard reputation alone.

#### Current R1 contract

R1 is a dense-only baseline: no exact lookup, lexical candidates, fusion, reranker, graph expansion, validity decision, cache, or answer generation. It uses the pinned revision `84f9d9ada0d1a3c37557398b9ae9fcedcdf40be0` of `bkai-foundation-models/vietnamese-bi-encoder`, a 768-dimensional PhoBERT-based Vietnamese bi-encoder whose model card requires word segmentation. `BKAIEncoder` therefore applies `pyvi.ViTokenizer` to both corpus units and queries, limits the model to 256 tokens, and asks SentenceTransformers for L2-normalized embeddings.

The offline builder derives deterministic text from document title, hierarchy locator, optional unit title, and canonical unit text. It embeds only Article, Clause, and Point (6,343 units in this snapshot): these are the answer/citation granularity; Part/Chapter/Section remain structural graph nodes. The importer gives those three physical Neo4j labels a shared `LegalUnit` label. `legal_units_bkai_v1` is a cosine vector index over `LegalUnit.embedding_bkai_v1`, with quantization disabled for the small corpus and a fixed dimension/model contract.

Neo4j 5.26 cannot apply a snapshot metadata filter inside this vector index. Consequently `build-dense-index` and `verify_index` reject embeddings belonging to a second snapshot and reconcile all three counts—validated units, graph `LegalUnit`s, and embedded `LegalUnit`s—before search/evaluation. This is an explicit v1 single-embedded-snapshot limit, not a post-filter that could silently under-fill top-k. A multi-snapshot deployment must use a filtered vector capability or a separate database/index per active snapshot.

`build-dense-index` is offline and accepts a bounded `--batch-size` hardware calibration parameter. An interrupted build resumes only missing vectors: the frozen snapshot, graph count, single-snapshot guard, model-versioned property, and final full-coverage check remain mandatory. `search-dense` and `evaluate-r1` only verify and read an existing `ONLINE` index. `evaluate-r1` records index/model/revision/segmentation/device configuration and the same source-ID metrics as R0; it is run on dev before any R2 fusion choice, never as evidence from the held-out test split.

#### First dev measurement

On the frozen `traffic-2026-08-13-v1` snapshot and the same 15-question dev split, R1 confirms that the BKAI+PyVi path is operational but does **not** replace R0. These generated reports are retrieval evidence, not a legal-quality or release claim.

| Baseline | Unit Recall@1 | Unit Recall@3 | Unit Recall@5 | Unit Recall@10 | MRR@10 | Full / partial / miss @10 |
|---|---:|---:|---:|---:|---:|---:|
| R0 exact + lexical | 0.500 | 0.767 | 0.767 | 0.900 | 0.676 | 13 / 1 / 1 |
| R1 BKAI + PyVi dense-only | 0.600 | 0.667 | 0.733 | 0.733 | 0.650 | 11 / 0 / 4 |

R1 leads only at rank 1; R0 retains more source units by rank 3–10 and a higher MRR. This supports the pre-registered next step—R2 RRF fusion—rather than replacing lexical retrieval or tuning R1 against the held-out test split.

### Fusion

The initial hybrid default is Reciprocal Rank Fusion:

    RRF(d) = Σ 1 / (k + rank_r(d))

It is chosen because lexical and dense scores need not share a calibrated scale. Keep fusion configuration versioned with each run.

### Selective reranking

A cross-encoder reranks only a bounded candidate pool, maximum 50 in v1. It has a fallback to fused ranking. Reranking is not assumed to help; keep it only if the ablation improves the gold set within latency budget.

### Graph expansion

After reranking (or RRF when reranking is unavailable), retrieve only needed parent, child, sibling, and approved `AMENDS` units. Expansion has fixed depth and count limits. Never insert an expanded unit into a claim unless it is included in the selected evidence set.

Validity is resolved before final context selection, so a structurally nearby but inapplicable provision cannot become evidence merely through graph expansion.

## Context selection

The final context:

- prioritizes direct evidence;
- groups units by document and hierarchy;
- keeps server-generated citation markers immutable;
- includes five to ten evidence units by default;
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

For the current pilot, `evaluate-r0` and `evaluate-r1` write source-ID-only reports for exactly one frozen split. They record macro unit/document Recall@1/3/5/10, MRR@10, full/partial/miss at 10, per-question ranked IDs, snapshot, index contract, gold-file SHA-256, git commit, and timestamp. R1 also records its BKAI model revision, PyVi segmentation, normalization, dimension, maximum sequence length, and device. Parameters may be selected only on `dev`; run `test` once R0–R2 are frozen.

## Deferred complexity

Learning-to-rank, query decomposition by an LLM, and agentic retrieval are deferred. Introduce each only after error analysis identifies a failure that the simpler pipeline cannot address.
