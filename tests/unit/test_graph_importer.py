from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import cast

from neo4j import Driver

from traffic_legal_qa.graph.importer import GraphSnapshotImporter, expected_counts
from traffic_legal_qa.ingestion.models import ParsedDocument, ReviewedSource
from traffic_legal_qa.ingestion.normalize import normalize_html
from traffic_legal_qa.ingestion.parser import LegalHierarchyParser
from traffic_legal_qa.ingestion.portal import parse_detail_response

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
        self._counts = counts

    def execute_query(self, query: str, **_: object) -> tuple[list[_Record], None, None]:
        self.queries.append(query)
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
    }
    assert any("CREATE CONSTRAINT article_unit_key" in query for query in driver.queries)
    assert any("HAS_ARTICLE" in query for query in driver.queries)
    assert any("HAS_POINT" in query for query in driver.queries)
    assert not any("AMENDS" in query for query in driver.queries)
