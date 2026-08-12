# 05. Retrieval and Reranking

## Mục tiêu

Thiết kế retrieval nhiều tầng để tối đa hóa recall ở candidate stage, sau đó cải thiện precision và legal context trước generation.

## 1. Retrieval contract

Input:

```text
question
conversation_context (optional)
effective_at (optional)
filters (optional)
```

Output mỗi candidate:

```json
{
  "unit_id": "...",
  "text": "...",
  "retriever": "bm25|dense|graph|...",
  "rank": 1,
  "score": 0.82,
  "document_id": "...",
  "validity": "current",
  "metadata": {}
}
```

Không để generator nhận candidate không có `unit_id`, snapshot hoặc validity metadata.

## 2. Query processing

### 2.1 Validation

- Giới hạn độ dài và số message.
- Chuẩn hóa Unicode/whitespace.
- Nhận diện câu hỏi rỗng, ngoài domain, prompt injection pattern.
- Giữ nguyên số hiệu, Điều, Khoản, Điểm, ngày tháng và tên phương tiện.

### 2.2 Query rewrite

Chỉ rewrite khi câu hỏi phụ thuộc lịch sử hội thoại hoặc có đại từ không rõ. Rewrite phải:

- giữ nguyên ý định;
- không thêm quy định chưa có trong input;
- trả về structured output;
- lưu `rewrite_version` và original query.

Nếu rewrite confidence thấp, search cả original và rewritten query.

### 2.3 Query expansion

Các dạng expansion có thể benchmark:

- synonym/abbreviation phương tiện;
- từ khóa pháp lý tương ứng với cách nói đời thường;
- số hiệu văn bản/điều khoản được trích xuất;
- sub-query theo thành phần: hành vi, chủ thể, phương tiện, hậu quả, thời điểm.

Không dùng expansion nếu nó làm mất từ khóa định danh. Lưu cả query gốc để tránh drift.

## 3. Metadata filtering

Filter trước ANN/search khi có thể:

```text
domain = traffic
document_type in allowed_types
document_id = exact match (nếu user nêu)
unit_type in article/clause/point
validity at effective_at
snapshot_id = active snapshot
```

Nếu filter quá chặt làm candidate rỗng, retry một lần với filter mềm hơn và gắn warning; không âm thầm trả “không có luật”.

## 4. First-stage retrieval

### 4.1 Lexical/BM25

BM25 bắt tốt:

- số hiệu văn bản;
- Điều/Khoản/Điểm;
- tên hành vi và thuật ngữ hiếm;
- mã phương tiện/mức phạt.

Đây là baseline bắt buộc vì BEIR cho thấy lexical retrieval vẫn bền và mạnh trong nhiều domain.

### 4.2 Dense retrieval

Embedding dùng để bắt semantic match giữa câu hỏi đời thường và văn bản pháp lý. Model phải được benchmark trên tiếng Việt và data domain; không mặc định model đa ngôn ngữ tốt nhất.

Candidate pool mặc định: dense top 20–50.

### 4.3 Graph lookup

Graph lookup phục vụ exact citation, hierarchy, validity và references. Graph không thay thế first-stage text retrieval.

## 5. Fusion

RRF là default vì không cần đưa raw score của BM25 và vector về cùng scale:

```text
RRF(d) = Σ_r 1 / (k + rank_r(d))
```

`k` và trọng số nếu có phải được lưu trong retrieval config. Cần so sánh thêm weighted score khi có lý do; không tune trên test set.

## 6. Reranking

Cross-encoder nhận query và candidate text để xếp lại candidate pool nhỏ. Reranker:

- không thể cứu document không nằm trong pool;
- cần giới hạn độ dài input;
- có thể lệch domain tiếng Việt;
- phải có fallback về fused ranking khi lỗi.

Heuristic legal signals chỉ dùng sau reranker và phải minh bạch:

- exact document/article match;
- validity hard filter hoặc penalty có giải thích;
- coverage của required entities;
- parent/child completeness.

Không dùng “newer document wins” như validity engine.

## 7. Graph context expansion

Sau rerank, với top evidence:

1. lấy parent article/chapter để hiểu ngữ cảnh;
2. lấy clause/point con nếu cần;
3. lấy sibling khi question đề cập danh sách/ngoại lệ;
4. lấy amendment/replacement neighbors nếu câu hỏi hỏi thời điểm;
5. deduplicate theo unit và giới hạn context.

Expansion được đánh giá bằng ablation; không mặc định lấy toàn bộ article/chapter.

## 8. Context selection

Context cuối phải:

- ưu tiên evidence trực tiếp;
- nhóm theo document và hierarchy;
- giữ citation marker bất biến;
- không quá 5–10 evidence units mặc định;
- có token budget riêng cho answer;
- không trộn current và repealed nếu không phục vụ câu hỏi lịch sử.

## 9. Retrieval confidence

Không dùng một score đơn độc làm xác suất. Response có thể có các signal:

```text
top_score
score_margin
candidate_count
exact_match_found
validity_known
retriever_agreement
reranker_fallback
```

Abstention policy kết hợp các signal này với threshold được calibrate trên validation set.

## 10. Retrieval evaluation matrix

| Run | Lexical | Dense | RRF | Rerank | Graph expansion | Validity |
|---|---:|---:|---:|---:|---:|---:|
| R0 | ✓ |  |  |  |  |  |
| R1 |  | ✓ |  |  |  |  |
| R2 | ✓ | ✓ | ✓ |  |  |  |
| R3 | ✓ | ✓ | ✓ | ✓ |  |  |
| R4 | ✓ | ✓ | ✓ | ✓ | ✓ |  |
| R5 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

## 11. Assumptions

- Corpus v1 đủ nhỏ để Neo4j full-text/vector đáp ứng benchmark.
- Reranker local có thể cần GPU hoặc precompute; API phải có fallback.
- Query expansion chỉ là candidate enhancement, không được coi là ground truth.

## 12. Failure modes

- Dense retrieval bỏ lỡ số hiệu chính xác.
- BM25 bỏ lỡ paraphrase đời thường.
- RRF đưa nhiều duplicate unit lên top.
- Reranker ưu tiên văn bản cũ vì lexical overlap.
- Graph expansion làm context vượt token budget.
- Query rewrite làm thay đổi chủ thể/phương tiện/thời gian.

## 13. Acceptance criteria

- Có baseline BM25 và dense độc lập.
- Hybrid run sử dụng RRF hoặc phương pháp fusion được ghi rõ.
- Reranker chỉ chạy trên candidate pool có giới hạn.
- Mọi candidate có citation ID và snapshot.
- Có fallback khi embedding/reranker/index lỗi.
- Có ablation report cho từng tầng.
