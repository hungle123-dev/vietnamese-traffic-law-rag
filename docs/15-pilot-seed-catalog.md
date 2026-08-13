# 15. Pilot seed catalog — Vietnamese road-traffic law

> **State:** approved source catalog for a draft snapshot; not a promoted corpus or graph-relation dataset.
>
> **Verified against the portal API:** 2026-08-13.
>
> The version-controlled catalog is [`data/catalog/pilot-traffic-2026-08-13-v1.json`](../data/catalog/pilot-traffic-2026-08-13-v1.json). All 12 records have been parsed into a validated draft snapshot; no record has been indexed, evaluated, or imported into a graph.

## Purpose and boundary

This is the approved 12-document **pilot** for the product's domain: Vietnamese road-traffic law. It is deliberately a small, useful slice for proving the whole data path before expanding to the 15–30 records planned for v1. The selection was revised after an exhaustive pagination check of the current portal search on 2026-08-13 resolved several predecessor documents that an earlier, incomplete search had missed.

The selection is independent. It does not copy portal GUIDs, raw data, parsed files, amendment records, or graph edges from the NLP-LegalQA reference repository. Its processing shape may later resemble that project's `portal detail -> text + metadata -> parsed hierarchy -> reviewed relations -> graph` flow, but every source and every legal relation in this project must be collected and reviewed afresh.

