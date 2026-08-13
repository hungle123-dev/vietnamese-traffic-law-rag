# 03. Data and Ingestion Contract

## Source contract

The primary source is the current legal-document interface of [Cổng Pháp luật quốc gia](https://phapluat.gov.vn/he-thong-van-ban-phap-luat). Its UI currently calls:

```text
POST /api/legal-documents
GET  /api/legal-documents/detail?docGUId={guid}&tabName=noidung
```

As observed on 2026-08-12, search returns candidates at `data.docs` and its total at `data.rowCount`. Detail returns an envelope with `success`, `data`, and `tabName`; metadata and HTML are at `data.docIdentity`, `data.docName`, and `data.docContent`. This is an undocumented UI-backed API, not a stable developer contract. The client therefore uses normal HTTPS verification, bounded timeout and response size, explicit schema validation, and regression fixtures. It never disables transport verification.

## Discovery request contract

The following search body was observed from the portal interface on 2026-08-12. It is a **discovery-only** contract: take candidate GUIDs from its result, then let a curator approve a catalog entry before any detail fetch.

```json
{
  "keywords": "",
  "isSearchExact": 0,
  "issueDateFrom": "",
  "issueDateTo": "",
  "searchByDate": null,
  "pageIndex": 0,
  "rowAmount": 20,
  "searchOptions": 1,
  "sortBy": "issueDate",
  "sortOrder": "desc",
  "docGroupIds": [],
  "fieldIds": [],
  "effectStatusIds": [],
  "signerIds": [],
  "organIds": [],
  "docTypeIds": [],
  "provinceIds": [],
  "wardIds": [],
  "languageId": 1,
  "qtdcListFilter": "all",
  "qtdcListScope": "all"
}
```

Do not use legacy `dateFrom` or `dateTo` keys. A saved search fixture must assert the `data.docs` and `data.rowCount` wrapper plus the candidate fields needed to capture `docGUId`, document identity, and title. Any mismatch is `PORTAL_SCHEMA_CHANGED`, not a reason to guess a replacement schema.

## Curated catalog, not bulk discovery

Portal search is used only to discover candidates. A curator selects a narrow traffic corpus and commits a versioned catalog with the exact portal GUID for every approved source.

| Tier | Records | Purpose |
|---|---:|---|
| Pilot | 12 source records | Validate portal client, parser, and question taxonomy |
| v1 | 15–30 document/version records | Product corpus with meaningful evaluation |
| Expansion | Only after error analysis | Fill demonstrated evidence gaps |

The catalog stores both the expected project document ID and the portal-specific GUID. Ingestion never re-finds a source by title.

```yaml
snapshot_id: traffic-YYYY-MM-DD-v1
sources:
  - document_guid: "portal-guid"
    expected_document_id: "36/2024/QH15"
    expected_title: "Luật Trật tự, an toàn giao thông đường bộ"
    expected_public_url: "https://phapluat.gov.vn/<verified-public-document-page>"
    include: true
    review_status: approved
    curator_note: "Core road-safety law"
```

`blocked_no_structured_content` is a valid catalog status. Blocked entries cannot enter parsing, indexing, or evaluation.

## Fetch contract

For each approved catalog entry, the pipeline:

1. fetches detail by stored GUID with `tabName=noidung`;
2. stores exact bounded response bytes as content-addressed raw JSON in quarantine;
3. validates `success == true` and non-empty `data.docIdentity`, `data.docName`, and `data.docContent`, then requires `data.docIdentity` to equal the catalog's `expected_document_id`;
4. maps portal fields to canonical metadata;
5. converts `docContent` HTML to normalized text;
6. applies only catalogued, curator-approved literal corrections whose exact expected match count succeeds; and
7. parses and validates legal hierarchy.

Canonical metadata:

```json
{
  "document_id": "36/2024/QH15",
  "portal_document_guid": "...",
  "title": "...",
  "document_type": "law|decree|circular|decision|other",
  "issuer": "...",
  "issued_date": "YYYY-MM-DD|null",
  "effective_from": "YYYY-MM-DD|null",
  "effective_to": "YYYY-MM-DD|null",
  "status": "current|repealed|amended|unknown",
  "source_url": "https://phapluat.gov.vn/<verified-public-document-page>",
  "content_url": "https://phapluat.gov.vn/api/legal-documents/detail?...",
  "retrieved_at": "ISO-8601 UTC",
  "content_sha256": "...",
  "snapshot_id": "traffic-YYYY-MM-DD-v1"
}
```

`status` is a source signal, not a legal inference. Curator review is required before promoting critical validity mappings.

A title mismatch after whitespace normalization is held for curator review; it is never promoted automatically. A GUID may identify one document only when both the exact document identity check and catalog approval pass. `source_url` is the catalog's manually verified public page, not a URL pattern inferred from an undocumented API.

## Artifact model

```text
raw/{sha256}.json
receipts/{sha256}.json
normalized/{sha256}.txt
parsed/{document_id}__{snapshot_id}.json
relations/{snapshot_id}.json
manifests/{snapshot_id}.json
reports/{run_id}.json
```

- Raw bytes are immutable and deduplicated by SHA-256.
- The raw receipt records the first UTC retrieval timestamp for that raw hash. Rebuilds reuse it; a run timestamp never mutates a parsed artifact.
- Normalized text is reproducible from raw JSON, a normalizer version, and the versioned catalogued corrections. A correction preserves the raw bytes, states an HTTPS evidence URL and reason, and blocks ingestion if its literal match count changes.
- Parsed documents store parser version and stable unit IDs.
- A manifest contains only validated parsed artifacts; a raw fetch alone is not corpus membership.
- Schema-invalid raw responses remain quarantined for drift diagnosis and are never exposed as search or QA evidence.
- Quarantine is a run/manifest classification of the one immutable raw artifact, not a second copy of its bytes.
- Logical `document_id` and `unit_id` stay stable across refreshes; a graph import scopes their physical records by `snapshot_id`.

## Curated relation artifact

Cross-document legal relations are a separate reviewed dataset, analogous to the parsed-document artifacts. Portal fields such as `data.docRelateEffects` and `data.docListRelates` may nominate candidates, but neither field creates a public graph edge by itself.

```json
{
  "snapshot_id": "traffic-YYYY-MM-DD-v1",
  "relations": [
    {
      "relation_id": "traffic-...::amends::001",
      "relation_type": "AMENDS",
      "source": {
        "document_id": "168/2024/NĐ-CP",
        "unit_id": "168/2024/NĐ-CP::article::52::clause::1"
      },
      "target": {
        "document_id": "100/2019/NĐ-CP",
        "unit_id": "100/2019/NĐ-CP::article::1::clause::2a"
      },
      "effective_from": "2025-01-01",
      "effective_to": null,
      "evidence_unit_id": "168/2024/NĐ-CP::article::52::clause::1",
      "source_url": "https://phapluat.gov.vn/<verified-public-document-page>",
      "raw_sha256": "...",
      "review_status": "approved",
      "reviewed_at": "YYYY-MM-DD",
      "note": null
    }
  ]
}
```

Allowed `relation_type` values are `AMENDS`, `REPEALS`, `REPLACES`, and `REFERENCES`. `source.unit_id` and `target.unit_id` may be null only for a document-level relation; `evidence_unit_id`, `source_url`, and `raw_sha256` are required for every approved relation. The importer accepts only `approved` records whose referenced documents and units resolve inside the draft snapshot.

## Normalization and hierarchy

Normalization applies Unicode NFC, non-breaking-space cleanup, and deterministic block breaks. It preserves legal numbering, dates, and text; it never paraphrases.

The parser recognizes `Phần`, `Chương`, `Mục`, `Điều`, `Khoản`, and `Điểm`. Unit IDs follow this pattern:

```text
36/2024/QH15::article::11::clause::2::point::a
```

Validation rejects empty units, duplicate IDs, missing parents, and malformed paths. The parser never uses an LLM to fill missing legal structure.

## State machine

```text
catalogued → fetched → raw_stored → normalized → parsed → validated
→ manifested → embedded → indexed → smoke_tested → promoted
```

Failures record an error code, timestamp, and raw artifact when available. No partial snapshot can be promoted.

## Data quality report

Every run reports catalog counts, fetch and schema failures, document/article/clause/point counts, orphan or duplicate units, `unknown` validity count, relation review status, manifest hash, and parser/normalizer/schema versions.

## Non-structured content policy

The v1 ingestion contract accepts only complete readable structured HTML from the source. A response that does not satisfy this contract is blocked and reported; it is never converted into weaker evidence silently.

## Acceptance gates

- One saved portal fixture passes schema, normalization, and parser tests.
- Rebuilding from identical raw bytes yields identical hash and unit IDs.
- Every promoted document has public URL, raw hash, portal GUID, and curator status.
- A portal contract change fails before parsing and promotion.
