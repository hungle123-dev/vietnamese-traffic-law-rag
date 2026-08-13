from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from neo4j import Driver

from traffic_legal_qa.graph.importer import GraphSnapshotImporter, expected_counts
from traffic_legal_qa.ingestion.models import LegalUnit, ParsedDocument, ReviewedSource
from traffic_legal_qa.ingestion.normalize import normalize_html
from traffic_legal_qa.ingestion.parser import LegalHierarchyParser
from traffic_legal_qa.ingestion.portal import parse_detail_response
from traffic_legal_qa.ingestion.relations import ApprovedRelation, RelationArtifactError

FIXTURES = Path(__file__).parents[1] / "fixtures"
TITLE = (
    "Nghị định số 168/2024/NĐ-CP Quy định xử phạt vi phạm hành chính về trật tự, "
    "an toàn giao thông trong lĩnh vực giao thông đường bộ; trừ điểm, phục hồi điểm "
    "giấy phép lái xe"
)


class _Record:
    def __init__(self, count: int) -> None:
        self._count = count

    def __getitem__(self, key: str) -> int:
        assert key == "count"
        return self._count


class _RecordingDriver:
    def __init__(self, counts: Iterator[int]) -> None:
        self.queries: list[str] = []
        self.parameters: list[dict[str, object]] = []
        self._counts = counts

    def execute_query(self, query: str, **parameters: object) -> tuple[list[_Record], None, None]:
        self.queries.append(query)
        self.parameters.append(parameters)
        if "RETURN count" in query:
            return ([_Record(next(self._counts))], None, None)
        return ([], None, None)


def _parsed_document() -> ParsedDocument:
    source = ReviewedSource(
        snapshot_id="traffic-2026-08-13-v1",
        document_guid="173920",
        expected_document_id="168/2024/NĐ-CP",
        expected_title=TITLE,
        expected_public_url="https://phapluat.gov.vn/legal-documents/173920?tabName=noidung",
    )
    detail = parse_detail_response((FIXTURES / "portal_detail_valid.json").read_bytes(), source)
    return LegalHierarchyParser().parse(normalize_html(detail.html), detail.metadata)


def test_importer_projects_only_the_explicit_structural_graph() -> None:
    document = _parsed_document()
    expected = expected_counts([document])
    driver = _RecordingDriver(
        iter([*expected.node_counts.values(), *expected.relationship_counts.values()])
    )

    verification = GraphSnapshotImporter(cast(Driver, driver)).import_snapshot(
        document.metadata.snapshot_id, [document]
    )

    assert verification.is_valid is True
    assert expected.node_counts == {
        "Snapshot": 1,
        "Document": 1,
        "DocumentType": 1,
        "EffectStatus": 1,
        "Field": 2,
        "Organization": 1,
        "Signer": 1,
        "Part": 0,
        "Chapter": 0,
        "Section": 0,
        "Article": 1,
        "Clause": 0,
        "Point": 1,
    }
    assert expected.relationship_counts == {
        "IN_SNAPSHOT": 3,
        "HAS_TYPE": 1,
        "HAS_STATUS": 1,
        "IN_FIELD": 2,
        "ISSUED_BY": 1,
        "SIGNED_BY": 1,
        "HAS_PART": 0,
        "HAS_CHAPTER": 0,
        "HAS_SECTION": 0,
        "HAS_ARTICLE": 1,
        "HAS_CLAUSE": 0,
        "HAS_POINT": 1,
        "AMENDS": 0,
    }
    assert any("CREATE CONSTRAINT article_unit_key" in query for query in driver.queries)
    assert any("HAS_ARTICLE" in query for query in driver.queries)
    assert any("HAS_POINT" in query for query in driver.queries)
    assert not any("AMENDS" in query for query in driver.queries)


