from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from traffic_legal_qa.ingestion.models import CanonicalMetadata, LegalUnit, ParsedDocument
from traffic_legal_qa.ingestion.relations import (
    ApprovedRelationArtifact,
    RelationArtifactError,
    load_approved_relation_artifact,
    resolve_approved_relations,
)

SNAPSHOT_ID = "traffic-2026-08-13-v1"
SOURCE_ID = "new/2026/NĐ-CP"
TARGET_ID = "old/2024/NĐ-CP"
SOURCE_URL = "https://phapluat.gov.vn/legal-documents/new?tabName=noidung"
SOURCE_HASH = "a" * 64


def _document(
    document_id: str, content_sha256: str, source_url: str, unit_id: str
) -> ParsedDocument:
    metadata = CanonicalMetadata(
        document_id=document_id,
        portal_document_guid=f"guid-{document_id}",
        title=f"Document {document_id}",
        document_type="decree",
        status="current",
        source_url=source_url,
        content_url=f"https://phapluat.gov.vn/api/{document_id}",
        retrieved_at=datetime(2026, 8, 13, tzinfo=UTC),
        content_sha256=content_sha256,
        snapshot_id=SNAPSHOT_ID,
    )
    unit = LegalUnit(
        unit_id=unit_id,
        document_id=document_id,
        unit_type="article",
        number="1",
        text="Reviewed amendment evidence.",
        path=(unit_id,),
    )
    return ParsedDocument(
        artifact_version="2",
        metadata=metadata,
        normalizer_version="1",
        parser_version="2",
        units=(unit,),
    )


def _artifact() -> ApprovedRelationArtifact:
    return ApprovedRelationArtifact.model_validate(
        {
            "artifact_version": "1",
            "snapshot_id": SNAPSHOT_ID,
            "relations": [
                {
                    "relation_id": "traffic-2026-08-13-v1::amends::001",
                    "relation_type": "AMENDS",
                    "amendment_type": "sửa đổi, bổ sung",
                    "source": {
                        "document_id": SOURCE_ID,
                        "unit_id": f"{SOURCE_ID}::article::1",
                    },
                    "target": {
                        "document_id": TARGET_ID,
                        "unit_id": f"{TARGET_ID}::article::1",
                    },
                    "evidence_unit_id": f"{SOURCE_ID}::article::1",
                    "source_url": SOURCE_URL,
                    "raw_sha256": SOURCE_HASH,
                    "provenance": "reviewed_primary_source",
                    "review_status": "approved",
                    "reviewed_by": "legal-curator",
                    "reviewed_at": date(2026, 8, 13),
                    "note": None,
                }
            ],
        }
    )


def test_resolve_approved_relations_requires_snapshot_evidence_and_endpoints() -> None:
    source = _document(SOURCE_ID, SOURCE_HASH, SOURCE_URL, f"{SOURCE_ID}::article::1")
    target = _document(
        TARGET_ID,
        "b" * 64,
        "https://phapluat.gov.vn/legal-documents/old",
        f"{TARGET_ID}::article::1",
    )

    assert resolve_approved_relations(_artifact(), [source, target]) == _artifact().relations


def test_resolve_approved_relations_rejects_a_tampered_raw_hash() -> None:
    source = _document(SOURCE_ID, SOURCE_HASH, SOURCE_URL, f"{SOURCE_ID}::article::1")
    target = _document(
        TARGET_ID,
        "b" * 64,
        "https://phapluat.gov.vn/legal-documents/old",
        f"{TARGET_ID}::article::1",
    )
    artifact = _artifact()
    tampered_relation = artifact.relations[0].model_copy(update={"raw_sha256": "c" * 64})
    tampered = artifact.model_copy(update={"relations": (tampered_relation,)})

    with pytest.raises(RelationArtifactError, match="raw hash differs"):
        resolve_approved_relations(tampered, [source, target])


def test_loader_rejects_an_unapproved_relation_artifact(tmp_path: Path) -> None:
    payload = _artifact().model_dump(mode="json")
    payload["relations"][0]["review_status"] = "candidate"
    path = tmp_path / "relations.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RelationArtifactError):
        load_approved_relation_artifact(path)
