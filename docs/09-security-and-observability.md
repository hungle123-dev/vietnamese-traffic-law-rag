# 09. Security and Observability

## Mục tiêu

Bảo vệ hệ thống khỏi prompt injection, data poisoning, abuse và lỗi khó quan sát; đồng thời đo được chất lượng, latency và chi phí.

## 1. Threat model

| Threat | Vector | Impact | Control |
|---|---|---|---|
| Prompt injection | User/document text | LLM bỏ policy, leak prompt | Tách instruction/data, output validation, allowlist |
| Citation injection | Document chứa fake marker | Citation giả | Server-generated IDs, resolver |
| Data poisoning | Raw source/parser relation sai | Trả luật sai | Official source, hash, review, promotion gate |
| Query injection | Text-to-Cypher/arbitrary filter | Data access/DoS | Không expose, read-only allowlist, limits |
| Denial of service | Query dài, repeated LLM calls | Tốn cost/latency | Body/rate/concurrency limits, cache |
| Secret leakage | Logs/prompts/errors | Credential compromise | Secret manager/env, redaction |
| Stale index | Data cập nhật nhưng index cũ | Answer outdated | Snapshot/version check, freshness metric |
| Model/provider outage | External dependency | Không trả answer | Timeout, retry, fallback search/abstain |
| PII exposure | User includes personal data | Privacy risk | Minimize storage, redact logs, retention policy |

## 2. Prompt injection controls

- User query, conversation và legal text phải là data fields, không concatenate thành system instruction.
- Giới hạn độ dài và loại control characters.
- Không cho document content thực thi tool call.
- LLM tools chỉ read-only và allowlist.
- Validator kiểm tra output schema, citation membership và forbidden content.
- Có test cases “ignore previous instructions”, fake citation và malicious legal text.

## 3. Data integrity controls

- Raw content checksum.
- Immutable snapshot artifact.
- Parser version và relation provenance.
- Manual review cho amendment/repeal critical edges.
- Index promotion chỉ sau smoke tests.
- Không sửa trực tiếp active index; build/promote/rollback.

## 4. Observability events

### Request event

```text
trace_id
request_id
timestamp
client_class
query_hash
input_length
snapshot_id
index_version
retrieval_config
prompt_version
model_name
status
abstain
```

### Stage timings

```text
validation_ms
rewrite_ms
filter_ms
lexical_ms
dense_ms
fusion_ms
rerank_ms
graph_ms
generation_ms
citation_verify_ms
total_ms
```

Không log raw question/answer mặc định. Debug mode phải explicit và redaction.

## 5. Metrics

### Product/quality

- questions per day;
- abstention rate;
- citation validation failure rate;
- user feedback/flag rate;
- answer acceptance nếu có feedback.

### Retrieval

- candidate count;
- retriever agreement;
- top score/margin;
- Recall@k từ evaluation runs;
- reranker fallback rate.

### Reliability

- API error rate;
- timeout rate;
- dependency health;
- ingestion failure rate;
- active snapshot age;
- index promotion/rollback count.

### Cost

- input/output tokens;
- estimated cost/request;
- embedding batch cost/time;
- cache hit rate;
- cost by endpoint/model.

## 6. Alerts

Alert tối thiểu:

- active snapshot quá cũ so với update policy;
- citation validation failure tăng đột biến;
- p95 latency vượt target;
- LLM timeout/rate limit;
- ingest/parser failure;
- cost/request vượt budget;
- index readiness false.

## 7. Logging and retention

- Structured JSON logs.
- Secret/token được redact.
- Raw legal document retention theo data policy; QA/evaluation có version.
- Query log dùng hash nếu không cần lưu nội dung.
- Xóa/ẩn PII trong câu hỏi khi phát hiện.

## 8. Fallback behavior

| Failure | Fallback |
|---|---|
| LLM down | Trả retrieved sources + thông báo không sinh được answer |
| Reranker down | Dùng RRF/fused ranking |
| Dense index down | BM25 + graph exact lookup |
| BM25 down | Dense + graph, warning |
| Cache down | Bỏ qua cache, tiếp tục request |
| Graph down | Search text nhưng không claim validity/relationship đầy đủ |
| Citation validator down | Không trả generated answer; trả safe error hoặc sources |

## 9. Assumptions

- Local demo có thể dùng log file; deployment thật nên đưa metrics vào Prometheus-compatible system.
- Không cần full SIEM/Kubernetes observability ở v1.
- Security của legal truth quan trọng hơn việc thêm tool agent.

## 10. Failure modes

- Logging debug vô tình lưu PII.
- Metrics không gắn snapshot nên không phân biệt lỗi data/model.
- Fallback trả answer cũ từ cache sau khi index đổi.
- Alert quá nhiều khiến operator bỏ qua cảnh báo quan trọng.

## 11. Acceptance criteria

- Mỗi request có trace ID và stage timings.
- Có thể truy nguyên answer về snapshot/index/model/prompt.
- Có rate limit và body limit.
- Có kiểm thử prompt injection và malformed output.
- Có fallback documented cho từng dependency chính.
