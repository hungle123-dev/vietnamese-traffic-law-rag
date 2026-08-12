# 03. Data and Ingestion

## Mục tiêu

Định nghĩa nguồn dữ liệu, schema tối thiểu và pipeline ingest có thể tái lập, kiểm tra và cập nhật.

## 1. Data policy

Nguồn ưu tiên:

1. [Cơ sở dữ liệu quốc gia về pháp luật](https://vbpl.moj.gov.vn/pages/portal.aspx).
2. [Cổng Pháp luật quốc gia](https://phapluat.gov.vn/home).
3. [Hệ thống văn bản Chính phủ](https://vanban.chinhphu.vn/).

Mỗi record phải lưu nguồn gốc. Không lấy bài báo hoặc blog làm căn cứ pháp lý chính; chúng chỉ có thể là nguồn câu hỏi/metadata phụ.

## 2. Dataset tiers

| Tier | Corpus | QA/evaluation | Mục đích |
|---|---:|---:|---|
| Baseline | 12 văn bản traffic tham khảo, khoảng 7.500 node cấu trúc | 300 câu hỏi | Tái hiện và kiểm tra pipeline nền |
| Đồ án v1 | 15–30 document/version records, gồm luật, nghị định xử phạt và văn bản hướng dẫn liên quan | 300–500 câu hỏi, citation-level | Sản phẩm hoàn chỉnh có evaluation |
| Scale-up | Mở rộng các văn bản giao thông liên quan và lịch sử sửa đổi | 1.000+ câu hỏi hoặc active learning | Benchmark/stress test, chỉ làm khi v1 ổn định |

Các con số là mục tiêu engineering. Corpus phải được đóng băng trong `data_manifest.json`; không dùng “latest crawl” làm benchmark cố định.

## 3. Raw document record

```json
{
  "document_id": "36/2024/QH15",
  "title": "Luật Trật tự, an toàn giao thông đường bộ",
  "document_type": "law",
  "issuer": "Quốc hội",
  "issued_date": "2024-06-27",
  "effective_from": "2025-01-01",
  "effective_to": null,
  "status": "current",
  "source_url": "https://...",
  "retrieved_at": "2026-08-12T00:00:00Z",
  "content_sha256": "...",
  "snapshot_id": "traffic-2026-08-12-v1"
}
```

`status` không được suy ra chỉ từ `issued_date`; phải dùng thông tin hiệu lực, bãi bỏ, thay thế và review.

## 4. Legal unit record

```json
{
  "unit_id": "36/2024/QH15::article::11::clause::2",
  "document_id": "36/2024/QH15",
  "unit_type": "clause",
  "number": "2",
  "parent_id": "36/2024/QH15::article::11",
  "text": "...",
  "path": [
    "36/2024/QH15",
    "36/2024/QH15::article::11",
    "36/2024/QH15::article::11::clause::2"
  ],
  "validity": "current",
  "source_locator": {"page": null, "html_anchor": "..."},
  "parser_version": "parser-1"
}
```

## 5. Ingestion states

```text
discovered → fetched → hashed → parsed → normalized
→ relations_resolved → validated → embedded → indexed
→ smoke_tested → promoted
```

Lỗi ở bất kỳ state nào chuyển record/job sang `failed` với error code, retry count và artifact liên quan. Không xóa raw artifact khi parse lỗi.

## 6. Pipeline details

### 6.1 Discovery and fetch

- Lưu query/source URL và thời điểm discovery.
- Có timeout, retry exponential có giới hạn và user-agent hợp lệ.
- Kiểm tra content type, kích thước và encoding.
- Không vượt rate limit của nguồn.
- Gắn checksum sau khi tải.

### 6.2 Normalization

- Chuẩn hóa Unicode và whitespace.
- Giữ nguyên số hiệu, ngày tháng, ký hiệu điều/khoản/điểm.
- Loại bỏ boilerplate HTML nhưng giữ anchor/locator.
- Không paraphrase nội dung pháp luật trong raw/normalized source.

### 6.3 Hierarchy parsing

Parser ưu tiên deterministic rules/regex dựa trên cấu trúc văn bản. LLM không được dùng để quyết định số điều hoặc hierarchy trong đường ingest chính.

Validation tối thiểu:

- article number không trùng bất thường trong cùng document;
- parent path tồn tại;
- clause/point nằm trong đúng article/clause;
- text không rỗng;
- số lượng node và relation có report;
- lưu parser version.

### 6.4 Amendment/repeal resolution

Mỗi relation phải có:

```text
relation_type
source_document_id
target_document_id/unit_id
effective_from
provenance_url
confidence
review_status
```

Các quan hệ chưa xác minh dùng `unknown`/`candidate`, không được dùng để tự động loại bỏ văn bản current.

### 6.5 Embedding and indexing

- Batch embedding, retry theo batch.
- Embedding input gồm text pháp lý và metadata cần thiết, nhưng citation ID phải lưu riêng.
- Index phải ghi model name, dimension, normalization và snapshot ID.
- Build index mới ngoài active index.
- Chạy sample queries trước khi promote.

## 7. Data quality report

Mỗi ingest run phải xuất:

- số document discovered/fetched/failed;
- số article/clause/point;
- số node mồ côi;
- số text rỗng/trùng hash;
- số relation theo type;
- số record validity unknown;
- embedding/index failure;
- parser warnings;
- snapshot ID và manifest hash.

## 8. QA data collection

Nguồn câu hỏi:

- câu hỏi do người dùng/nhóm tự viết theo taxonomy;
- câu hỏi biến thể paraphrase có review;
- câu hỏi tham khảo từ consultation platform chỉ khi có quyền sử dụng và được kiểm tra lại;
- hard negatives: câu hỏi gần nghĩa nhưng khác phương tiện, hành vi, thời điểm hoặc văn bản.

Mỗi sample cần:

```json
{
  "question_id": "traffic-0001",
  "question": "...",
  "gold_unit_ids": ["..."],
  "gold_document_ids": ["..."],
  "answer": "...",
  "effective_at": "2026-08-12",
  "question_type": "penalty",
  "difficulty": "multi_document",
  "review_status": "reviewed"
}
```

## 9. Data leakage policy

- Không chia random các paraphrase cùng một câu hỏi sang train/test.
- Nếu dùng document version cũ/mới, phải đánh dấu quan hệ để không làm lộ answer qua duplicate text.
- Evaluation question không được sinh từ answer rồi đưa nguyên answer vào prompt/index như metadata.
- Report phải ghi rõ nguồn và thời điểm tạo QA.

## 10. Assumptions

- Phần lớn document là HTML/text; OCR PDF chỉ là fallback.
- Một số quan hệ sửa đổi cần human review.
- `effective_at` có thể null nếu câu hỏi chỉ hỏi lý thuyết; khi đó phải hiển thị snapshot date.

## 11. Failure modes

- Nguồn đổi HTML khiến scraper vẫn chạy nhưng parse sai.
- Văn bản hợp nhất che mất lịch sử version.
- Duplicate document được ingest thành hai node.
- Relation extraction tạo false positive.
- Embedding batch lỗi một phần nhưng index báo thành công.

## 12. Acceptance criteria

- Một run ingest mới có thể resume sau khi dừng giữa chừng.
- Raw artifact có hash và source URL.
- Parsed hierarchy pass validation fixtures.
- Index active trỏ duy nhất tới một snapshot đã smoke-test.
- Có thể rollback về index snapshot trước.
- Mọi relation amendment/repeal tự động đều có provenance và review status.
