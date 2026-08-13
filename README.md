# Vietnamese Traffic Law Hybrid GraphRAG

Blueprint cho một sản phẩm tra cứu và hỏi đáp pháp luật giao thông đường bộ Việt Nam có căn cứ pháp lý.

## Trạng thái

Phase 1 đã tạo và kiểm tra một **draft snapshot 12 văn bản**: raw immutable, normalized text, parsed hierarchy, manifest và quality report. Blueprint vẫn là nguồn quyết định; source chưa có graph, retrieval, LLM hay UI. Snapshot chưa được "promote" vì 30 gold questions và relation-evidence vẫn chưa tồn tại.

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

## Chạy Phase 1

```powershell
uv sync --all-groups
uv run pytest tests/unit
uv run traffic-legal-qa fetch-portal `
  --catalog data/catalog/smoke-168-2024-nd-cp.json `
  --document-id "168/2024/NĐ-CP"
uv run traffic-legal-qa fetch-catalog `
  --catalog data/catalog/pilot-traffic-2026-08-13-v1.json
uv run traffic-legal-qa validate-snapshot --snapshot-id traffic-2026-08-13-v1
uv run traffic-legal-qa report-snapshot `
  --snapshot-id traffic-2026-08-13-v1 `
  --catalog data/catalog/pilot-traffic-2026-08-13-v1.json
```

Raw response, parsed artifacts và report sinh ra trong `data/` được `.gitignore`; catalog được version-control.
