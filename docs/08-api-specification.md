# 08. API Specification

## Mục tiêu

Định nghĩa API contract ổn định cho UI, evaluator và các client khác. API v1 ưu tiên response có citation, traceability và lỗi có cấu trúc.

## 1. API conventions

- Base path: `/api/v1`.
- JSON UTF-8.
- Thời gian dùng ISO-8601 UTC.
- `trace_id` có trong response và log.
- API không expose raw database credentials hoặc Cypher tùy ý.
- Public question endpoint có rate limit; ingestion/evaluation endpoint là internal.

## 2. Endpoint inventory

| Method | Path | Audience | Purpose |
|---|---|---|---|
| GET | `/health` | internal | Process liveness |
| GET | `/ready` | internal | Index/model dependency readiness |
| POST | `/api/v1/qa` | user | Grounded legal answer |
| POST | `/api/v1/search` | user/researcher | Retrieval-only inspection |
| GET | `/api/v1/documents/{document_id}` | user | Document metadata/hierarchy |
| GET | `/api/v1/units/{unit_id}` | user | Exact legal unit and citation |
| POST | `/api/v1/ingestion/runs` | operator | Start/resume ingest |
| GET | `/api/v1/ingestion/runs/{run_id}` | operator | Job status/report |
| POST | `/api/v1/evaluation/runs` | researcher | Start evaluation |
| GET | `/api/v1/evaluation/runs/{run_id}` | researcher | Evaluation result |

## 3. `POST /api/v1/qa`

### Request

```json
{
  "question": "Đi xe máy vượt đèn đỏ bị xử lý như thế nào?",
  "conversation": [],
  "effective_at": "2026-08-12",
  "snapshot_id": null,
  "options": {
    "include_history": false,
    "stream": false,
    "top_k": 5
  }
}
```

Rules:

- `question` bắt buộc, non-empty, length limit.
- `effective_at` optional; nếu null dùng active snapshot date và phải hiển thị.
- Client không được tự chọn snapshot chưa public; researcher/internal endpoint mới được pin snapshot.
- `top_k` có upper bound server-side.

### Response

```json
{
  "request_id": "qa_01H...",
  "trace_id": "trace_01H...",
  "answer": "...",
  "claims": [
    {
      "text": "...",
      "citations": [
        {
          "unit_id": "168/2024/NĐ-CP::article::6::clause::...",
          "label": "Nghị định 168/2024/NĐ-CP, Điều 6",
          "source_url": "https://..."
        }
      ]
    }
  ],
  "sources": [],
  "warnings": [],
  "abstain": false,
  "confidence_label": "medium",
  "metadata": {
    "snapshot_id": "traffic-2026-08-12-v1",
    "index_version": "idx-...",
    "prompt_version": "qa-v1",
    "latency_ms": 1234
  }
}
```

`sources` chứa evidence đã dùng, không phải toàn bộ candidates. Có thể thêm `debug` chỉ khi caller là researcher và server bật flag.

## 4. `POST /api/v1/search`

Dùng để debug/evaluate retrieval, không gọi generation.

```json
{
  "query": "giấy tờ người điều khiển xe máy phải mang",
  "effective_at": "2026-08-12",
  "filters": {"document_type": ["law", "decree"]},
  "retrieval_config": "hybrid-default",
  "top_k": 10
}
```

Response phải trả candidate ID, rank từng retriever, fused score, rerank score nếu có, validity và citation locator.

## 5. Document and unit endpoints

`GET /documents/{document_id}` trả metadata, status, effective dates, source URL, hierarchy summary và amendment neighbors đã xác minh.

`GET /units/{unit_id}` trả text, parent chain, child units, validity, source locator và citation label.

Không trả raw content ngoài snapshot hoặc quan hệ chưa được review như thể đã verified.

## 6. Ingestion endpoints

`POST /ingestion/runs` là internal:

```json
{
  "source": "official_portal",
  "query": "giao thông đường bộ",
  "document_ids": [],
  "mode": "discover|refresh|reindex",
  "idempotency_key": "..."
}
```

Job response:

```json
{
  "run_id": "ing_01H...",
  "status": "queued",
  "snapshot_id": null,
  "created_at": "..."
}
```

Cùng `idempotency_key` không được tạo duplicate run.

## 7. Evaluation endpoints

Internal endpoint nhận question set version, data snapshot, retrieval/generation config và output path. Result phải lưu run metadata theo [07-evaluation-plan.md](07-evaluation-plan.md).

## 8. Error model

Dùng error shape tương đương RFC 7807:

```json
{
  "type": "https://example/errors/validation",
  "title": "Invalid request",
  "status": 422,
  "code": "QUESTION_TOO_LONG",
  "detail": "Question exceeds the allowed length.",
  "trace_id": "trace_01H..."
}
```

Các code tối thiểu:

```text
QUESTION_EMPTY
QUESTION_TOO_LONG
OUT_OF_DOMAIN
INDEX_NOT_READY
RETRIEVAL_FAILED
GENERATION_TIMEOUT
OUTPUT_VALIDATION_FAILED
CITATION_VALIDATION_FAILED
RATE_LIMITED
INGESTION_CONFLICT
```

Không expose stack trace cho client.

## 9. Streaming

SSE có thể dùng cho UI chat sau khi retrieval/citation policy đã ổn định. Stream event nên gồm `status`, `token`, `sources`, `final`, `error`. Final event vẫn phải là structured response đã validate; không coi text đang stream là kết quả đã kiểm chứng.

## 10. Authentication and rate limits

- Local demo có thể không auth cho `qa/search`.
- Internal ingestion/evaluation bắt buộc API key hoặc network protection.
- Rate limit theo client/IP; giới hạn request body.
- Không cho user gọi text-to-Cypher hoặc arbitrary graph query.

## 11. Assumptions

- OpenAPI được sinh từ schema implementation nhưng file docs này là contract trước code.
- UI chỉ cần `qa`, `search`, `documents`, `units` trong v1.
- Snapshot promotion do operator/worker thực hiện, không từ user endpoint.

## 12. Failure modes

- Response thiếu trace ID khiến không debug được.
- Client nhận source nhưng source không thuộc evidence.
- Job retry tạo duplicate snapshot.
- Streaming token đã hiển thị nhưng final validation fail.
- Error message làm lộ provider/secret.

## 13. Acceptance criteria

- Có OpenAPI document tương ứng khi implementation bắt đầu.
- Mọi endpoint public có request/response/error example.
- Citation object resolve được bằng unit endpoint.
- Internal endpoints được phân quyền và rate limit.
- Contract test bắt được breaking change trong `/api/v1`.
