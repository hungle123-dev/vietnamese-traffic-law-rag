from __future__ import annotations

import json
from pathlib import Path

from traffic_legal_qa.ingestion.models import ReviewedSource
from traffic_legal_qa.ingestion.pipeline import IngestionPipeline
from traffic_legal_qa.ingestion.storage import ArtifactStore

FIXTURES = Path(__file__).parents[1] / "fixtures"
TITLE = (
    "Nghị định số 168/2024/NĐ-CP Quy định xử phạt vi phạm hành chính về trật tự, "
    "an toàn giao thông trong lĩnh vực giao thông đường bộ; trừ điểm, phục hồi điểm "
    "giấy phép lái xe"
)


def source() -> ReviewedSource:
    return ReviewedSource(
        snapshot_id="traffic-2026-08-13-v1",
        document_guid="173920",
        expected_document_id="168/2024/NĐ-CP",
        expected_title=TITLE,
        expected_public_url="https://phapluat.gov.vn/legal-documents/173920?tabName=noidung",
    )


def test_pipeline_keeps_raw_and_promotes_only_a_validated_hierarchy(tmp_path: Path) -> None:
    raw_bytes = (FIXTURES / "portal_detail_valid.json").read_bytes()
    pipeline = IngestionPipeline(lambda _: raw_bytes, ArtifactStore(tmp_path))

    result = pipeline.ingest(source())

    assert result.raw_path.read_bytes() == raw_bytes
    assert result.normalized_path.read_text(encoding="utf-8").startswith("Điều 1.")
    assert result.unit_count == 2
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["documents"][0]["document_id"] == "168/2024/NĐ-CP"
