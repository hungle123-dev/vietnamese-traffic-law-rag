# Vietnamese Traffic Law Hybrid GraphRAG

Blueprint cho một sản phẩm tra cứu và hỏi đáp pháp luật giao thông đường bộ Việt Nam có căn cứ pháp lý.

## Trạng thái

Code hiện có gồm ingestion, **structural Neo4j graph**, contract kiểm chứng artifact `AMENDS`, 30 retrieval gold citations được source-verify, và R0 exact-plus-lexical retrieval/evaluator cho draft snapshot 12 văn bản: raw immutable, normalized text, parsed hierarchy, manifest, quality report, metadata portal, node/edge graph, full-text index contract và reconciliation command. Dense retrieval, hybrid fusion, rerank, generation có citation, cache và monitoring chưa được scaffold trước phase của chúng. Snapshot chưa được promote: cần báo cáo R0 chạy trên Neo4j, các baseline tiếp theo, và gold/relation record được người review pháp lý phê duyệt.

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
uv run traffic-legal-qa rebuild-snapshot `
  --snapshot-id traffic-2026-08-13-v1 `
  --catalog data/catalog/pilot-traffic-2026-08-13-v1.json
uv run traffic-legal-qa validate-snapshot --snapshot-id traffic-2026-08-13-v1
uv run traffic-legal-qa report-snapshot `
  --snapshot-id traffic-2026-08-13-v1 `
  --catalog data/catalog/pilot-traffic-2026-08-13-v1.json
uv run traffic-legal-qa validate-gold-set `
  --snapshot-id traffic-2026-08-13-v1 `
  --gold-set data/gold/traffic-2026-08-13-v1.source-verified.json

$env:NEO4J_PASSWORD = Read-Host "Neo4j password"
docker compose up --detach --wait
uv run traffic-legal-qa import-graph --snapshot-id traffic-2026-08-13-v1
uv run traffic-legal-qa verify-graph --snapshot-id traffic-2026-08-13-v1
uv run traffic-legal-qa build-lexical-index --snapshot-id traffic-2026-08-13-v1
uv run traffic-legal-qa search-lexical `
  --snapshot-id traffic-2026-08-13-v1 `
  --query "Theo 168/2024/NĐ-CP, Điều 3 khoản 1 điểm a là gì?"
uv run traffic-legal-qa evaluate-r0 `
  --snapshot-id traffic-2026-08-13-v1 `
  --gold-set data/gold/traffic-2026-08-13-v1.source-verified.json `
  --split dev
```

`build-lexical-index` là bước offline và kiểm tra Neo4j có đúng 6.433 legal units của snapshot. `search-lexical` chỉ đọc index đã `ONLINE`; nó không tự tạo index trên query path. Chỉ chạy `evaluate-r0 --split test` sau khi đã chốt mọi quyết định R0 bằng dev; report sinh ra ở `data/evaluations/` không được commit.

Sau khi một curator phê duyệt relation artifact, kiểm chứng nó trước rồi truyền cùng artifact cho cả import và verify:

```powershell
uv run traffic-legal-qa validate-relations `
  --snapshot-id traffic-2026-08-13-v1 `
  --relation-artifact data/relations/traffic-2026-08-13-v1.json
uv run traffic-legal-qa import-graph `
  --snapshot-id traffic-2026-08-13-v1 `
  --relation-artifact data/relations/traffic-2026-08-13-v1.json
uv run traffic-legal-qa verify-graph `
  --snapshot-id traffic-2026-08-13-v1 `
  --relation-artifact data/relations/traffic-2026-08-13-v1.json
```

Raw response, parsed artifacts và report sinh ra trong `data/` được `.gitignore`; catalog được version-control.