def test_importer_projects_only_approved_amends_edges() -> None:
    target = _parsed_document()
    source_metadata = target.metadata.model_copy(
        update={
            "document_id": "238/2026/NĐ-CP",
            "portal_document_guid": "238-guid",
            "title": "Amending decree",
            "source_url": "https://phapluat.gov.vn/legal-documents/238?tabName=noidung",
            "content_url": "https://phapluat.gov.vn/api/legal-documents/detail?docGUId=238",
            "content_sha256": "a" * 64,
        }
    )
    source = ParsedDocument(
        artifact_version="2",
        metadata=source_metadata,
        normalizer_version="1",
        parser_version="2",
        units=(
            LegalUnit(
                unit_id="238/2026/NĐ-CP::article::1",
                document_id="238/2026/NĐ-CP",
                unit_type="article",
                number="1",
                text="Sửa đổi Điều 1.",
                path=("238/2026/NĐ-CP::article::1",),
            ),
        ),
    )
    relation = ApprovedRelation.model_validate(
        {
            "relation_id": "traffic-2026-08-13-v1::amends::001",
            "relation_type": "AMENDS",
            "amendment_type": "sửa đổi",
            "source": {"document_id": "238/2026/NĐ-CP", "unit_id": "238/2026/NĐ-CP::article::1"},
            "target": {"document_id": target.metadata.document_id, "unit_id": None},
            "evidence_unit_id": "238/2026/NĐ-CP::article::1",
            "source_url": "https://phapluat.gov.vn/legal-documents/238?tabName=noidung",
            "raw_sha256": "a" * 64,
            "provenance": "reviewed_primary_source",
            "review_status": "approved",
            "reviewed_by": "legal-curator",
            "reviewed_at": "2026-08-13",
            "note": None,
        }
    )
    expected = expected_counts([source, target], (relation,))
    driver = _RecordingDriver(
        iter([*expected.node_counts.values(), *expected.relationship_counts.values()])
    )

    verification = GraphSnapshotImporter(cast(Driver, driver)).import_snapshot(
        target.metadata.snapshot_id, [source, target], (relation,)
    )

    assert verification.is_valid is True
    assert expected.relationship_counts["AMENDS"] == 1
    assert any("relation:AMENDS" in query for query in driver.queries)
    assert any(
        parameters.get("parameters_")
        == {
            "rows": [
                {
                    "relation_id": relation.relation_id,
                    "source_key": "traffic-2026-08-13-v1::238/2026/NĐ-CP::article::1",
                    "target_key": "traffic-2026-08-13-v1::168/2024/NĐ-CP",
                    "properties": {
                        "relation_id": relation.relation_id,
                        "amendment_type": "sửa đổi",
                        "evidence_unit_id": "238/2026/NĐ-CP::article::1",
                        "source_url": "https://phapluat.gov.vn/legal-documents/238?tabName=noidung",
                        "raw_sha256": "a" * 64,
                        "provenance": "reviewed_primary_source",
                        "review_status": "approved",
                        "reviewed_by": "legal-curator",
                        "reviewed_at": "2026-08-13",
                        "snapshot_id": "traffic-2026-08-13-v1",
                    },
                }
            ]
        }
        for parameters in driver.parameters
    )


def test_importer_rejects_an_unresolved_relation_before_any_graph_write() -> None:
    target = _parsed_document()
    relation = ApprovedRelation.model_validate(
        {
            "relation_id": "traffic-2026-08-13-v1::amends::unresolved",
            "relation_type": "AMENDS",
            "amendment_type": "sửa đổi",
            "source": {"document_id": "238/2026/NĐ-CP", "unit_id": "238/2026/NĐ-CP::article::1"},
            "target": {"document_id": target.metadata.document_id, "unit_id": None},
            "evidence_unit_id": "238/2026/NĐ-CP::article::1",
            "source_url": "https://phapluat.gov.vn/legal-documents/238?tabName=noidung",
            "raw_sha256": "a" * 64,
            "provenance": "reviewed_primary_source",
            "review_status": "approved",
            "reviewed_by": "legal-curator",
            "reviewed_at": "2026-08-13",
            "note": None,
        }
    )
    driver = _RecordingDriver(iter(()))

    with pytest.raises(RelationArtifactError, match="unknown document"):
        GraphSnapshotImporter(cast(Driver, driver)).import_snapshot(
            target.metadata.snapshot_id, [target], (relation,)
        )

    assert driver.queries == []
