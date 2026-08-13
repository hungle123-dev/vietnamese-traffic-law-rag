from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from traffic_legal_qa.ingestion.models import CanonicalMetadata
from traffic_legal_qa.ingestion.parser import HierarchyParseError, LegalHierarchyParser

FIXTURES = Path(__file__).parents[1] / "fixtures"


def metadata() -> CanonicalMetadata:
    return CanonicalMetadata(
        document_id="168/2024/NĐ-CP",
        portal_document_guid="173920",
        title="Fixture",
        document_type="decree",
        status="current",
        source_url="https://example.test/public",
        content_url="https://example.test/api",
        retrieved_at=datetime(2026, 8, 13, tzinfo=UTC),
        content_sha256="a" * 64,
        snapshot_id="traffic-2026-08-13-v1",
    )


def test_parser_creates_stable_units_and_parents() -> None:
    parsed = LegalHierarchyParser().parse(
        (FIXTURES / "traffic_sample_normalized.txt").read_text(encoding="utf-8"), metadata()
    )
    units = {unit.unit_id: unit for unit in parsed.units}

    article = units["168/2024/NĐ-CP::article::1"]
    clause = units["168/2024/NĐ-CP::article::1::clause::1"]
    point = units["168/2024/NĐ-CP::article::1::clause::1::point::a"]

    assert article.parent_id == "168/2024/NĐ-CP::chapter::I"
    assert clause.parent_id == article.unit_id
    assert point.parent_id == clause.unit_id
    assert point.path[-1] == point.unit_id


def test_parser_rejects_a_duplicate_point_label() -> None:
    text = """Điều 1. Test\n1. Nội dung\na) Điểm thứ nhất\na) Điểm lặp"""

    with pytest.raises(HierarchyParseError, match="duplicate legal unit"):
        LegalHierarchyParser().parse(text, metadata())
