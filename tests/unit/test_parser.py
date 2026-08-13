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


def test_parser_combines_a_split_chapter_heading() -> None:
    text = """Chương
VI Đường cao tốc
Mục 1
Phạm vi
Điều 1. Quy định chung"""

    parsed = LegalHierarchyParser().parse(text, metadata())
    units = {unit.unit_id: unit for unit in parsed.units}

    chapter = units["168/2024/NĐ-CP::chapter::VI"]
    section = units["168/2024/NĐ-CP::chapter::VI::section::1"]
    assert chapter.title == "Đường cao tốc"
    assert section.parent_id == chapter.unit_id


def test_parser_preserves_quoted_amendment_text_without_creating_nested_units() -> None:
    text = """Điều 1. Sửa đổi
1. Sửa đổi như sau:
“1. Nội dung được thay thế.
2. Nội dung của văn bản được sửa đổi.”
2. Quy định tiếp theo."""

    parsed = LegalHierarchyParser().parse(text, metadata())
    units = {unit.unit_id: unit for unit in parsed.units}

    first_clause = units["168/2024/NĐ-CP::article::1::clause::1"]
    assert "2. Nội dung của văn bản được sửa đổi.”" in first_clause.text
    assert "168/2024/NĐ-CP::article::1::clause::2" in units


def test_parser_stops_main_hierarchy_before_an_appendix() -> None:
    text = """Điều 1. Quy định chung
PHỤ LỤC I
1. Trường biểu mẫu"""

    parsed = LegalHierarchyParser().parse(text, metadata())

    assert [unit.unit_type for unit in parsed.units] == ["article"]


def test_parser_keeps_parsing_after_an_inline_quote() -> None:
    text = """Điều 1. Quy định chung
1. Cụm từ “nội dung trích dẫn” được áp dụng.
2. Quy định tiếp theo."""

    parsed = LegalHierarchyParser().parse(text, metadata())
    unit_ids = {unit.unit_id for unit in parsed.units}

    assert "168/2024/NĐ-CP::article::1::clause::2" in unit_ids


def test_parser_does_not_treat_part_noun_as_a_structural_heading() -> None:
    text = """Chương III
PHẦN ĐẤT ĐỂ BẢO VỆ ĐƯỜNG BỘ
Điều 10. Quy định chung"""

    parsed = LegalHierarchyParser().parse(text, metadata())
    units = {unit.unit_id: unit for unit in parsed.units}

    assert units["168/2024/NĐ-CP::chapter::III"].title == "PHẦN ĐẤT ĐỂ BẢO VỆ ĐƯỜNG BỘ"
