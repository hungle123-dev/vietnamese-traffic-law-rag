# 01. Scope and Requirements

## Mục tiêu

Chuyển product brief thành yêu cầu có thể triển khai và kiểm thử.

## 1. Scope statement

Hệ thống phục vụ tra cứu pháp luật giao thông đường bộ Việt Nam trong một corpus có version. Đơn vị bằng chứng nhỏ nhất là **point** nếu văn bản có point; nếu không, **clause** hoặc **article**. Hệ thống không tự mở rộng sang domain ngoài data manifest.

## 2. Use cases

### UC-01: Hỏi quy định

Người dùng nhập câu hỏi; hệ thống trả lời, sources, thời điểm áp dụng và cảnh báo.

### UC-02: Tra cứu điều khoản trực tiếp

Người dùng nhập số hiệu văn bản, số điều/khoản; hệ thống trả nguyên văn đã chuẩn hóa và vị trí trong hierarchy.

### UC-03: Hỏi theo tình huống

Ví dụ: loại phương tiện, hành vi, địa điểm, thời điểm, giấy tờ. Hệ thống tìm các điều khoản có thể liên quan và nêu điều kiện/ngoại lệ.

### UC-04: Kiểm tra hiệu lực

Người dùng hỏi quy định hiện tại hoặc tại một ngày cụ thể. Hệ thống dùng validity metadata và amendment graph để trả kết luận có căn cứ.

### UC-05: So sánh phiên bản

Hiển thị điều khoản hiện tại và phiên bản trước nếu có quan hệ sửa đổi/thay thế được xác minh.

### UC-06: Ingest/update corpus

Operator chạy discovery hoặc ingest một nguồn mới. Job phải idempotent, có trạng thái, log, lỗi và khả năng tiếp tục.

### UC-07: Đánh giá pipeline

Researcher chạy một evaluation run với snapshot, model config, prompt version và metric version cụ thể.

## 3. Functional requirements

| ID | Requirement | Priority | Verification |
|---|---|---:|---|
| FR-01 | Nhận câu hỏi tiếng Việt qua API/UI | MUST | API/integration test |
| FR-02 | Validate độ dài, encoding và input hợp lệ | MUST | Unit test |
| FR-03 | Giới hạn domain ở traffic law | MUST | Routing test |
| FR-04 | Hỗ trợ query rewrite cho hội thoại ngắn | SHOULD | Golden tests |
| FR-05 | Tìm kiếm keyword/BM25 | MUST | Retrieval benchmark |
| FR-06 | Tìm kiếm dense embedding | MUST | Retrieval benchmark |
| FR-07 | Hợp nhất bằng RRF | SHOULD | Ablation |
| FR-08 | Cross-encoder reranking top candidates | SHOULD | Ablation/latency |
| FR-09 | Graph expansion parent/child/sibling/amendment | MUST | Graph tests |
| FR-10 | Lọc theo validity và effective date | MUST | Temporal test set |
| FR-11 | Trả citation ở article/clause/point level | MUST | Citation tests |
| FR-12 | Abstain khi evidence không đạt ngưỡng | MUST | Abstention test set |
| FR-13 | Validate output LLM theo schema | MUST | Malformed-output test |
| FR-14 | Cache query/retrieval/embedding phù hợp | SHOULD | Cache integration test |
| FR-15 | Ingest raw source, metadata và parsed hierarchy | MUST | Fixture tests |
| FR-16 | Job có retry, checkpoint, dedup và report | MUST | Failure injection test |
| FR-17 | Ghi lại data/model/prompt/index version | MUST | Trace inspection |
| FR-18 | Có endpoint health/readiness | MUST | API test |
| FR-19 | Có evaluation runner và export kết quả | MUST | Reproducibility test |
| FR-20 | UI hiển thị answer, sources, warnings | SHOULD | Manual acceptance |

## 4. Non-functional requirements

### Correctness and safety

- Không claim pháp lý nếu không có source được truy hồi.
- Không cho LLM tự tạo citation không tồn tại.
- Citation được kiểm tra lại với evidence store trước khi trả.
- Văn bản `unknown` validity phải được gắn warning, không được tự coi là current.

### Performance targets

Đây là mục tiêu thiết kế cần benchmark, không phải SLA đã cam kết:

- p50 end-to-end không quá 5 giây với hosted LLM;
- p95 không quá 15 giây trong local/single-node demo;
- retrieval trước generation dưới 1 giây cho corpus v1;
- rerank candidate pool được giới hạn, mặc định 20–50 item;
- context gửi LLM tối đa 5–10 evidence unit sau khi chọn lọc.

### Reliability

- LLM call có timeout, retry có giới hạn và circuit breaker/fallback.
- Ingestion lỗi một document không làm mất raw data hoặc dừng toàn bộ job.
- Index build có version; chỉ promote index khi validation pass.

### Reproducibility

Mỗi evaluation/run phải lưu:

```text
data_snapshot_id
index_version
embedding_model
reranker_model
llm_model
prompt_version
retrieval_config
timestamp
```

### Privacy and security

- Không yêu cầu dữ liệu cá nhân để hỏi luật.
- Log phải redact câu hỏi nếu có khả năng chứa thông tin nhạy cảm.
- Tool/DB access của LLM chỉ read-only và allowlist.

## 5. User-facing response contract

Một câu trả lời tốt có các phần:

1. Kết luận trực tiếp.
2. Điều kiện hoặc ngoại lệ quan trọng.
3. Căn cứ pháp lý có citation.
4. Trạng thái hiệu lực và thời điểm dữ liệu.
5. Cảnh báo nếu câu hỏi thiếu thông tin hoặc hệ thống không đủ evidence.

## 6. Assumptions

- Không cần authentication phức tạp trong local demo; production-like deployment vẫn phải có rate limit.
- Query language chính là tiếng Việt; có thể từ chối câu hỏi ngoài domain.
- Chưa cần real-time crawling; cập nhật theo job theo lịch hoặc operator trigger là đủ.

## 7. Failure modes

- Câu hỏi có nhiều hành vi/phương tiện nhưng decomposition sai.
- Số văn bản viết sai khiến exact lookup thất bại.
- Một điều có nhiều bản hợp nhất; hệ thống hiển thị nhầm version.
- Reranker làm tụt kết quả đúng do model lệch domain.
- Cache trả câu trả lời cũ sau khi promote data snapshot mới.

## 8. Acceptance criteria

- Mọi FR MUST có ít nhất một test hoặc checklist kiểm chứng.
- Không có requirement nào yêu cầu “LLM phải luôn trả lời”; hệ thống được phép abstain.
- Scope không chứa contract review, general legal advice hoặc multi-agent tự trị.
