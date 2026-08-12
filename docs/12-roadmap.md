# 12. Roadmap

## Mục tiêu

Chia project thành các mốc có thể demo và đánh giá, tránh xây toàn bộ hạ tầng trước khi biết retrieval có hoạt động.

## Phase 0: Research freeze

### Deliverables

- Product brief và scope.
- Data source policy.
- Corpus manifest v0.
- QA taxonomy và annotation guideline.
- ADR baseline.

### Exit criteria

- Domain và document list được supervisor/team duyệt.
- Có ít nhất 30 câu hỏi pilot với gold citation.

## Phase 1: Data foundation

### Deliverables

- Source client.
- Raw immutable storage.
- Deterministic parser.
- Hierarchy validation.
- Neo4j import.
- Data quality report.

### Exit criteria

- Rebuild cùng input tạo hierarchy/citation IDs ổn định.
- Parser fixtures pass.
- 12 baseline documents được ingest.

## Phase 2: Retrieval baseline

### Deliverables

- Article/clause/point search.
- BM25.
- Dense embedding.
- Retrieval-only API.
- Recall/MRR/nDCG evaluator.

### Exit criteria

- Có R0 BM25 và R1 dense report.
- Có error analysis candidate recall.

## Phase 3: Hybrid GraphRAG QA

### Deliverables

- RRF fusion.
- Reranker.
- Hierarchy/amendment expansion.
- Validity filtering.
- Grounded generator.
- Citation resolver/verifier.

### Exit criteria

- QA API trả answer + sources + warnings.
- Không trả citation không resolve.
- Có ablation R0–R5.

## Phase 4: Product hardening

### Deliverables

- Ingestion job state/retry/checkpoint.
- Snapshot promotion/rollback.
- Cache.
- Rate limit/timeout/fallback.
- Trace/metrics/cost logging.
- Streamlit/web UI.

### Exit criteria

- Demo chạy từ clean environment.
- Có fallback matrix và smoke test.
- Có p50/p95/cost report.

## Phase 5: Evaluation and portfolio release

### Deliverables

- 300–500 reviewed questions.
- Final ablation report.
- Error analysis.
- Architecture diagram.
- Demo video/screenshots.
- README setup/troubleshooting.
- Limitations and responsible-use statement.

### Exit criteria

- Người khác clone/chạy được theo README.
- Evaluation run tái lập được từ manifest/config.
- Có kết luận trung thực về điểm mạnh/yếu.

## Optional Phase 6: Agentic retrieval experiment

Chỉ thực hiện nếu Phase 3/5 chứng minh các query multi-document/multi-hop còn lỗi đáng kể.

Scope nhỏ:

- một planner/router;
- tools: exact lookup, hybrid search, graph traversal, validity check;
- tối đa 2–3 vòng retrieval;
- budget và stop condition rõ;
- so sánh với fixed pipeline trên cùng gold set.

Không merge vào default nếu chưa chứng minh quality/cost trade-off.

## Suggested weekly sequence

```text
Week 1: scope + source + QA guideline
Week 2: scraper/raw/manifest
Week 3: parser/graph/validation
Week 4: BM25/dense retrieval
Week 5: RRF/reranker/graph context
Week 6: generator/citation verifier
Week 7: evaluation/ablation
Week 8: API/UI/observability
Week 9: hardening/demo/reproducibility
```

## Risks by phase

| Risk | Detection | Response |
|---|---|---|
| Parser không ổn định | Fixtures/quality report | Sửa deterministic parser, không vội dùng LLM |
| Data thiếu quan hệ sửa đổi | Provenance review | Giảm claim validity hoặc thêm manual mapping |
| Dense không tốt tiếng Việt | Recall comparison | Giữ BM25/hybrid, benchmark model khác |
| Reranker làm xấu | Ablation | Tắt mặc định hoặc calibrate |
| QA annotation tốn thời gian | Pilot review | Ưu tiên citation/validity, giảm scope |
| Agent làm phức tạp | Cost/quality comparison | Giữ fixed pipeline |

## Acceptance criteria

- Mỗi phase có demo hoặc report độc lập.
- Không chuyển phase khi exit criteria chưa đạt chỉ vì muốn thêm feature.
- Optional agentic phase không ảnh hưởng v1 release.
