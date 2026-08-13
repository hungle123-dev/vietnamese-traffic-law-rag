# Documentation map

Đây là blueprint chuẩn của sản phẩm. Tài liệu mô tả **mục tiêu thiết kế**, không tuyên bố tính năng đã được triển khai. README và bản đồ này dùng tiếng Việt; các contract đánh số dùng tiếng Anh để coding agent và technical reviewer có thể dùng trực tiếp.

| # | Document | Quyết định chính |
|---:|---|---|
| 00 | [Product brief](00-product-brief.md) | Sản phẩm, user và giá trị |
| 01 | [Scope and requirements](01-scope-and-requirements.md) | Ranh giới v1 và yêu cầu kiểm thử được |
| 02 | [System architecture](02-system-architecture.md) | Modular monolith và source layout dự kiến |
| 03 | [Data and ingestion](03-data-and-ingestion.md) | API/HTML-first, catalog duyệt thủ công |
| 04 | [Knowledge graph model](04-knowledge-graph-model.md) | Graph pháp lý xác định, version-aware |
| 05 | [Retrieval and reranking](05-retrieval-and-reranking.md) | BM25 + dense + RRF + selective rerank |
| 06 | [Generation and citation policy](06-generation-and-citation-policy.md) | Grounding, verifier và abstention |
| 07 | [Evaluation plan](07-evaluation-plan.md) | Retrieval/citation-first benchmark |
| 08 | [API specification](08-api-specification.md) | Contract public và operator API |
| 09 | [Security and observability](09-security-and-observability.md) | Integrity, prompt safety và traceability |
| 10 | [Deployment plan](10-deployment-plan.md) | Local → demo deployment, không overbuild |
| 11 | [Architecture decisions](11-adr.md) | Trade-off đã chấp nhận |
| 12 | [Roadmap](12-roadmap.md) | Gate theo phase |
| 13 | [Acceptance criteria](13-acceptance-criteria.md) | Điều kiện hoàn thành v1 |
| 14 | [Implementation blueprint](14-implementation-blueprint.md) | Thứ tự file/module khi bắt đầu code |
| 15 | [Candidate seed catalog](15-candidate-seed-catalog.md) | Danh sách pilot độc lập, chờ duyệt trước khi tạo data |

## Non-negotiable decisions

1. Corpus chỉ gồm văn bản giao thông được tuyển chọn; không crawl hàng loạt toàn bộ portal.
2. Nguồn ingest là API/HTML có cấu trúc từ Cổng Pháp luật quốc gia; response không đạt contract bị block.
3. Raw portal response, normalized text, parsed hierarchy và index version là các artifact tách biệt.
4. LLM không quyết định hierarchy, hiệu lực, citation hay ghi dữ liệu pháp lý.
5. Modular monolith trước; chỉ tách service/database khi benchmark chứng minh cần.

## Research references

- [NLP-LegalQA reference repository](https://github.com/n3sfan/NLP-LegalQA)
- [Cổng Pháp luật quốc gia](https://phapluat.gov.vn/he-thong-van-ban-phap-luat)
- [Vietnamese Legal QA, COLING 2020](https://aclanthology.org/2020.coling-main.86/)
- [BEIR](https://arxiv.org/abs/2104.08663)
- [BGE-M3](https://arxiv.org/abs/2402.03216)
- [GraphRAG](https://arxiv.org/abs/2404.16130)
