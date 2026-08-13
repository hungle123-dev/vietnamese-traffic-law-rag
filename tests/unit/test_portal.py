from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from traffic_legal_qa.ingestion.models import ReviewedSource
from traffic_legal_qa.ingestion.portal import PortalIdentityMismatch, parse_detail_response

FIXTURES = Path(__file__).parents[1] / "fixtures"
TITLE = (
    "Nghị định số 168/2024/NĐ-CP Quy định xử phạt vi phạm hành chính về trật tự, "
    "an toàn giao thông trong lĩnh vực giao thông đường bộ; trừ điểm, phục hồi điểm "
    "giấy phép lái xe"
)


def reviewed_source(**changes: str) -> ReviewedSource:
    values = {
        "snapshot_id": "traffic-2026-08-13-v1",
        "document_guid": "173920",
        "expected_document_id": "168/2024/NĐ-CP",
        "expected_title": TITLE,
        "expected_public_url": "https://phapluat.gov.vn/legal-documents/173920?tabName=noidung",
    }
    values.update(changes)
    return ReviewedSource.model_validate(values)


def test_parse_detail_response_maps_a_validated_portal_record() -> None:
    raw_bytes = (FIXTURES / "portal_detail_valid.json").read_bytes()

    detail = parse_detail_response(
        raw_bytes,
        reviewed_source(),
        retrieved_at=datetime(2026, 8, 13, tzinfo=UTC),
    )

    assert detail.metadata.document_id == "168/2024/NĐ-CP"
    assert detail.metadata.status == "current"
    assert detail.metadata.portal_document_type == "Nghị định"
    assert detail.metadata.fields == ("Đường bộ",)
    assert detail.metadata.issuing_organs == ("Chính phủ",)
    assert detail.metadata.signers[0].name == "Trần Hồng Hà"
    assert detail.metadata.effective_to is None
    assert detail.metadata.content_sha256
    assert detail.title_matches_expected is True
    assert detail.metadata.retrieved_at == datetime(2026, 8, 13, tzinfo=UTC)


def test_parse_detail_response_rejects_a_guid_that_resolves_to_another_document() -> None:
    raw_bytes = (FIXTURES / "portal_detail_valid.json").read_bytes()

    with pytest.raises(PortalIdentityMismatch, match="identity"):
        parse_detail_response(raw_bytes, reviewed_source(expected_document_id="35/2024/QH15"))
