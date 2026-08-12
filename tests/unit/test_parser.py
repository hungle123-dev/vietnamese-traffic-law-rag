from pathlib import Path

import pytest

from traffic_legal_qa.ingestion.parser import LegalHierarchyParser

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "traffic_sample.txt"


def test_parser_builds_hierarchy_and_stable_ids() -> None:
    content = FIXTURE_PATH.read_text(encoding="utf-8")

    units = LegalHierarchyParser("sample").parse(content)

    assert [unit.unit_type for unit in units] == [
        "part",
        "chapter",
        "section",
        "article",
        "clause",
        "point",
        "point",
        "clause",
        "article",
        "clause",
        "point",
    ]
    assert units[3].unit_id == "sample::part::I::chapter::I::section::1::article::1"
    assert units[4].unit_id == f"{units[3].unit_id}::clause::1"
    assert units[5].unit_id == f"{units[4].unit_id}::point::a"
    assert units[8].unit_id.endswith("::article::2")
    assert units[9].unit_id == f"{units[8].unit_id}::clause::1"
    assert units[9].unit_id != units[4].unit_id
    assert units[9].parent_id == units[8].unit_id
    assert units[9].parser_version == "parser-1"
    ids = {unit.unit_id for unit in units}
    assert all(unit.path[-1] == unit.unit_id for unit in units)
    assert all(unit.parent_id == "sample" or unit.parent_id in ids for unit in units)


def test_parser_matches_documentation_id_format_without_containers() -> None:
    units = LegalHierarchyParser("36/2024/QH15").parse("Điều 11. Mẫu\n2. Nội dung\n")

    assert units[1].unit_id == "36/2024/QH15::article::11::clause::2"


def test_parser_ignores_preamble_before_first_article() -> None:
    content = """
    CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
    Luật mẫu

    Điều 1. Điều đầu tiên
    Nội dung.
    """

    units = LegalHierarchyParser("sample").parse(content)

    assert [unit.unit_type for unit in units] == ["article"]
    assert units[0].text == "Điều 1. Điều đầu tiên\nNội dung."


@pytest.mark.parametrize("content", ["", "   ", "\n\n"])
def test_parser_rejects_empty_document(content: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        LegalHierarchyParser("sample").parse(content)


def test_parser_rejects_document_without_legal_units() -> None:
    with pytest.raises(ValueError, match="No legal units found"):
        LegalHierarchyParser("sample").parse("Document title only")
