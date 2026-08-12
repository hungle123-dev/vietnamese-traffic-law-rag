# Vietnamese Traffic Law Hybrid GraphRAG

Project AI Engineer xây dựng hệ thống hỏi đáp pháp luật giao thông đường bộ Việt Nam.

## Current milestone: ingestion vertical slice (Phase 1A)

Phase 1 chỉ triển khai vertical slice:

```text
local source document
→ immutable raw storage
→ deterministic hierarchy parser
→ manifest + parsed JSON
→ parser/pipeline tests
```

Chưa có retrieval, LLM generation, UI hoặc Agentic RAG. Phase 1B có thể tải và ingest PDF text từ nguồn chính thức.

## Setup

```powershell
uv sync --extra dev
```

## Quality checks

```powershell
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -q
```

## Ingest a document

```powershell
uv run traffic-legal ingest `
  --source tests/fixtures/traffic_sample.txt `
  --document-id 36/2024/QH15 `
  --title "Luật Trật tự, an toàn giao thông đường bộ" `
  --issuer "Quốc hội" `
  --source-url https://vbpl.moj.gov.vn/ `
  --snapshot-id traffic-dev-v1
```

## Ingest an official PDF

`source_url` là trang công bố để hiển thị citation; `content_url` là PDF được tải, hash và lưu immutable.

```powershell
uv run traffic-legal fetch-pdf `
  --document-id "36/2024/QH15" `
  --title "Luật Trật tự, an toàn giao thông đường bộ" `
  --document-type law `
  --issuer "Quốc hội" `
  --issued-date 2024-06-27 `
  --effective-from 2025-01-01 `
  --status current `
  --source-url "https://vanban.chinhphu.vn/?classid=1&docid=211194&pageid=27160" `
  --content-url "https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/9/36-2024-qh15.pdf" `
  --snapshot-id "traffic-2026-08-12-v1"
```

The command writes ignored local artifacts under `data/`:

- `data/raw/`: content-addressed raw text;
- `data/parsed/`: parsed legal units;
- `data/manifests/manifest.json`: document metadata and lineage.

## Documentation

Start with [docs/README.md](docs/README.md), then read the product brief and ingestion design before changing behavior. Agent-specific rules are in [AGENTS.md](AGENTS.md).
