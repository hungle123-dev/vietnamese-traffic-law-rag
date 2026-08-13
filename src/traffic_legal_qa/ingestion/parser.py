"""Deterministic parser for Vietnamese legal hierarchy headings."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final

from traffic_legal_qa.ingestion.models import CanonicalMetadata, LegalUnit, ParsedDocument, UnitType

PARSER_VERSION: Final = "1"
_RANK: Final = {"part": 0, "chapter": 1, "section": 2, "article": 3, "clause": 4, "point": 5}
_STRUCTURAL_TYPES: Final = frozenset({"part", "chapter", "section"})
_PART = re.compile(r"^PHẦN\s+(?P<number>.+?)(?:[.:]\s*(?P<title>.*))?$", re.IGNORECASE)
_CHAPTER = re.compile(
    r"^CHƯƠNG\s+(?P<number>[IVXLCDM]+|\d+[A-Za-z]?)(?:[.:]\s*(?P<title>.*))?$",
    re.IGNORECASE,
)
_SECTION = re.compile(
    r"^MỤC\s+(?P<number>[IVXLCDM]+|\d+[A-Za-z]?)(?:[.:]\s*(?P<title>.*))?$",
    re.IGNORECASE,
)
_ARTICLE = re.compile(r"^Điều\s+(?P<number>\d+[A-Za-z]?)(?:\.\s*)?(?P<title>.*)$", re.IGNORECASE)
_CLAUSE = re.compile(r"^(?P<number>\d+[A-Za-z]?)\.\s+(?P<text>.+)$")
_POINT = re.compile(r"^(?P<number>[a-zđ])\)\s+(?P<text>.+)$", re.IGNORECASE)


class HierarchyParseError(ValueError):
    """The normalized source cannot form a valid deterministic hierarchy."""


@dataclass
class _UnitBuilder:
    unit_id: str
    document_id: str
    unit_type: UnitType
    number: str
    parent_id: str | None
    path: tuple[str, ...]
    title: str | None = None
    body: list[str] = field(default_factory=list)

    def add_text(self, line: str) -> None:
        self.body.append(line)

    def build(self) -> LegalUnit:
        text = "\n".join(part for part in [self.title, *self.body] if part).strip()
        return LegalUnit(
            unit_id=self.unit_id,
            document_id=self.document_id,
            unit_type=self.unit_type,
            number=self.number,
            title=self.title,
            text=text,
            parent_id=self.parent_id,
            path=self.path,
        )


def _normalize_heading_title(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _unit_id(document_id: str, unit_type: UnitType, number: str, parent_id: str | None) -> str:
    if unit_type == "article":
        return f"{document_id}::article::{number}"
    if parent_id is not None:
        return f"{parent_id}::{unit_type}::{number}"
    return f"{document_id}::{unit_type}::{number}"


class LegalHierarchyParser:
    """Parses headings only; it never infers missing legal structure."""

    def parse(self, text: str, metadata: CanonicalMetadata) -> ParsedDocument:
        active: dict[UnitType, _UnitBuilder] = {}
        builders: list[_UnitBuilder] = []
        seen_ids: set[str] = set()

        def current() -> _UnitBuilder | None:
            if not active:
                return None
            return max(active.values(), key=lambda unit: _RANK[unit.unit_type])

        def parent_for(unit_type: UnitType) -> _UnitBuilder | None:
            candidates: dict[UnitType, tuple[UnitType, ...]] = {
                "part": (),
                "chapter": ("part",),
                "section": ("chapter", "part"),
                "article": ("section", "chapter", "part"),
                "clause": ("article",),
                "point": ("clause", "article"),
            }
            for candidate in candidates[unit_type]:
                if candidate in active:
                    return active[candidate]
            return None

        def start(unit_type: UnitType, number: str, title: str | None) -> None:
            parent = parent_for(unit_type)
            if unit_type in {"clause", "point"} and parent is None:
                raise HierarchyParseError(f"{unit_type} {number} has no legal parent")
            for active_type in tuple(active):
                if _RANK[active_type] >= _RANK[unit_type]:
                    del active[active_type]
            parent_id = parent.unit_id if parent else None
            unit_id = _unit_id(metadata.document_id, unit_type, number, parent_id)
            if unit_id in seen_ids:
                raise HierarchyParseError(f"duplicate legal unit: {unit_id}")
            seen_ids.add(unit_id)
            path = (parent.path if parent else ()) + (unit_id,)
            builder = _UnitBuilder(
                unit_id=unit_id,
                document_id=metadata.document_id,
                unit_type=unit_type,
                number=number,
                parent_id=parent_id,
                path=path,
                title=title,
            )
            builders.append(builder)
            active[unit_type] = builder

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if match := _PART.match(line):
                start("part", match["number"].strip(), _normalize_heading_title(match["title"]))
            elif match := _CHAPTER.match(line):
                start("chapter", match["number"], _normalize_heading_title(match["title"]))
            elif match := _SECTION.match(line):
                start("section", match["number"], _normalize_heading_title(match["title"]))
            elif match := _ARTICLE.match(line):
                start("article", match["number"], _normalize_heading_title(match["title"]))
            elif (match := _CLAUSE.match(line)) and "article" in active:
                start("clause", match["number"], match["text"].strip())
            elif (match := _POINT.match(line)) and ("clause" in active or "article" in active):
                start("point", match["number"].lower(), match["text"].strip())
            elif (unit := current()) is not None:
                if unit.unit_type in _STRUCTURAL_TYPES and unit.title is None and line.isupper():
                    unit.title = line
                else:
                    unit.add_text(line)

        units = tuple(builder.build() for builder in builders)
        self._validate(units, metadata.document_id)
        return ParsedDocument(
            metadata=metadata,
            normalizer_version="1",
            parser_version=PARSER_VERSION,
            units=units,
        )

    @staticmethod
    def _validate(units: tuple[LegalUnit, ...], document_id: str) -> None:
        if not units:
            raise HierarchyParseError("no legal headings found")
        unit_ids = {unit.unit_id for unit in units}
        if len(unit_ids) != len(units):
            raise HierarchyParseError("duplicate legal unit IDs")
        for unit in units:
            if not unit.text:
                raise HierarchyParseError(f"empty legal unit: {unit.unit_id}")
            if not unit.unit_id.startswith(f"{document_id}::"):
                raise HierarchyParseError(f"unit belongs to another document: {unit.unit_id}")
            if unit.parent_id is not None and unit.parent_id not in unit_ids:
                raise HierarchyParseError(f"orphan legal unit: {unit.unit_id}")
