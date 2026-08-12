import re
from dataclasses import dataclass, field

from traffic_legal_qa.ingestion.models import LegalUnit, LegalUnitType

_PART_RE = re.compile(
    r"^\s*Phần\s+(?P<number>[^:\-–]+?)(?:\s*[-:–]\s*(?P<title>.*))?\s*$",
    re.IGNORECASE,
)
_CHAPTER_RE = re.compile(
    r"^\s*Chương\s+(?P<number>[^:\-–]+?)(?:\s*[-:–]\s*(?P<title>.*))?\s*$",
    re.IGNORECASE,
)
_SECTION_RE = re.compile(
    r"^\s*Mục\s+(?P<number>[^:\-–]+?)(?:\s*[-:–]\s*(?P<title>.*))?\s*$",
    re.IGNORECASE,
)
_ARTICLE_RE = re.compile(
    r"^\s*Điều\s+(?P<number>\d+[A-Za-zÀ-ỹ]*)(?:\s*[.\-–:]\s*(?P<title>.*))?\s*$",
    re.IGNORECASE,
)
_CLAUSE_RE = re.compile(r"^\s*(?P<number>\d+)\.\s+(?P<title>.+?)\s*$")
_POINT_RE = re.compile(r"^\s*(?P<number>[a-zđ])\)\s+(?P<title>.+?)\s*$", re.IGNORECASE)


@dataclass
class _MutableUnit:
    document_id: str
    unit_type: LegalUnitType
    number: str
    parent_id: str
    path: tuple[str, ...]
    ordinal: int
    title: str | None = None
    lines: list[str] = field(default_factory=list)

    @property
    def unit_id(self) -> str:
        return f"{self.parent_id}::{self.unit_type}::{self.number}"

    def append(self, line: str) -> None:
        if line:
            self.lines.append(line)

    def build(self) -> LegalUnit:
        text = "\n".join(self.lines).strip()
        if not text:
            raise ValueError(f"Legal unit has no text: {self.unit_id}")
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


