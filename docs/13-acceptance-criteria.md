# 13. Acceptance Criteria

This checklist distinguishes a documentation-ready blueprint from a released product. No unchecked item is silently treated as complete.

## A. Documentation-ready gate

- [x] Product has one domain: Vietnamese road-traffic law.
- [x] Corpus is curated; portal-wide bulk discovery is excluded.
- [x] Source contract is portal JSON plus structured HTML.
- [x] Catalog stores reviewed portal GUIDs and expected identifiers.
- [x] Raw response, normalized text, parsed hierarchy, manifest, and index are distinct artifacts.
- [x] A reviewed relation artifact has explicit source, target, evidence, provenance, and approval fields.
- [x] Graph, retrieval, generation, citation, API, evaluation, operations, and roadmap use the same snapshot model.
- [x] Architecture is a modular monolith with explicit upgrade triggers.
- [x] Default agentic retrieval is excluded from v1.
- [x] Planned source layout and implementation order exist.
- [x] No runtime source code or data artifact remains in this repository.

## B. Phase 0 data-readiness gate

- [ ] About 12 source GUIDs have manual portal verification.
- [ ] Every selected record has expected document ID, title, public page URL, and curator status.
- [ ] Every selected response contains complete readable structured HTML.
- [ ] Thirty pilot questions have reviewed gold citation IDs.
- [ ] Every pilot temporal or amendment question has an approved relation-evidence record.
- [ ] Sanitized portal JSON and HTML fixtures exist.
- [ ] Curator checklist documents status and relation limitations.

## C. Data foundation gate

- [ ] Portal response schema is validated before artifact promotion.
- [ ] Raw responses are immutable and content-addressed.
- [ ] Normalization is deterministic and versioned.
- [ ] Parser returns stable hierarchy IDs for fixtures.
- [ ] Duplicate, empty, and orphan units are rejected.
- [ ] A manifest includes only validated parsed artifacts.
- [ ] A quality report records source, parser, and catalog versions.
- [ ] Failure retains raw artifact when available and blocks promotion.

## D. Retrieval and graph gate

- [ ] Neo4j constraints protect document, unit, and snapshot identity.
- [ ] Exact lookup, lexical, and dense retrieval run independently.
- [ ] Hybrid fusion is versioned and evaluated.
- [ ] Reranking is bounded and has fallback.
- [ ] Expansion has fixed depth and count limits.
- [ ] Validity returns true, false, or unknown.
- [ ] Every public cross-document relation has provenance and review status.
- [ ] Retrieval API returns candidate ID, score, snapshot, and source locator.

## E. Generation and API gate

- [ ] QA receives only selected evidence.
- [ ] Output schema validation handles malformed provider output.
- [ ] Citation verifier rejects non-existent, out-of-snapshot, and non-evidence IDs.
- [ ] Unsupported claims are removed, limited, clarified, or abstained.
- [ ] Unknown validity is visible in warnings.
- [ ] Health and readiness are distinct.
- [ ] Public requests have body, timeout, and rate controls.
- [ ] Operator endpoints do not accept arbitrary source URLs or graph queries.

## F. Evaluation and release gate

- [ ] Gold set contains at least 300 reviewed questions, or release documents a clear limitation.
- [ ] Reports include recall, citation support, validity, abstention, latency, and cost.
- [ ] R0–R5 ablations use the same held-out split and snapshot.
- [ ] At least twenty failures have root-cause analysis.
- [ ] Each run stores all version metadata needed to reproduce it.
- [ ] Demo shows direct answer, temporal question, ambiguity, abstention, and multi-document retrieval.
- [ ] README explains limitations and responsible use.
- [ ] No quality claim is published without the matching report.
