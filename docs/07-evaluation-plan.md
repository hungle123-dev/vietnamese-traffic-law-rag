# 07. Evaluation Plan

## Mục tiêu

Đo riêng từng tầng của hệ thống để biết lỗi nằm ở data, parser, retrieval, graph, generator hay vận hành. Không dùng một điểm LLM-as-a-judge duy nhất để kết luận hệ thống tốt.

## 1. Evaluation datasets

### 1.1 Gold QA set

Target cho đồ án: 300–500 câu hỏi tiếng Việt được review citation. Mỗi câu có:

- question;
- gold article/clause/point IDs;
- gold document/version;
- effective_at;
- answer hoặc answer key;
- question type;
- difficulty;
- reviewer status.

### 1.2 Taxonomy

| Type | Ví dụ khái quát |
|---|---|
| Definition | phương tiện/chủ thể/thuật ngữ là gì |
| Obligation | phải mang giấy tờ/trang bị gì |
| Prohibition | hành vi nào bị cấm |
| Penalty | hành vi bị xử phạt thế nào |
| Procedure | thủ tục/điều kiện thực hiện |
| Temporal | quy định có hiệu lực khi nào |
| Comparison | văn bản hiện tại khác bản cũ thế nào |
| Multi-document | cần luật + nghị định/hướng dẫn |
| Ambiguous | thiếu phương tiện/thời điểm/địa điểm |
| Out-of-domain | không thuộc traffic law |

### 1.3 Splits

- `train/dev/test` chỉ dùng nếu có model tuning.
- Với retrieval, test set phải giữ kín trước khi chọn model/threshold.
- Paraphrase cùng intent và cùng gold units phải nằm cùng split.
- Temporal test phải có cases current/repealed/amended.

## 2. Retrieval metrics

Với mỗi question, gold set là các legal units được reviewer xác nhận:

- `Recall@1`, `Recall@3`, `Recall@5`, `Recall@10`;
- `MRR`;
- `nDCG@k` nếu có graded relevance;
- document-level recall;
- unit-level recall;
- validity-aware recall;
- citation precision/recall.

Phải report micro và macro; macro tránh domain phổ biến lấn át các category khó.

## 3. Citation and legal correctness

### 3.1 Citation validity

```text
citation_exists
citation_in_evidence
citation_supports_claim
citation_has_correct_scope
citation_has_correct_version
```

### 3.2 Answer rubric

Mỗi mẫu được chấm 0–2 cho:

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Factual correctness | Sai | Một phần đúng | Đúng |
| Citation correctness | Sai/không có | Có nhưng thiếu | Đúng và đủ |
| Completeness | Thiếu nghiêm trọng | Thiếu chi tiết | Đủ cho câu hỏi |
| Validity awareness | Dùng sai version | Có warning nhưng chưa rõ | Xử lý đúng |
| Clarity | Khó hiểu | Chấp nhận được | Dễ hiểu |
| Abstention behavior | Đoán sai | Cảnh báo yếu | Từ chối đúng lúc |

Human reviewer nên là người hiểu pháp luật; nếu không có chuyên gia, ghi rõ reviewer limitation.

## 4. Generation metrics

- Exact match/ROUGE/BERTScore chỉ là supplementary vì long-form legal answer có nhiều cách diễn đạt.
- Groundedness: claim có evidence support.
- Citation coverage: tỷ lệ claim pháp lý có citation đúng.
- Citation precision: citation trả về có liên quan không.
- Unsupported claim rate.
- Abstention precision/recall.
- LLM-as-a-judge dùng rubric cố định, model/version cố định, chỉ là secondary signal.

## 5. System metrics

Mỗi run phải đo:

- p50/p95 latency theo stage;
- end-to-end latency;
- timeout/error rate;
- cache hit rate;
- token usage và estimated cost/query;
- embedding throughput;
- indexing time;
- ingest freshness;
- parser warning/failure rate;
- citation validation failure rate;
- abstention rate;
- active snapshot ID.

## 6. Required ablations

```text
A0: BM25 only
A1: Dense only
A2: BM25 + dense + RRF
A3: A2 + reranker
A4: A3 + hierarchy expansion
A5: A4 + amendment/version filtering
A6: A5 + query rewrite/expansion
A7: A5 + cache/production optimizations (quality unchanged target)
```

Mỗi ablation phải dùng cùng snapshot, question split, model và evaluator. Chỉ thay đúng component đang nghiên cứu.

## 7. Error analysis

Mỗi run lưu top candidates và phân loại lỗi:

1. gold không nằm trong candidate pool;
2. gold có nhưng rank thấp;
3. reranker làm tụt gold;
4. graph expansion thiếu hoặc thêm nhiễu;
5. validity filter sai;
6. generator không dùng evidence;
7. citation mapping lỗi;
8. câu hỏi mơ hồ nhưng hệ thống không hỏi lại.

Mục tiêu là chuyển mỗi failure thành một test case; không chỉ tối ưu aggregate metric.

## 8. Benchmark acceptance targets

Đây là ngưỡng đề xuất để quyết định v1, không phải cam kết kết quả trước khi đo:

- unit Recall@10 ≥ 0.80 trên gold set traffic;
- citation existence/resolve ≥ 0.98;
- citation correctness do reviewer đánh giá ≥ 0.90;
- unsupported claim rate ≤ 0.05 trên tập review;
- validity-aware accuracy được report riêng, không gộp vào answer score;
- p95 online request ≤ 15 giây với cấu hình demo;
- ingest run có thể tái lập và rollback.

Nếu không đạt, phải báo failure analysis thay vì nới threshold tùy ý.

## 9. Reproducibility

Mỗi evaluation result chứa:

```text
run_id
data_snapshot_id
index_version
question_set_version
retriever_config
reranker_config
generator_config
prompt_version
metric_version
git_commit
```

## 10. Assumptions

- 300 mẫu đủ cho baseline có ý nghĩa nhưng chưa đại diện toàn bộ traffic law.
- Human review tốn công nên ưu tiên citation/validity hơn văn phong.
- Metric threshold phải được điều chỉnh sau pilot, không lấy từ domain khác.

## 11. Failure modes

- Test leakage làm metric ảo.
- LLM judge bị bias theo văn phong.
- Gold annotation thiếu điều khoản thay thế.
- Recall cao nhưng context selection bỏ mất evidence.
- Đạt answer score nhưng citation không audit được.

## 12. Acceptance criteria

- Có một script/routine chạy được toàn bộ ablation matrix.
- Xuất bảng retrieval, citation, answer và latency.
- Có ít nhất 20 case error analysis thủ công.
- Kết quả có đủ version metadata để tái lập.
- Không báo một con số “accuracy” duy nhất như bằng chứng chất lượng pháp lý.