class LegalHierarchyParser:
    """Parse common Vietnamese legal-document hierarchy markers deterministically."""

    def __init__(self, document_id: str) -> None:
        if not document_id.strip():
            raise ValueError("document_id must not be empty")
        self.document_id = document_id.strip()
        self._ordinal = 0

    def parse(self, content: str) -> list[LegalUnit]:
        lines = self._normalize_lines(content)
        completed: list[tuple[int, LegalUnit]] = []
        part_id: str | None = None
        chapter_id: str | None = None
        section_id: str | None = None
        article: _MutableUnit | None = None
        clause: _MutableUnit | None = None
        point: _MutableUnit | None = None

        for line in lines:
            heading = self._match_container(line)
            if heading is not None:
                completed.extend(self._finish_article(article, clause, point))
                article = clause = point = None
                part_id, chapter_id, section_id, container = self._start_container(
                    heading, part_id, chapter_id, section_id
                )
                completed.append((container.ordinal, container.build()))
                continue

            article_heading = _ARTICLE_RE.match(line)
            if article_heading is not None:
                completed.extend(self._finish_article(article, clause, point))
                clause = point = None
                article = self._new_article(article_heading, part_id, chapter_id, section_id)
                continue

            if article is None:
                continue

            clause_heading = _CLAUSE_RE.match(line)
            if clause_heading is not None:
                completed.extend(self._finish_children(clause, point))
                point = None
                article.append(line)
                clause = self._new_clause(clause_heading, article)
                continue

            point_heading = _POINT_RE.match(line)
            if point_heading is not None and clause is not None:
                completed.extend(self._finish_children(None, point))
                article.append(line)
                clause.append(line)
                point = self._new_point(point_heading, clause, article)
                continue

            self._append_body(line, article, clause, point)

        completed.extend(self._finish_article(article, clause, point))
        units = [unit for _, unit in sorted(completed, key=lambda item: item[0])]
        self._validate(units)
        if not units:
            raise ValueError("No legal units found")
        return units

    @staticmethod
    def _normalize_lines(content: str) -> list[str]:
        if not content.strip():
            raise ValueError("Document content must not be empty")
        return [line.strip() for line in content.splitlines() if line.strip()]

    @staticmethod
    def _match_container(line: str) -> re.Match[str] | None:
        for pattern in (_PART_RE, _CHAPTER_RE, _SECTION_RE):
            match = pattern.match(line)
            if match is not None:
                return match
        return None

    def _start_container(
        self,
        heading: re.Match[str],
        part_id: str | None,
        chapter_id: str | None,
        section_id: str | None,
    ) -> tuple[str | None, str | None, str | None, _MutableUnit]:
        unit_type = self._container_type(heading)
        number = self._clean_number(heading.group("number"))
        title = self._clean_title(heading.group("title"))
        parent_id = self._parent_for(unit_type, part_id, chapter_id, section_id)
        path = self._path_for(parent_id, part_id, chapter_id, section_id)
        unit = self._new_unit(unit_type, number, parent_id, path, title, heading.group(0))

        if unit_type == "part":
            return unit.unit_id, None, None, unit
        if unit_type == "chapter":
            return part_id, unit.unit_id, None, unit
        return part_id, chapter_id, unit.unit_id, unit

    def _new_article(
        self,
        heading: re.Match[str],
        part_id: str | None,
        chapter_id: str | None,
        section_id: str | None,
    ) -> _MutableUnit:
        number = self._clean_number(heading.group("number"))
        parent_id = self._parent_for("article", part_id, chapter_id, section_id)
        path = self._path_for(parent_id, part_id, chapter_id, section_id)
        return self._new_unit(
            "article",
            number,
            parent_id,
            path,
            self._clean_title(heading.group("title")),
            heading.group(0),
        )

    def _new_clause(self, heading: re.Match[str], article: _MutableUnit) -> _MutableUnit:
        return self._new_unit(
            "clause",
            heading.group("number"),
            article.unit_id,
            article.path,
            None,
            heading.group(0),
        )

    def _new_point(
        self,
        heading: re.Match[str],
        clause: _MutableUnit,
        article: _MutableUnit,
    ) -> _MutableUnit:
        return self._new_unit(
            "point",
            heading.group("number").lower(),
            clause.unit_id,
            article.path + (clause.unit_id,),
            None,
            heading.group(0),
        )

    def _new_unit(
        self,
        unit_type: LegalUnitType,
        number: str,
        parent_id: str,
        parent_path: tuple[str, ...],
        title: str | None,
        first_line: str,
    ) -> _MutableUnit:
        self._ordinal += 1
        unit_id = f"{parent_id}::{unit_type}::{number}"
        unit = _MutableUnit(
            document_id=self.document_id,
            unit_type=unit_type,
            number=number,
            parent_id=parent_id,
            path=parent_path + (unit_id,),
            ordinal=self._ordinal,
            title=title,
        )
        unit.append(first_line)
        return unit

    @staticmethod
    def _append_body(
        line: str,
        article: _MutableUnit,
        clause: _MutableUnit | None,
        point: _MutableUnit | None,
    ) -> None:
        article.append(line)
        if clause is not None:
            clause.append(line)
        if point is not None:
            point.append(line)

    @staticmethod
    def _finish_children(
        clause: _MutableUnit | None,
        point: _MutableUnit | None,
    ) -> list[tuple[int, LegalUnit]]:
        completed: list[tuple[int, LegalUnit]] = []
        if clause is not None:
            completed.append((clause.ordinal, clause.build()))
        if point is not None:
            completed.append((point.ordinal, point.build()))
        return completed

    @classmethod
    def _finish_article(
        cls,
        article: _MutableUnit | None,
        clause: _MutableUnit | None,
        point: _MutableUnit | None,
    ) -> list[tuple[int, LegalUnit]]:
        completed = cls._finish_children(clause, point)
        if article is not None:
            completed.append((article.ordinal, article.build()))
        return completed

    @staticmethod
    def _container_type(heading: re.Match[str]) -> LegalUnitType:
        text = heading.group(0).strip().casefold()
        if text.startswith("phần"):
            return "part"
        if text.startswith("chương"):
            return "chapter"
        return "section"

    def _parent_for(
        self,
        unit_type: LegalUnitType,
        part_id: str | None,
        chapter_id: str | None,
        section_id: str | None,
    ) -> str:
        if unit_type == "chapter":
            return part_id or self.document_id
        if unit_type == "section":
            return chapter_id or part_id or self.document_id
        return section_id or chapter_id or part_id or self.document_id

    def _path_for(
        self,
        parent_id: str,
        part_id: str | None,
        chapter_id: str | None,
        section_id: str | None,
    ) -> tuple[str, ...]:
        if parent_id == self.document_id:
            return (self.document_id,)
        path = [self.document_id]
        for identifier in (part_id, chapter_id, section_id):
            if identifier is not None:
                path.append(identifier)
        return tuple(path)

    @staticmethod
    def _clean_number(value: str) -> str:
        return " ".join(value.split())

    @staticmethod
    def _clean_title(value: str | None) -> str | None:
        if value is None:
            return None
        title = value.strip()
        return title or None

    def _validate(self, units: list[LegalUnit]) -> None:
        identifiers = {unit.unit_id for unit in units}
        if len(identifiers) != len(units):
            raise ValueError("Duplicate legal unit IDs detected")
        allowed_parents = identifiers | {self.document_id}
        missing_parents = {unit.parent_id for unit in units} - allowed_parents
        if missing_parents:
            raise ValueError(f"Missing legal unit parents: {sorted(missing_parents)}")
        invalid_paths = {
            unit.unit_id
            for unit in units
            if unit.path[-1] != unit.unit_id or unit.parent_id not in unit.path
        }
        if invalid_paths:
            raise ValueError(f"Invalid legal unit paths: {sorted(invalid_paths)}")
