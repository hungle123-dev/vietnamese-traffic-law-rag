# Vietnamese Traffic Law Hybrid GraphRAG

Blueprint cho một sản phẩm tra cứu và hỏi đáp pháp luật giao thông đường bộ Việt Nam có căn cứ pháp lý.

## Trạng thái

Repository hiện là **documentation-only**. Không có source code, test, dependency lockfile, data corpus hay cấu hình runtime. Mọi quyết định cần thiết trước giai đoạn code được đóng băng trong [`docs/`](docs/README.md).

## Product đã chốt

- **Domain:** pháp luật giao thông đường bộ Việt Nam.
- **Product:** trợ lý tra cứu pháp lý có citation Điều/Khoản/Điểm, nhận biết hiệu lực theo data snapshot.
- **Data path:** Cổng Pháp luật quốc gia API/HTML → raw response bất biến → hierarchy parser → graph/index → hybrid retrieval → cited answer.
- **Không thuộc v1:** chatbot tổng quát, toàn bộ pháp luật Việt Nam, xử lý tài liệu không có HTML cấu trúc, agent loop tự trị và fine-tuning trước benchmark.

## Đọc trước khi viết code

1. [Product brief](docs/00-product-brief.md)
2. [Scope and requirements](docs/01-scope-and-requirements.md)
3. [System architecture and planned source layout](docs/02-system-architecture.md)
4. [Data and ingestion contract](docs/03-data-and-ingestion.md)
5. [Implementation blueprint](docs/14-implementation-blueprint.md)

Chỉ bắt đầu Phase 1 khi các điều kiện trong [acceptance criteria](docs/13-acceptance-criteria.md) và Phase 0 của [roadmap](docs/12-roadmap.md) được đáp ứng.
