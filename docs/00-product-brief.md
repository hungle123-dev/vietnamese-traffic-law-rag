# 00. Product Brief

## Product statement

**Vietnamese Traffic Law Hybrid GraphRAG** helps users find verifiable Vietnamese road-traffic law from a curated corpus. It is a legal-information product, not a general chatbot or a substitute for professional legal advice.

Users ask in Vietnamese, for example:

- “Đi xe máy vượt đèn đỏ bị xử lý thế nào?”
- “Tôi cần mang giấy tờ gì khi điều khiển xe?”
- “Quy định này có còn áp dụng vào ngày X không?”

The product answers only when the selected evidence supports the claim. It returns a citation to document, article, clause, or point; shows validity information and the public source link; and asks for clarification or abstains when evidence is insufficient.

## Target users

| Persona | Need | Product boundary |
|---|---|---|
| Road user | Understand duties, violations, and procedures | Do not infer personal legal liability from incomplete facts |
| Student or law learner | Locate provisions and their hierarchy | Do not provide unverifiable citations |
| Small transport operator | Find relevant transport rules | Do not present stale provisions as current |
| Reviewer | Audit data, retrieval, and citations | Do not hide defects behind fluent prose |

## Core value

1. **Grounded:** each legal claim has evidence.
2. **Temporal:** answers are tied to `effective_at` or the snapshot date.
3. **Structured:** a point belongs to a clause and an article; context expansion is bounded.
4. **Auditable:** an answer can be traced to an index, parsed unit, raw portal response, and public URL.
5. **Measurable:** retrieval and citation are evaluated separately from generation fluency.
6. **System-oriented:** ingestion and indexing are offline; the request path is cache → retrieval → bounded graph context → cited generation.

## Domain boundary

### In scope

- Curator-approved laws, decrees, circulars, and directly relevant documents on Vietnamese road traffic.
- Exact provision lookup, natural-language search, validity-aware answers, and multi-document questions within the active snapshot.
- Operator workflows for curation, ingest, evaluation, and snapshot promotion.

### Out of scope

- The whole Vietnamese legal system or every record exposed by a portal search.
- Official legal advice, dispute prediction, filing fines or complaints, and personal-case handling.
- Camera analysis, traffic-sign recognition, or unbounded crawling.
- Default agent loops, multi-agent coordination, arbitrary graph queries, and fine-tuning before benchmark evidence exists.

## Data decision

The primary source is the National Legal Portal. The planned client uses the same JSON endpoints as its web interface to fetch metadata and `docContent` HTML. It saves the response unchanged before deterministic normalization and hierarchy parsing.

Because this interface is UI-backed rather than a versioned public developer API, the curated catalog stores a reviewed portal GUID for every source. Each ingestion run validates the response schema before any parsed data enters a snapshot.

A source without complete readable structured HTML is marked `blocked_no_structured_content`. It is not parsed, indexed, or cited until a curator approves another structured source.

## v1 success definition

v1 is complete only when a new operator can rebuild a reviewed snapshot, build its graph/indexes, run search and QA, resolve every displayed citation, and reproduce an evaluation report. A chat screen that produces plausible text is not a success criterion.

## Key failure modes to demonstrate

- Retrieved text sounds relevant but does not support the claim.
- A citation resolves but is outside the active snapshot.
- A question lacks vehicle type or time and the system answers too confidently.
- Validity metadata is incomplete.
- The upstream portal response changes shape or omits content.

Requirements are defined in [01-scope-and-requirements.md](01-scope-and-requirements.md); implementation boundaries are defined in [02-system-architecture.md](02-system-architecture.md).
