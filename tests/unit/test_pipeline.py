import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from traffic_legal_qa.ingestion.models import LegalDocumentMetadata
from traffic_legal_qa.ingestion.pipeline import IngestionPipeline


def test_ingestion_pipeline_stores_raw_parsed_and_manifest(
    tmp_path: Path,
) -> None:
    source = tmp_path / "traffic.txt"
    source.write_bytes("Điều 1. Quy định\r\nNội dung.".encode())
    metadata = LegalDocumentMetadata(
        document_id="sample",
        title="Văn bản mẫu",
        document_type="law",
        issuer="Cơ quan mẫu",
        source_url="https://example.com/sample",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        snapshot_id="snapshot-1",
    )

    result = IngestionPipeline(tmp_path / "data").ingest_file(source, metadata)

    assert result.unit_count == 1
    assert Path(result.raw_path).read_bytes() == source.read_bytes()
    expected_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    parsed = json.loads(Path(result.parsed_path).read_text(encoding="utf-8"))
    assert parsed["metadata"]["content_sha256"] == expected_hash
    assert parsed["units"][0]["unit_id"] == "sample::article::1"
    assert parsed["units"][0]["parser_version"] == "parser-1"
    manifest = tmp_path / "data" / "manifests" / "manifest.json"
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload["documents"][0]["snapshot_id"] == "snapshot-1"
    assert manifest_payload["documents"][0]["content_sha256"] == expected_hash


def test_ingest_content_keeps_pdf_bytes_as_a_pdf_artifact(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    raw_content = b"%PDF-1.7\nraw document bytes"
    metadata = LegalDocumentMetadata(
        document_id="36/2024/QH15",
        title="Luật Trật tự, an toàn giao thông đường bộ",
        document_type="law",
        issuer="Quốc hội",
        source_url="https://example.gov.vn/document",
        content_url="https://example.gov.vn/document.pdf",
        retrieved_at=datetime(2026, 8, 12, tzinfo=UTC),
        snapshot_id="test-v1",
    )

    result = IngestionPipeline(data_dir).ingest_content(
        raw_content,
        "Điều 1. Phạm vi điều chỉnh\nNội dung.",
        metadata,
        raw_suffix=".pdf",
    )

    assert Path(result.raw_path).suffix == ".pdf"
    assert Path(result.raw_path).read_bytes() == raw_content


def test_ingestion_keeps_raw_bytes_when_utf8_decoding_fails(tmp_path: Path) -> None:
    source = tmp_path / "invalid.txt"
    raw_bytes = b"\xff\xfe"
    source.write_bytes(raw_bytes)
    metadata = LegalDocumentMetadata(
        document_id="invalid",
        title="Văn bản lỗi encoding",
        document_type="law",
        issuer="Cơ quan mẫu",
        source_url="https://example.com/invalid",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        snapshot_id="snapshot-invalid",
    )
    pipeline = IngestionPipeline(tmp_path / "data")

    with pytest.raises(UnicodeDecodeError):
        pipeline.ingest_file(source, metadata)

    expected_raw = tmp_path / "data" / "raw" / f"{hashlib.sha256(raw_bytes).hexdigest()}.txt"
    assert expected_raw.read_bytes() == raw_bytes
