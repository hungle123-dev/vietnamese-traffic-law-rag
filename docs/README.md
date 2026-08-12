# Vietnamese Traffic Law Hybrid GraphRAG

Bộ tài liệu thiết kế cho sản phẩm hỏi đáp pháp luật giao thông đường bộ Việt Nam.

## Product decision

Đây là một **version-aware Hybrid GraphRAG Legal QA Platform**. Người dùng đặt câu hỏi tiếng Việt; hệ thống truy hồi các điều/khoản/điểm phù hợp, kiểm tra trạng thái hiệu lực và quan hệ sửa đổi, sau đó sinh câu trả lời có dẫn nguồn.

Phạm vi dữ liệu là pháp luật giao thông đường bộ Việt Nam, không phải toàn bộ pháp luật Việt Nam. Hệ thống là công cụ tra cứu và hỗ trợ thông tin, không thay thế tư vấn pháp lý chính thức.

## Reading order

1. [00-product-brief.md](00-product-brief.md)
2. [01-scope-and-requirements.md](01-scope-and-requirements.md)
3. [02-system-architecture.md](02-system-architecture.md)
4. [03-data-and-ingestion.md](03-data-and-ingestion.md)
5. [04-knowledge-graph-model.md](04-knowledge-graph-model.md)
6. [05-retrieval-and-reranking.md](05-retrieval-and-reranking.md)
7. [06-generation-and-citation-policy.md](06-generation-and-citation-policy.md)
8. [07-evaluation-plan.md](07-evaluation-plan.md)
9. [08-api-specification.md](08-api-specification.md)
10. [09-security-and-observability.md](09-security-and-observability.md)
11. [10-deployment-plan.md](10-deployment-plan.md)
12. [11-adr.md](11-adr.md)
13. [12-roadmap.md](12-roadmap.md)
14. [13-acceptance-criteria.md](13-acceptance-criteria.md)

## Research basis

- [NLP-LegalQA reference repository](https://github.com/n3sfan/NLP-LegalQA)
- [Vietnamese Legal QA, COLING 2020](https://aclanthology.org/2020.coling-main.86/)
- [Improving Vietnamese Legal QA based on Automatic Data Enrichment](https://arxiv.org/abs/2306.04841)
- [VLQA](https://arxiv.org/abs/2507.19995)
- [BEIR](https://arxiv.org/abs/2104.08663)
- [BGE-M3](https://arxiv.org/abs/2402.03216)
- [GraphRAG](https://arxiv.org/abs/2404.16130)
- [GRAG](https://arxiv.org/abs/2405.16506)
- [LRAGE](https://github.com/hoorangyee/LRAGE)

## Document conventions

- `MUST`: yêu cầu bắt buộc.
- `SHOULD`: khuyến nghị cho v1, có thể thay đổi khi có benchmark.
- `MAY`: tùy chọn, chưa cần để hoàn thành v1.
- Các số liệu trong tài liệu là mục tiêu thiết kế, không phải kết quả benchmark đã đạt.
- Mọi kết luận về hiệu lực pháp luật phải dựa trên metadata và nguồn chính thống trong data snapshot, không dựa riêng vào LLM.
