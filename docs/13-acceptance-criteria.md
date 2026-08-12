# 13. Acceptance Criteria

## Mục tiêu

Checklist nghiệm thu sản phẩm v1 theo bốn nhóm: data, AI quality, product/API và operations.

## 1. Data and ingestion

- [ ] Có data manifest ghi rõ document ID, source URL, retrieved time và hash.
- [ ] Raw document được lưu immutable hoặc có version.
- [ ] Ingestion có state, retry và resume.
- [ ] Parser tạo đúng document/part/chapter/section/article/clause/point trên fixture.
- [ ] Không có hierarchy cycle hoặc orphan node ngoài các case được ghi nhận.
- [ ] Mỗi parsed unit có stable `unit_id`.
- [ ] Mỗi amendment/repeal/replacement edge có provenance và review status.
- [ ] Index được build từ snapshot cụ thể.
- [ ] Có smoke test trước promote và rollback sau promote.

## 2. Retrieval and graph

- [ ] BM25 baseline chạy được.
- [ ] Dense baseline chạy được.
- [ ] Hybrid fusion được cấu hình và log.
- [ ] RRF hoặc fusion method có unit test.
- [ ] Reranker candidate pool có giới hạn và fallback.
- [ ] Graph expansion có depth/limit.
- [ ] Validity query trả `true/false/unknown`.
- [ ] Current/repealed/amended cases có test.
- [ ] Retrieval-only API trả rank, score, unit ID và snapshot.

## 3. Generation and citation

- [ ] LLM chỉ nhận evidence được chọn.
- [ ] Output được parse/schema validate.
- [ ] Citation ID không tồn tại bị reject.
- [ ] Citation ngoài evidence bị reject.
- [ ] Claim không support bị repair an toàn hoặc abstain.
- [ ] Không khẳng định current khi validity unknown.
- [ ] Có clarification cho câu hỏi thiếu biến quan trọng.
- [ ] Có out-of-domain response.
- [ ] Có prompt injection regression cases.
- [ ] Có prompt version và golden cases.

## 4. Evaluation

- [ ] Có QA gold set tối thiểu 300 câu cho target đồ án, hoặc ghi rõ limitation nếu chưa đủ.
- [ ] Gold labels ở article/clause/point level.
- [ ] Có test split không leakage.
- [ ] Report Recall@1/3/5/10, MRR và nDCG nếu áp dụng.
- [ ] Report citation precision/recall và validity-aware metric.
- [ ] Report unsupported claim rate và abstention behavior.
- [ ] Có ablation BM25/dense/hybrid/RRF/reranker/graph/validity.
- [ ] Có ít nhất 20 lỗi được phân tích thủ công.
- [ ] LLM-as-a-judge không phải metric duy nhất.
- [ ] Run lưu snapshot/model/prompt/config/commit.

## 5. API and product

- [ ] `GET /health` và `GET /ready` hoạt động.
- [ ] `POST /api/v1/qa` trả answer, claims, sources, warnings và metadata.
- [ ] `POST /api/v1/search` không gọi generation.
- [ ] Error response có code và trace ID.
- [ ] API input có length/rate/concurrency limits.
- [ ] UI hiển thị nguồn và disclaimer.
- [ ] UI thể hiện rõ answer abstain/low confidence.
- [ ] Client không thể gọi arbitrary Cypher.

## 6. Operations and security

- [ ] Timeout/retry/circuit breaker hoặc fallback cho LLM.
- [ ] Dense/reranker/cache/graph failure có degradation path.
- [ ] Token usage và estimated cost được log.
- [ ] Stage latency được log.
- [ ] Query/PII redaction policy được áp dụng.
- [ ] Secret không nằm trong repository hoặc log.
- [ ] Có snapshot/index rollback.
- [ ] Có README chạy dev/eval/demo từ clean environment.
- [ ] Có Docker Compose hoặc deployment path được kiểm thử.

## 7. Portfolio/demo acceptance

- [ ] Demo trả lời được các câu hỏi traffic phổ biến với citation.
- [ ] Demo cho thấy một câu hỏi cần nhiều văn bản.
- [ ] Demo cho thấy current/repealed hoặc effective date.
- [ ] Demo cho thấy câu hỏi mơ hồ được hỏi lại.
- [ ] Demo cho thấy câu hỏi ngoài domain bị từ chối.
- [ ] Có architecture diagram và data flow.
- [ ] Có bảng ablation trước/sau.
- [ ] README nói rõ giới hạn và không claim tư vấn pháp lý.

## 8. Release gate

Chỉ gọi là `v1` khi tất cả mục MUST ở nhóm data, retrieval, generation, evaluation và security đã được đánh dấu hoặc có waiver viết rõ lý do. Các feature như Qdrant, multi-agent, Kubernetes và full-domain expansion không phải release gate.
