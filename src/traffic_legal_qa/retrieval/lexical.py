"""Snapshot-scoped exact lookup and Neo4j full-text retrieval."""

from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass, replace
from typing import Final, Literal, cast

from neo4j import Driver, Record

from traffic_legal_qa.ingestion.models import ParsedDocument, UnitType

LEXICAL_INDEX_NAMES: Final = (
    "legal_articles_fts_v1",
    "legal_clauses_fts_v1",
    "legal_points_fts_v1",
)
LEXICAL_INDEX_FORMAT: Final = "neo4j-fulltext-3way-rrf-v1"
_FULLTEXT_ANALYZER: Final = "standard-no-stop-words"
_RRF_K: Final = 60
_UNIT_TYPES: Final = frozenset(("article", "clause", "point"))
_TOKEN = re.compile(r"\w+", re.UNICODE)
_ARTICLE = re.compile(r"\bdieu\s+(\d+[a-z]?)\b")
_CLAUSE = re.compile(r"\bkhoan\s+(\d+[a-z]?)\b")
_POINT = re.compile(r"\bdiem\s+([a-zđ])\b")


class LexicalIndexError(RuntimeError):
    """The lexical index does not safely match the requested graph snapshot."""


@dataclass(frozen=True)
class _FulltextIndex:
    name: str
    label: str
    unit_type: UnitType
    properties: tuple[str, ...]


_FULLTEXT_INDEXES: Final = (
    _FulltextIndex(
        name="legal_articles_fts_v1",
        label="Article",
        unit_type="article",
        properties=("snapshot_id", "document_id", "title", "text"),
    ),
    _FulltextIndex(
        name="legal_clauses_fts_v1",
        label="Clause",
        unit_type="clause",
        properties=("snapshot_id", "document_id", "text"),
    ),
    _FulltextIndex(
        name="legal_points_fts_v1",
        label="Point",
        unit_type="point",
        properties=("snapshot_id", "document_id", "text"),
    ),
)


@dataclass(frozen=True)
class LexicalIndexStatus:
    """Verified full-text index state for one graph snapshot."""

    snapshot_id: str
    index_names: tuple[str, ...]
    index_format: str
    state: str
    expected_unit_count: int
    graph_unit_count: int

    def model_dump(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "index_names": list(self.index_names),
            "index_format": self.index_format,
            "state": self.state,
            "expected_unit_count": self.expected_unit_count,
            "graph_unit_count": self.graph_unit_count,
        }


@dataclass(frozen=True)
class RetrievalCandidate:
    """One retrieval-only legal provision with immutable source location."""

    unit_id: str
    document_id: str
    snapshot_id: str
    text: str
    unit_type: UnitType
    source_url: str
    title: str | None
    validity: Literal["unknown"] = "unknown"
    exact_rank: int | None = None
    lexical_rank: int | None = None
    lexical_score: float | None = None
    lexical_rrf_score: float | None = None

    def model_dump(self) -> dict[str, object]:
        return {
            "unit_id": self.unit_id,
            "document_id": self.document_id,
            "snapshot_id": self.snapshot_id,
            "text": self.text,
            "unit_type": self.unit_type,
            "source_url": self.source_url,
            "title": self.title,
            "validity": self.validity,
            "exact_rank": self.exact_rank,
            "lexical_rank": self.lexical_rank,
            "lexical_score": self.lexical_score,
            "lexical_rrf_score": self.lexical_rrf_score,
        }