The pilot is not a promise that the product can answer every traffic-law question. The Road Law is present, but the Road Traffic Order and Safety Law remains unavailable through a currently resolved portal detail source; that limitation is explicit in [known gaps](#known-gaps-and-exclusions).

## What was verified

For every proposed record, a direct request to the portal detail endpoint on 2026-08-13 satisfied all of the following:

1. HTTP status was `200`.
2. The JSON envelope had `success == true`.
3. `data.docIdentity` exactly matched the proposed legal identifier.
4. `data.docName` and HTML `data.docContent` were non-empty.
5. The public UI route used by the portal frontend—`/legal-documents/{docGUId}?tabName=noidung`—returned HTTP `200` for every record.

Vietnamese JSON was decoded from UTF-8 bytes before validation. The public route is client-rendered: a headless browser was blocked by the portal WAF, so title and content identity are verified through the same first-party detail API used by the UI, not inferred from the SSR shell. The portal's relation fields were empty across all 12 checked documents, so they are not used as graph evidence.

The technical verification above is separate from legal-relation approval. Curator approval, public-page URLs, and any reviewed literal corrections are recorded in the version-controlled catalog; provision-level relation evidence is still required before a legal-change edge or temporal answer is allowed. Deterministic hierarchy and portal-metadata graph projection do not depend on it.

## Approved pilot documents

### A. Foundation

| ID | Why it belongs in the pilot | Portal status on 2026-08-13 | Verified portal sources |
|---|---|---|---|
| `35/2024/QH15` | The Road Law is the foundation for road activity, infrastructure, and road transport. A road-law product without one directly available foundation law has a structural coverage gap. | Effective 2025-01-01; **Còn hiệu lực**; 377,196 HTML characters. | [Public page](https://phapluat.gov.vn/legal-documents/172475?tabName=noidung) · [API detail](https://phapluat.gov.vn/api/legal-documents/detail?docGUId=172475&tabName=noidung) |

### B. Sanctions and licence points

| ID | Why it belongs in the pilot | Portal status on 2026-08-13 | Verified portal sources |
|---|---|---|---|
| `168/2024/NĐ-CP` | Core road-traffic administrative sanctions and licence-point deduction/recovery. | Effective 2025-01-01; **Còn hiệu lực**; 392,583 HTML characters. | [Public page](https://phapluat.gov.vn/legal-documents/173920?tabName=noidung) · [API detail](https://phapluat.gov.vn/api/legal-documents/detail?docGUId=173920&tabName=noidung) |
| `238/2026/NĐ-CP` | Amendment to `168/2024/NĐ-CP`; gives the pilot a real temporal/amendment case. | Effective 2026-08-15; **Chưa có hiệu lực** on verification date; 54,057 characters. It must not support a current-law answer before that date. | [Public page](https://phapluat.gov.vn/legal-documents/f4b0c320-79e6-11f1-8c8a-3587e086d762?tabName=noidung) · [API detail](https://phapluat.gov.vn/api/legal-documents/detail?docGUId=f4b0c320-79e6-11f1-8c8a-3587e086d762&tabName=noidung) |
| `336/2025/NĐ-CP` | Sanctions in road-operation activity; complements the road-safety sanction focus without pretending it is the same regime as `168`. | Effective 2026-03-01; **Còn hiệu lực**; 162,780 characters. | [Public page](https://phapluat.gov.vn/legal-documents/185666?tabName=noidung) · [API detail](https://phapluat.gov.vn/api/legal-documents/detail?docGUId=185666&tabName=noidung) |

### C. Road activity and implementation

| ID | Why it belongs in the pilot | Portal status on 2026-08-13 | Verified portal sources |
|---|---|---|---|
| `165/2024/NĐ-CP` | Detailed guidance for the Road Law and Article 77 of the Road Traffic Order and Safety Law. | Effective 2025-01-01; **Hết hiệu lực một phần**; 408,042 characters. Questions that rely on an amended portion require temporal evidence. | [Public page](https://phapluat.gov.vn/legal-documents/173895?tabName=noidung) · [API detail](https://phapluat.gov.vn/api/legal-documents/detail?docGUId=173895&tabName=noidung) |
| `241/2026/NĐ-CP` | Amendment to `165/2024/NĐ-CP`; supplies another verified temporal case. | Effective 2026-07-01; **Còn hiệu lực**; 274,576 characters. | [Public page](https://phapluat.gov.vn/legal-documents/aee9c160-8bc1-11f1-a232-057125fe017c?tabName=noidung) · [API detail](https://phapluat.gov.vn/api/legal-documents/detail?docGUId=aee9c160-8bc1-11f1-a232-057125fe017c&tabName=noidung) |
| `151/2024/NĐ-CP` | Detailed implementation of the Road Traffic Order and Safety Law; it supplies the resolved predecessor needed to review the current amendment path. | Effective 2025-01-01; **Hết hiệu lực một phần**; 125,847 characters. | [Public page](https://phapluat.gov.vn/legal-documents/174961?tabName=noidung) · [API detail](https://phapluat.gov.vn/api/legal-documents/detail?docGUId=174961&tabName=noidung) |
| `236/2026/NĐ-CP` | Current amendment affecting detailed road-traffic-order-and-safety implementation. With `151/2024/NĐ-CP` now resolved, it is a real reviewable temporal case rather than an unsupported dependency. | Effective 2026-07-01; **Còn hiệu lực**; 184,528 characters. | [Public page](https://phapluat.gov.vn/legal-documents/224b21d0-7d9e-11f1-bb7a-69f7cf2f90db?tabName=noidung) · [API detail](https://phapluat.gov.vn/api/legal-documents/detail?docGUId=224b21d0-7d9e-11f1-bb7a-69f7cf2f90db&tabName=noidung) |

### D. Road transport activity

| ID | Why it belongs in the pilot | Portal status on 2026-08-13 | Verified portal sources |
|---|---|---|---|
| `158/2024/NĐ-CP` | Main regulation on road-transport activity; the direct predecessor for the next document. | Effective 2025-01-01; **Hết hiệu lực một phần**; 378,100 characters. | [Public page](https://phapluat.gov.vn/legal-documents/173412?tabName=noidung) · [API detail](https://phapluat.gov.vn/api/legal-documents/detail?docGUId=173412&tabName=noidung) |
| `218/2026/NĐ-CP` | Amendment to `158/2024/NĐ-CP`; a focused road-domain temporal case with both source documents now available. | Effective 2026-08-10; **Còn hiệu lực**; 524,660 characters. | [Public page](https://phapluat.gov.vn/legal-documents/8a3f0c20-8bc2-11f1-b860-ff58e2a2eb18?tabName=noidung) · [API detail](https://phapluat.gov.vn/api/legal-documents/detail?docGUId=8a3f0c20-8bc2-11f1-b860-ff58e2a2eb18&tabName=noidung) |

### E. Licensing procedure

| ID | Why it belongs in the pilot | Portal status on 2026-08-13 | Verified portal sources |
|---|---|---|---|
| `12/2025/TT-BCA` | Licensing tests, licence issuance, and international driving permits; a main user-facing procedure topic. | Effective 2025-03-01; **Còn hiệu lực**; 147,255 characters. | [Public page](https://phapluat.gov.vn/legal-documents/175618?tabName=noidung) · [API detail](https://phapluat.gov.vn/api/legal-documents/detail?docGUId=175618&tabName=noidung) |
| `108/2026/TT-BCA` | Current licensing-test, licence-issuance, and international-permit document. It deliberately shares a topic with `12/2025/TT-BCA` so evaluation can expose a temporal overlap instead of hiding it. | Effective 2026-07-01; **Còn hiệu lực**; 170,020 characters. | [Public page](https://phapluat.gov.vn/legal-documents/6423e210-7ffe-11f1-a6e4-33cf5e12fa5a?tabName=noidung) · [API detail](https://phapluat.gov.vn/api/legal-documents/detail?docGUId=6423e210-7ffe-11f1-a6e4-33cf5e12fa5a&tabName=noidung) |

## Candidate relations, not graph edges

The following are title-supported **document-level candidates** only. They must remain outside `relations/{snapshot_id}.json` until a reviewer identifies the source and target provisions, saves the evidence unit, and approves the relation under the contract in [03-data-and-ingestion.md](03-data-and-ingestion.md).

| Candidate | Seed-level provision evidence | What it does **not** establish yet | State |
|---|---|---|---|
| `238/2026/NĐ-CP → 168/2024/NĐ-CP` | Source Article 1 changes points of clause 3, Article 3; target Article 3 and clause 3 exist in `168`. | The complete set of amended provisions and their final validity. | `seed_evidence_located` |
| `241/2026/NĐ-CP → 165/2024/NĐ-CP` | Source Article 1 changes Article 4; target Article 4 exists in `165`. | The complete set of amended provisions and their final validity. | `seed_evidence_located` |
| `236/2026/NĐ-CP → 151/2024/NĐ-CP` | Source Article 1 changes clause 1, Article 9; target Article 9 and clause 1 exist in `151`. | The complete set of amended provisions and the role of `184/2025/NĐ-CP` in each target provision. | `seed_evidence_located` |
| `218/2026/NĐ-CP → 158/2024/NĐ-CP` | Source Article 1 changes point a, clause 6, Article 4; the target article and clause exist in `158`. | The complete set of amended provisions and their final validity. | `seed_evidence_located` |
| `108/2026/TT-BCA` and `12/2025/TT-BCA` | Both concern licensing tests, licence issuance, and international permits. | That either one replaces or amends the other. | `no_relation_claimed` |

## Known gaps and exclusions

| Record or candidate | Decision | Reason and product behavior |
|---|---|---|
| `36/2024/QH15` — Luật Trật tự, an toàn giao thông đường bộ | Not included. | Same limitation. It is a priority for the next catalog review, not a hidden assumption. |
| `184/2025/NĐ-CP` | Not selected for this 12-document pilot, although its current detail source is resolved. | Its title is broader than road traffic (two-tier local government and public-security decrees). It remains a reviewed-relation dependency for `151/2024/NĐ-CP` and `236/2026/NĐ-CP`, not a primary retrieval source. |
| `119/2024/NĐ-CP`, `65/2024/TT-BCA`, `105/2026/TT-BCA` | Deferred to the v1 expansion catalog. | They are valid, focused sources, but their marginal coverage is lower than the newly resolved foundation/base documents. Point recovery is already represented by `168/2024/NĐ-CP`; electronic payment is a narrower question family. |
| `13/2025/TT-BCA` | Excluded from this 12-document proposal. | It spans road, rail, and inland-waterway topics. `218/2026/NĐ-CP` provides a more focused road-domain slot. It can be reconsidered during expansion if evaluation exposes a specific road-only gap. |

## Why this is a sound first corpus, and what it is not

The selection is based on a fixed order of evidence, not on “the newest documents” or a copied list:

1. **Hard source gate:** a record must pass the current detail-response contract. Legal importance cannot compensate for an unfetchable source.
2. **Direct road-domain fit:** pure road-traffic/road-transport records beat cross-modal or broad administrative records for a 12-slot pilot.
3. **Marginal question coverage:** every retained group anchors a different user question family.
4. **Lifecycle value:** where possible, include both the base and its current amendment so the graph must handle time and provenance rather than assume that a newer text wins.
5. **Redundancy last:** defer a valid narrow procedure before deferring a foundation law or a resolvable base/amendment pair.

| Question family | Pilot anchors | Why this cannot be replaced by a single generic document |
|---|---|---|
| Road activity and infrastructure | `35`, `165`, `241` | It needs a foundation law plus detailed guidance and a verified amendment path. |
| Road-traffic sanctions and licence points | `168`, `238`, `336` | `168` and `336` govern different sanction scopes; `238` forces an effective-date check. |
| Detailed road-traffic order and safety | `151`, `236` | The pair makes a current amendment reviewable instead of leaving an orphan amendment. |
| Road-transport activity | `158`, `218` | The pair is a separate road-transport regime and a second independently reviewable amendment chain. |
| Licensing procedure | `12`, `108` | The overlap is intentional: both are effective, so the system must retrieve evidence and warn rather than invent a replacement relation. |

This yields one foundation law, five distinct question families, and four explicit document-lifecycle cases (`238→168`, `241→165`, `236→151`, `218→158`). The 12 records are a stronger future GraphRAG evaluation slice than 12 unrelated traffic documents because they will test retrieval, citations, time, and relation review together.

## Final bounded validation

| Check | Result | Boundary |
|---|---|---|
| Detail-source contract | 12/12 passed HTTP `200`, `success == true`, exact identifier, non-empty title, and non-empty HTML. | Re-run before each future snapshot; portal API is not a stable developer contract. |
| Graph-ready portal metadata | Parsed artifact v2 has document type, effect status, organ, and signer on 12/12 documents; field on 11/12 and major on 8/12. | This supports only deterministic metadata nodes; it does not create legal-change relations. |
| Public portal route | 12/12 public URLs are recorded and returned HTTP `200`. The route was read from the portal's own frontend code. | The page is client-rendered and the portal WAF blocks headless rendering, so API identity remains the automated evidence. |
| Amendment evidence | A precise Article-1 source provision and target-unit presence are located for each of the four amendment chains. | These are candidate inputs, not approved relation records or temporal QA evidence. |
| Scope and safety | `238/2026/NĐ-CP` is explicitly marked not effective until 2026-08-15. | No current-law answer may apply it before that date. |

It is still only a pilot. The validated draft snapshot has 6,433 hierarchy units, but has no machine-readable approved relation artifact and no gold questions. Calling it a promoted corpus, measured GraphRAG system, or legal temporal-answer system now would be false.

## Remaining gates before promotion

Before importing legal-change edges, claiming retrieval quality, or serving QA, complete all of the following:

1. Keep the recorded public URL and re-run the source contract immediately before each future snapshot; do not re-discover a record by title.
2. For every temporal pilot question, promote its reviewed provision mapping into a relation-evidence record after parsing provides stable unit IDs; otherwise design the question to return a validity warning or abstain.
3. Write 30 pilot questions with gold citations only after the selected documents have stable parsed unit IDs.
