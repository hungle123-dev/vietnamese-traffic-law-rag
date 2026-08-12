# 11. Architecture Decision Records

## Mục tiêu

Ghi lại các quyết định có ảnh hưởng lớn để tránh thay đổi stack theo cảm tính và giúp reviewer hiểu trade-off.

## ADR summary

| ID | Decision | Status |
|---|---|---|
| ADR-001 | Giới hạn domain ở pháp luật giao thông đường bộ Việt Nam | Accepted |
| ADR-002 | Legal unit có cấu trúc là retrieval/citation unit | Accepted |
| ADR-003 | Neo4j là graph và index store ban đầu | Accepted |
| ADR-004 | Hybrid BM25 + dense, fusion bằng RRF | Accepted |
| ADR-005 | Reranker là stage có benchmark/fallback, không bắt buộc mọi request | Accepted |
| ADR-006 | Validity là deterministic metadata/graph logic | Accepted |
| ADR-007 | Ingestion offline, snapshot và index promotion | Accepted |
| ADR-008 | Không dùng Agentic RAG mặc định | Accepted |
| ADR-009 | LLM generation có structured output và citation verifier | Accepted |
| ADR-010 | Evaluation lấy retrieval/citation làm metric chính | Accepted |

## ADR-001: Domain boundary

### Context

Pháp luật Việt Nam quá rộng, trong khi project cần một sản phẩm có dữ liệu và evaluation đủ sâu.

### Decision

Chỉ xử lý pháp luật giao thông đường bộ Việt Nam trong data manifest. Câu hỏi ngoài domain được reject hoặc chuyển clarification.

### Trade-off

Mất độ rộng nhưng có thể xây parser, version model, QA taxonomy và benchmark có ý nghĩa.

### Revisit when

Traffic domain đạt quality/coverage và có nguồn lực annotation cho domain mới.

## ADR-002: Structured legal unit

### Context

Chunk theo token có thể tách mất điều kiện, ngoại lệ và citation boundary.

### Decision

Article/clause/point là evidence unit; parent context chỉ được thêm có giới hạn.

### Trade-off

Parser phức tạp hơn, nhưng citation và hierarchy rõ hơn.

### Revisit when

Đánh giá cho thấy unit quá dài/nhỏ; khi đó thêm secondary window/chunk nhưng giữ canonical unit.

## ADR-003: Neo4j initially

### Context

Graph hierarchy/amendment là điểm khác biệt của product; tách nhiều database ngay làm tăng vận hành.

### Decision

Dùng Neo4j cho graph, metadata, full-text/vector trong v1; thiết kế index layer có thể thay adapter sau này.

### Alternatives

Qdrant + OpenSearch + Neo4j; PostgreSQL + pgvector; Elasticsearch duy nhất.

### Trade-off

Ít service và dễ đồng bộ snapshot; có thể kém hơn specialized stores khi corpus/throughput lớn.

### Revisit when

Load test hoặc corpus thực tế cho thấy p95/throughput không đạt.

## ADR-004: Hybrid retrieval + RRF

### Context

BM25 mạnh ở số hiệu/thuật ngữ; dense mạnh ở paraphrase. Raw scores khác scale.

### Decision

Chạy lexical và dense độc lập, hợp nhất bằng RRF, sau đó mới rerank.

### Trade-off

Tốn hai search nhưng dễ giải thích và ablate; RRF không học trọng số domain.

### Revisit when

Gold set đủ lớn để train/calibrate learning-to-rank hoặc weighted fusion.

## ADR-005: Selective reranking

### Context

Reranker tốn latency và chỉ sắp xếp candidate đã có.

### Decision

Rerank top candidate pool có giới hạn; fallback về fused rank khi model lỗi; benchmark tác động chất lượng.

### Trade-off

Có thể tăng precision nhưng tăng cost/latency và đôi khi làm xấu kết quả.

### Revisit when

Error analysis chứng minh reranker domain-specific đáng fine-tune.

## ADR-006: Deterministic validity

### Context

LLM/recency heuristic dễ sử dụng văn bản đã hết hiệu lực.

### Decision

Hiệu lực được quyết định từ metadata, effective dates và reviewed relations; `unknown` là trạng thái hợp lệ.

### Trade-off

Cần data curation/review, nhưng giảm hallucinated legal status.

### Revisit when

Có nguồn official structured validity đáng tin để tự động hóa thêm.

## ADR-007: Offline ingestion and snapshots

### Context

Fetch/parse/embed trong request path gây latency, lỗi khó rollback và không tái lập.

### Decision

Ingestion offline/resumable; raw immutable; build snapshot/index mới; smoke-test rồi promote.

### Trade-off

Dữ liệu không real-time từng giây, nhưng an toàn và debug được.

### Revisit when

Có yêu cầu freshness cao và nguồn có API/event ổn định.

## ADR-008: No default Agentic RAG

### Context

Pipeline traffic QA chủ yếu là retrieval có cấu trúc; agent loop có thể tăng cost và khó đánh giá.

### Decision

v1 dùng orchestrated fixed pipeline: rewrite → retrieve → rerank → graph → generate → verify. Chỉ thử agentic retrieval trong một experiment có benchmark riêng.

### Trade-off

Ít “agentic” hơn về marketing, nhưng deterministic và phù hợp use case.

### Revisit when

Câu hỏi multi-hop/multi-source có failure rate cao và agent có tool/điều kiện dừng rõ ràng.

## ADR-009: Structured generation and verifier

### Context

LLM output không đáng tin tuyệt đối, nhất là citation và validity.

### Decision

LLM trả claims + unit IDs theo schema; server resolve, check evidence membership và validity trước khi trả.

### Trade-off

Thêm code/latency nhỏ, đổi lại có safety boundary rõ.

### Revisit when

Có citation verifier model tốt hơn nhưng vẫn phải giữ resolver deterministic.

## ADR-010: Retrieval/citation-first evaluation

### Context

Answer fluency có thể che lỗi retrieval/citation.

### Decision

Report Recall/MRR/nDCG, citation precision/recall, validity accuracy, unsupported claim rate và latency; LLM judge chỉ secondary.

### Trade-off

Cần annotation thủ công, nhưng kết quả actionable hơn một điểm accuracy.

### Revisit when

Có benchmark chuyên gia lớn và rubric đã calibration.

## Assumptions

- Các ADR này là baseline v1, không phải cam kết không đổi.
- Mọi thay đổi phải cập nhật status, rationale và evaluation evidence.

## Failure modes

- Stack được thay đổi nhưng ADR không cập nhật.
- ADR dùng ngôn ngữ tuyệt đối dù benchmark đã thay đổi.
- “Production” được hiểu là cần microservices/Kubernetes dù chưa có trigger.

## Acceptance criteria

- Mọi quyết định lớn trong architecture có ADR tương ứng.
- Mỗi ADR nêu context, decision, alternatives, trade-off và revisit trigger.
- Khi benchmark thay đổi quyết định, ADR được cập nhật cùng report.
