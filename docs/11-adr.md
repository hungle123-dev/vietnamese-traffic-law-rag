# 11. Architecture Decision Records

This document records the v1 decisions and their revisit triggers. A decision is not permanent; it changes only with documented evidence.

## ADR summary

| ID | Decision | Status |
|---|---|---|
| ADR-001 | Restrict domain to Vietnamese road traffic | Accepted |
| ADR-002 | Use structured legal units as canonical evidence | Accepted |
| ADR-003 | Use the National Legal Portal structured HTML contract | Accepted |
| ADR-004 | Use a curated GUID catalog and versioned snapshots | Accepted |
| ADR-005 | Start with Neo4j for graph, lexical, and vector indexes | Accepted |
| ADR-006 | Use hybrid lexical plus dense retrieval with RRF | Accepted |
| ADR-007 | Make validity deterministic metadata and graph logic | Accepted |
| ADR-008 | Use fixed retrieval orchestration, not default agents | Accepted |
| ADR-009 | Verify structured citations after generation | Accepted |
| ADR-010 | Measure retrieval and citation before answer fluency | Accepted |

## ADR-001: Narrow traffic domain

**Context:** Vietnamese law is too broad for a small team to curate, evaluate, and demonstrate safely.

**Decision:** Include only curator-approved road-traffic sources in one active snapshot.

**Trade-off:** Less breadth, but meaningful citation, validity, and evaluation coverage.

**Revisit:** The traffic corpus meets quality targets and another domain has its own reviewed corpus and gold questions.

## ADR-002: Structured units over blind chunks

**Context:** Token chunks can separate conditions, exceptions, and citation boundaries.

**Decision:** Part, Chapter, Section, Article, Clause, and Point are canonical units. A bounded text window may be added later, but cannot replace unit identity.

**Trade-off:** Deterministic parsing needs fixtures and validation.

**Revisit:** Gold evaluation shows a clear retrieval limitation caused by unit granularity.

## ADR-003: Structured portal response

**Context:** The portal interface exposes document metadata and full HTML content through its active web JSON endpoints.

**Decision:** Ingest only complete readable structured HTML after schema validation. Use normal HTTPS verification and a small, concrete client.

**Trade-off:** The interface is UI-backed and may change.

**Mitigation:** Store raw responses, pin reviewed GUIDs, keep fixtures, smoke-test schema, and fail safely on drift.

**Revisit:** The portal publishes a stable public API or the contract becomes unsuitable for the curated corpus.

## ADR-004: Curated GUID catalog and snapshots

**Context:** Portal search result count is large and search order/title matching are not stable corpus selection mechanisms.

**Decision:** Catalog stores reviewed GUID, expected document ID, approval state, and snapshot version. Build a draft snapshot, validate it, then promote it.

**Trade-off:** Human curation takes time.

**Revisit:** A stable official classification and relation source can safely automate a narrow part of curation.

## ADR-005: Neo4j first

**Context:** Hierarchy and legal relations are central, while v1 corpus and traffic are small.

**Decision:** Use Neo4j as the initial graph plus lexical/vector index store.

**Trade-off:** It may not be the fastest specialized engine at larger scale.

**Revisit:** Same-gold-set benchmarks show a measurable latency or quality limitation.

## ADR-006: Hybrid retrieval with RRF

**Context:** Lexical search is strong for legal identifiers; dense search is strong for paraphrases.

**Decision:** Run both and fuse with RRF before optional reranking.

**Trade-off:** Two retrieval calls and additional evaluation work.

**Revisit:** Sufficient held-out data supports a better calibrated fusion method.

## ADR-007: Deterministic validity

**Context:** Recency guesses and LLM judgments are unreliable for legal effect.

**Decision:** Validity comes from source metadata and reviewed graph relations. Unknown is an explicit public outcome.

**Trade-off:** Curation is necessary.

**Revisit:** A trusted structured source provides enough provenance to automate specific relations.

## ADR-008: No default agentic retrieval

**Context:** The core path is known: lookup, hybrid retrieval, bounded expansion, citation verification.

**Decision:** Use a fixed orchestrated pipeline. An agent experiment is separate and must beat the fixed path on the same gold set under a bounded tool budget.

**Trade-off:** Less agentic marketing language.

**Revisit:** Error analysis shows persistent multi-hop failures the fixed path cannot resolve.

## ADR-009: Structured output and citation verifier

**Context:** Fluent generated text can contain fabricated citations or unsupported detail.

**Decision:** Generate structured claims and resolve citations deterministically before response.

**Trade-off:** Small latency and implementation cost.

**Revisit:** Never remove deterministic resolver; only improve its support assessment.

## ADR-010: Retrieval and citation-first evaluation

**Context:** Answer-style metrics can conceal evidence failures.

**Decision:** Treat recall, citation support, validity, abstention, and reproducibility as primary. Text similarity and model judging are secondary.

**Trade-off:** Requires reviewed questions and manual analysis.

**Revisit:** A domain-expert benchmark broad enough to calibrate additional metrics becomes available.
