# 08. API Specification

## Conventions

- Base path: /api/v1.
- JSON uses UTF-8; timestamps use ISO-8601 UTC.
- Every response contains trace_id.
- Public endpoints are read-only.
- Ingestion and evaluation endpoints are operator-only.
- The implementation-generated OpenAPI document is the executable contract; this document defines the intended surface before code exists.

## Endpoint inventory

| Method | Path | Audience | Purpose |
|---|---|---|---|
| GET | /health | Internal | Process liveness |
| GET | /ready | Internal | Active snapshot and dependency readiness |
| POST | /api/v1/qa | User | Grounded legal answer |
| POST | /api/v1/search | User/researcher | Retrieval inspection without generation |
| GET | /api/v1/documents?document_id={document_id} | User | Document metadata and hierarchy summary |
| GET | /api/v1/units?unit_id={unit_id} | User | Exact unit, parents, validity, and citation |
| POST | /api/v1/ingestion/runs | Operator | Build or resume a curated snapshot |
| GET | /api/v1/ingestion/runs/{run_id} | Operator | Run state and quality report |
| POST | /api/v1/evaluation/runs | Researcher | Evaluate a pinned configuration |
| GET | /api/v1/evaluation/runs/{run_id} | Researcher | Result and artifacts |

## QA request

    POST /api/v1/qa

    {
      "question": "Đi xe máy vượt đèn đỏ bị xử lý như thế nào?",
      "conversation": [],
      "effective_at": "2026-08-12",
      "options": {
        "top_k": 5
      }
    }

Rules:

- question is required, non-empty, and length-limited;
- effective_at is optional; null means use the active snapshot date and state it in the response;
- clients cannot choose unpublished snapshots;
- top_k has a server-side upper bound.

## QA response

    {
      "request_id": "qa_...",
      "trace_id": "trace_...",
      "answer": "...",
      "claims": [
        {
          "text": "...",
          "citations": [
            {
              "unit_id": "36/2024/QH15::article::...",
              "snapshot_id": "traffic-...",
              "label": "36/2024/QH15, Điều ...",
              "source_url": "https://phapluat.gov.vn/<verified-public-document-page>"
            }
          ]
        }
      ],
      "sources": [],
      "warnings": [],
      "needs_clarification": false,
      "abstain": false,
      "confidence_label": "medium",
      "metadata": {
        "snapshot_id": "traffic-...",
        "index_version": "idx-...",
        "prompt_version": "qa-v1",
        "latency_ms": 0
      }
    }

Sources are evidence used in the answer, not every retrieval candidate.

## Search request

    POST /api/v1/search

    {
      "query": "giấy tờ người điều khiển xe máy phải mang",
      "effective_at": "2026-08-12",
      "filters": {
        "document_type": ["law", "decree"]
      },
      "top_k": 10
    }

The response includes candidate unit ID, document ID, ranks and scores by retriever, fused/rerank score when available, validity, and source locator. It never calls generation.

## Document and unit endpoints

Use query parameters because document and unit IDs contain `/` and `::`:

    GET /api/v1/documents?document_id=36%2F2024%2FQH15
    GET /api/v1/units?unit_id=36%2F2024%2FQH15%3A%3Aarticle%3A%3A11&effective_at=2026-08-12

Both endpoints read the active promoted snapshot only. Document lookup returns canonical metadata, source URL, status, effective dates, hierarchy summary, and reviewed relations.

Unit lookup returns normalized legal text, parent chain, bounded children when requested, validity at a date, and citation metadata.

Neither endpoint represents unreviewed relations as fact.

## Operator ingestion endpoint

    POST /api/v1/ingestion/runs

    {
      "catalog_version": "traffic-...",
      "document_guids": ["..."],
      "mode": "build",
      "idempotency_key": "..."
    }

Only catalog GUIDs may be requested. The service does not accept arbitrary URLs or a free-text bulk crawl request.

## Error shape

    {
      "type": "https://project/errors/validation",
      "title": "Invalid request",
      "status": 422,
      "code": "QUESTION_TOO_LONG",
      "detail": "Question exceeds the allowed length.",
      "trace_id": "trace_..."
    }

Minimum codes:

    QUESTION_EMPTY
    QUESTION_TOO_LONG
    OUT_OF_DOMAIN
    SNAPSHOT_NOT_READY
    RETRIEVAL_FAILED
    GENERATION_TIMEOUT
    OUTPUT_VALIDATION_FAILED
    CITATION_VALIDATION_FAILED
    RATE_LIMITED
    INGESTION_CONFLICT
    PORTAL_SCHEMA_CHANGED

## Authorization and limits

Local demo may leave QA and search unauthenticated. Operator ingestion and evaluation must require an API key or private network boundary. Apply body, rate, concurrency, and timeout limits to public requests.

No endpoint exposes arbitrary Cypher, raw database credentials, or unrestricted source fetches.

## Streaming

Streaming is deferred until citation validation is stable. If added, only a validated final event is authoritative.