class Neo4jLexicalRetriever:
    """Three snapshot-scoped full-text indexes, built outside the request path."""

    def __init__(self, driver: Driver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    def build_index(
        self, snapshot_id: str, documents: list[ParsedDocument], wait_seconds: float = 30.0
    ) -> LexicalIndexStatus:
        """Create the fixed full-text indexes and reject a mismatched graph snapshot."""

        if wait_seconds <= 0:
            raise LexicalIndexError("wait_seconds must be positive")
        for index in _FULLTEXT_INDEXES:
            properties = ", ".join(f"unit.{property_name}" for property_name in index.properties)
            self._execute(
                f"CREATE FULLTEXT INDEX {index.name} IF NOT EXISTS "
                f"FOR (unit:{index.label}) ON EACH [{properties}] "
                "OPTIONS {indexConfig: {`fulltext.analyzer`: 'standard-no-stop-words', "
                "`fulltext.eventually_consistent`: false}}"
            )
        return self.verify_index(snapshot_id, documents, wait_seconds=wait_seconds)

    def verify_index(
        self,
        snapshot_id: str,
        documents: list[ParsedDocument],
        *,
        wait_seconds: float = 0.0,
    ) -> LexicalIndexStatus:
        """Confirm offline-built indexes are online and cover this frozen snapshot."""

        if wait_seconds < 0:
            raise LexicalIndexError("wait_seconds must not be negative")
        expected_unit_count = _validated_indexed_unit_count(snapshot_id, documents)
        state = self._await_online(wait_seconds)
        graph_unit_count = self._graph_unit_count(snapshot_id)
        if graph_unit_count != expected_unit_count:
            raise LexicalIndexError(
                "graph unit count does not match the validated snapshot; "
                "import or verify the graph first"
            )
        return LexicalIndexStatus(
            snapshot_id=snapshot_id,
            index_names=LEXICAL_INDEX_NAMES,
            index_format=LEXICAL_INDEX_FORMAT,
            state=state,
            expected_unit_count=expected_unit_count,
            graph_unit_count=graph_unit_count,
        )

    def search(
        self,
        snapshot_id: str,
        documents: list[ParsedDocument],
        query: str,
        top_k: int = 10,
    ) -> tuple[RetrievalCandidate, ...]:
        """Return exact provision candidates first, then bounded full-text candidates."""

        if not 1 <= top_k <= 50:
            raise LexicalIndexError("top_k must be between 1 and 50")
        normalized_query = _normalize_query(query)
        document_ids = _matching_document_ids(documents, normalized_query)
        exact_unit_ids = _exact_unit_ids(documents, document_ids, normalized_query)
        exact_candidates = self._load_exact_candidates(snapshot_id, exact_unit_ids)
        if len(exact_candidates) != len(exact_unit_ids):
            raise LexicalIndexError("an exact provision is missing from the graph snapshot")

        candidates_by_id = {candidate.unit_id: candidate for candidate in exact_candidates}
        lexical_candidates = _rrf_merge(
            tuple(
                self._search_fulltext(
                    index,
                    snapshot_id,
                    _fulltext_query(normalized_query, snapshot_id, document_ids),
                    document_ids,
                    top_k,
                )
                for index in _FULLTEXT_INDEXES
            )
        )
        for candidate in lexical_candidates:
            existing = candidates_by_id.get(candidate.unit_id)
            if existing is None:
                candidates_by_id[candidate.unit_id] = candidate
            else:
                candidates_by_id[candidate.unit_id] = replace(
                    existing,
                    lexical_rank=candidate.lexical_rank,
                    lexical_score=candidate.lexical_score,
                    lexical_rrf_score=candidate.lexical_rrf_score,
                )

        exact_unit_id_set = {candidate.unit_id for candidate in exact_candidates}
        ordered = [candidates_by_id[candidate.unit_id] for candidate in exact_candidates]
        ordered.extend(
            candidates_by_id[candidate.unit_id]
            for candidate in lexical_candidates
            if candidate.unit_id not in exact_unit_id_set
        )
        return tuple(ordered[:top_k])

    def _await_online(self, wait_seconds: float) -> str:
        deadline = time.monotonic() + wait_seconds
        while True:
            records = self._records(
                "SHOW FULLTEXT INDEXES YIELD name, state, labelsOrTypes, properties, options "
                "WHERE name IN $index_names "
                "RETURN name, state, labelsOrTypes, properties, options",
                index_names=list(LEXICAL_INDEX_NAMES),
            )
            records_by_name = {
                record["name"]: record for record in records if isinstance(record["name"], str)
            }
            states: list[str] = []
            for index in _FULLTEXT_INDEXES:
                record = records_by_name.get(index.name)
                if record is None:
                    raise LexicalIndexError(f"full-text index was not created: {index.name}")
                _validate_index_schema(index, record)
                state = record["state"]
                if not isinstance(state, str):
                    raise LexicalIndexError("full-text index returned a malformed state")
                states.append(state)
            if all(state == "ONLINE" for state in states):
                return "ONLINE"
            if time.monotonic() >= deadline:
                raise LexicalIndexError(f"full-text indexes did not become ONLINE: {states}")
            time.sleep(0.1)

    def _graph_unit_count(self, snapshot_id: str) -> int:
        record = self._one(
            "MATCH (unit)-[:IN_SNAPSHOT]->(:Snapshot {snapshot_id: $snapshot_id}) "
            "WHERE unit:Article OR unit:Clause OR unit:Point "
            "RETURN count(unit) AS count",
            snapshot_id=snapshot_id,
        )
        if record is None or not isinstance(record["count"], int):
            raise LexicalIndexError("graph unit count query returned no integer")
        return record["count"]

    def _load_exact_candidates(
        self, snapshot_id: str, unit_ids: tuple[str, ...]
    ) -> tuple[RetrievalCandidate, ...]:
        if not unit_ids:
            return ()
        records = self._records(
            "UNWIND range(0, size($unit_ids) - 1) AS position "
            "WITH position, $unit_ids[position] AS unit_id "
            "MATCH (unit {snapshot_id: $snapshot_id, unit_id: unit_id}) "
            "MATCH (document:Document {snapshot_id: $snapshot_id, document_id: unit.document_id}) "
            "RETURN position, unit.unit_id AS unit_id, unit.document_id AS document_id, "
            "unit.unit_type AS unit_type, unit.title AS title, unit.text AS text, "
            "document.source_url AS source_url "
            "ORDER BY position",
            snapshot_id=snapshot_id,
            unit_ids=list(unit_ids),
        )
        return tuple(
            _candidate_from_record(record, snapshot_id, exact_rank=position + 1)
            for position, record in enumerate(records)
        )

    def _search_fulltext(
        self,
        index: _FulltextIndex,
        snapshot_id: str,
        fulltext_query: str,
        document_ids: tuple[str, ...],
        limit: int,
    ) -> tuple[RetrievalCandidate, ...]:
        records = self._records(
            "CALL db.index.fulltext.queryNodes($index_name, $fulltext_query, {limit: $limit}) "
            "YIELD node, score "
            "WITH node, score "
            "WHERE node.snapshot_id = $snapshot_id "
            "AND (size($document_ids) = 0 OR node.document_id IN $document_ids) "
            "MATCH (document:Document {snapshot_id: $snapshot_id, document_id: node.document_id}) "
            "RETURN node.unit_id AS unit_id, node.document_id AS document_id, "
            "node.unit_type AS unit_type, node.title AS title, node.text AS text, "
            "document.source_url AS source_url, score "
            "ORDER BY score DESC, unit_id ASC "
            "LIMIT $limit",
            index_name=index.name,
            fulltext_query=fulltext_query,
            limit=limit,
            snapshot_id=snapshot_id,
            document_ids=list(document_ids),
        )
        candidates = tuple(_candidate_from_record(record, snapshot_id) for record in records)
        if any(candidate.unit_type != index.unit_type for candidate in candidates):
            raise LexicalIndexError(f"full-text index returned the wrong unit type: {index.name}")
        return tuple(
            replace(candidate, lexical_rank=rank)
            for rank, candidate in enumerate(candidates, start=1)
        )

    def _one(self, query: str, **parameters: object) -> Record | None:
        records = self._records(query, **parameters)
        if len(records) > 1:
            raise LexicalIndexError("expected one graph record")
        return records[0] if records else None

    def _records(self, query: str, **parameters: object) -> list[Record]:
        records, _, _ = self._driver.execute_query(
            query,
            parameters_=parameters,
            database_=self._database,
        )
        return list(records)

    def _execute(self, query: str) -> None:
        self._driver.execute_query(query, database_=self._database)


def _validated_indexed_unit_count(snapshot_id: str, documents: list[ParsedDocument]) -> int:
    if not documents:
        raise LexicalIndexError("cannot index an empty snapshot")
    if {document.metadata.snapshot_id for document in documents} != {snapshot_id}:
        raise LexicalIndexError("parsed documents do not share the requested snapshot")
    unit_ids = [
        unit.unit_id
        for document in documents
        for unit in document.units
        if unit.unit_type in _UNIT_TYPES
    ]
    if not unit_ids:
        raise LexicalIndexError("snapshot has no Article, Clause, or Point units")
    if len(unit_ids) != len(set(unit_ids)):
        raise LexicalIndexError("snapshot has duplicate unit IDs")
    return len(unit_ids)


def _normalize_query(query: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFC", query).split())
    if not normalized:
        raise LexicalIndexError("query must not be blank")
    if len(normalized) > 1000:
        raise LexicalIndexError("query exceeds 1000 characters")
    return normalized


def _matching_document_ids(
    documents: list[ParsedDocument], normalized_query: str
) -> tuple[str, ...]:
    folded_query = _fold(normalized_query)
    return tuple(
        document.metadata.document_id
        for document in documents
        if _fold(document.metadata.document_id) in folded_query
    )


def _exact_unit_ids(
    documents: list[ParsedDocument], document_ids: tuple[str, ...], normalized_query: str
) -> tuple[str, ...]:
    if not document_ids:
        return ()
    folded_query = _fold(normalized_query)
    article_match = _ARTICLE.search(folded_query)
    if article_match is None:
        return ()
    clause_match = _CLAUSE.search(folded_query)
    point_match = _POINT.search(folded_query)
    units_by_id = {
        unit.unit_id: unit
        for document in documents
        if document.metadata.document_id in document_ids
        for unit in document.units
    }
    article_ids = [
        unit_id
        for unit_id, unit in units_by_id.items()
        if unit.unit_type == "article" and unit.number.casefold() == article_match.group(1)
    ]
    if clause_match is None:
        return tuple(sorted(article_ids))
    clause_ids = [
        unit_id
        for unit_id, unit in units_by_id.items()
        if unit.unit_type == "clause"
        and unit.parent_id in article_ids
        and unit.number.casefold() == clause_match.group(1)
    ]
    if point_match is None:
        return tuple(sorted(clause_ids))
    parent_ids = clause_ids or article_ids
    return tuple(
        sorted(
            unit_id
            for unit_id, unit in units_by_id.items()
            if unit.unit_type == "point"
            and unit.parent_id in parent_ids
            and unit.number.casefold() == point_match.group(1)
        )
    )


def _fulltext_query(normalized_query: str, snapshot_id: str, document_ids: tuple[str, ...]) -> str:
    tokens = tuple(dict.fromkeys(token.casefold() for token in _TOKEN.findall(normalized_query)))
    if not tokens:
        raise LexicalIndexError("query has no searchable tokens")
    terms = " OR ".join(f'"{token}"' for token in tokens)
    scopes = [f"snapshot_id:{_lucene_phrase(snapshot_id)}"]
    if document_ids:
        document_scopes = " OR ".join(
            f"document_id:{_lucene_phrase(document_id)}" for document_id in document_ids
        )
        scopes.append(f"({document_scopes})")
    return f"{' AND '.join(scopes)} AND ({terms})"


def _lucene_phrase(value: str) -> str:
    return f'"{value.replace("\\", "\\\\").replace(chr(34), r"\"")}"'


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(
        "d" if character == "đ" else character
        for character in decomposed
        if not unicodedata.combining(character)
    )


def _validate_index_schema(index: _FulltextIndex, record: Record) -> None:
    labels = record["labelsOrTypes"]
    properties = record["properties"]
    options = record["options"]
    index_config = options.get("indexConfig") if isinstance(options, dict) else None
    if (
        not isinstance(labels, list)
        or not all(isinstance(label, str) for label in labels)
        or not isinstance(properties, list)
        or not all(isinstance(property_name, str) for property_name in properties)
        or labels != [index.label]
        or set(properties) != set(index.properties)
        or not isinstance(index_config, dict)
        or index_config.get("fulltext.analyzer") != _FULLTEXT_ANALYZER
        or index_config.get("fulltext.eventually_consistent") is not False
    ):
        raise LexicalIndexError("full-text index does not match the retrieval contract")


def _rrf_merge(
    ranked_lists: tuple[tuple[RetrievalCandidate, ...], ...],
) -> tuple[RetrievalCandidate, ...]:
    candidates: dict[str, RetrievalCandidate] = {}
    scores: dict[str, float] = {}
    for ranked_candidates in ranked_lists:
        for rank, candidate in enumerate(ranked_candidates, start=1):
            candidates.setdefault(candidate.unit_id, candidate)
            scores[candidate.unit_id] = scores.get(candidate.unit_id, 0.0) + 1.0 / (_RRF_K + rank)
    return tuple(
        sorted(
            (
                replace(candidate, lexical_rrf_score=scores[unit_id])
                for unit_id, candidate in candidates.items()
            ),
            key=lambda candidate: (-cast(float, candidate.lexical_rrf_score), candidate.unit_id),
        )
    )


def _candidate_from_record(
    record: Record,
    snapshot_id: str,
    *,
    exact_rank: int | None = None,
) -> RetrievalCandidate:
    unit_id = record["unit_id"]
    document_id = record["document_id"]
    unit_type = record["unit_type"]
    source_url = record["source_url"]
    text = record["text"]
    if not all(
        isinstance(value, str) and value for value in (unit_id, document_id, source_url, text)
    ):
        raise LexicalIndexError("retrieval query returned malformed candidate text")
    if unit_type not in _UNIT_TYPES:
        raise LexicalIndexError("retrieval query returned an unknown unit type")
    score = record["score"] if "score" in record.keys() else None
    if score is not None and not isinstance(score, (float, int)):
        raise LexicalIndexError("retrieval query returned a malformed lexical score")
    title = record["title"]
    if title is not None and not isinstance(title, str):
        raise LexicalIndexError("retrieval query returned a malformed title")
    return RetrievalCandidate(
        unit_id=unit_id,
        document_id=document_id,
        snapshot_id=snapshot_id,
        text=text,
        unit_type=cast(UnitType, unit_type),
        source_url=source_url,
        title=title,
        exact_rank=exact_rank,
        lexical_score=float(score) if score is not None else None,
    )
