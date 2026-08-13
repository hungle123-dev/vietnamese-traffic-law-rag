from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest
from neo4j import Driver

from traffic_legal_qa.ingestion.models import CanonicalMetadata, LegalUnit, ParsedDocument
from traffic_legal_qa.retrieval.lexical import LexicalIndexError, Neo4jLexicalRetriever

SNAPSHOT_ID = "traffic-2026-08-13-v1"
DOCUMENT_ID = "168/2024/NĐ-CP"
SOURCE_URL = "https://phapluat.gov.vn/legal-documents/168?tabName=noidung"


class _Record(dict[str, object]):
    pass


class _Driver:
    def __init__(self, graph_unit_count: int = 3, analyzer: str = "standard-no-stop-words") -> None:
        self.queries: list[str] = []
        self.parameters: list[dict[str, object]] = []
        self._graph_unit_count = graph_unit_count
        self._analyzer = analyzer

    def execute_query(self, query: str, **parameters: object) -> tuple[list[_Record], None, None]:
        self.queries.append(query)
        passed = parameters.get("parameters_")
        self.parameters.append(cast(dict[str, object], passed) if passed is not None else {})
        if query.startswith("CREATE FULLTEXT INDEX"):
            return ([], None, None)
        if query.startswith("SHOW FULLTEXT INDEXES"):
            return (
                [
                    _Record(
                        state="ONLINE",
                        labelsOrTypes=["Part", "Chapter", "Section", "Article", "Clause", "Point"],
                        properties=["snapshot_id", "document_id", "title", "text"],
                        options={
                            "indexConfig": {
                                "fulltext.analyzer": self._analyzer,
                                "fulltext.eventually_consistent": False,
                            }
                        },
                    )
                ],
                None,
                None,
            )
        if "RETURN count(unit) AS count" in query:
            return ([_Record(count=self._graph_unit_count)], None, None)
        if query.startswith("UNWIND range"):
            return (
                [
                    _Record(
                        unit_id=f"{DOCUMENT_ID}::article::3::clause::1::point::a",
                        document_id=DOCUMENT_ID,
                        unit_type="point",
                        title=None,
                        text="Cảnh cáo.",
                        source_url=SOURCE_URL,
                    )
                ],
                None,
                None,
            )
        if query.startswith("CALL db.index.fulltext.queryNodes"):
            return (
                [
                    _Record(
                        unit_id=f"{DOCUMENT_ID}::article::3::clause::1::point::a",
                        document_id=DOCUMENT_ID,
                        unit_type="point",
                        title=None,
                        text="Cảnh cáo.",
                        source_url=SOURCE_URL,
                        score=2.0,
                    ),
                    _Record(
                        unit_id=f"{DOCUMENT_ID}::article::3::clause::1",
                        document_id=DOCUMENT_ID,
                        unit_type="clause",
                        title=None,
                        text="Hình thức xử phạt chính.",
                        source_url=SOURCE_URL,
                        score=1.0,
                    ),
                ],
                None,
                None,
            )
        raise AssertionError(f"unexpected query: {query}")


def _document() -> ParsedDocument:
    article_id = f"{DOCUMENT_ID}::article::3"
    clause_id = f"{article_id}::clause::1"
    point_id = f"{clause_id}::point::a"
    return ParsedDocument(
        artifact_version="2",
        metadata=CanonicalMetadata(
            document_id=DOCUMENT_ID,
            portal_document_guid="173920",
            title="Sanctions",
            document_type="decree",
            status="current",
            source_url=SOURCE_URL,
            content_url="https://phapluat.gov.vn/api/legal-documents/detail?docGUId=173920",
            retrieved_at=datetime(2026, 8, 13, tzinfo=UTC),
            content_sha256="a" * 64,
            snapshot_id=SNAPSHOT_ID,
        ),
        normalizer_version="1",
        parser_version="2",
        units=(
            LegalUnit(
                unit_id=article_id,
                document_id=DOCUMENT_ID,
                unit_type="article",
                number="3",
                text="Hình thức xử phạt.",
                path=(article_id,),
            ),
            LegalUnit(
                unit_id=clause_id,
                document_id=DOCUMENT_ID,
                unit_type="clause",
                number="1",
                text="Hình thức xử phạt chính.",
                parent_id=article_id,
                path=(article_id, clause_id),
            ),
            LegalUnit(
                unit_id=point_id,
                document_id=DOCUMENT_ID,
                unit_type="point",
                number="a",
                text="Cảnh cáo.",
                parent_id=clause_id,
                path=(article_id, clause_id, point_id),
            ),
        ),
    )


def test_exact_lookup_precedes_fulltext_and_keeps_its_lexical_rank() -> None:
    driver = _Driver()
    retriever = Neo4jLexicalRetriever(cast(Driver, driver))

    candidates = retriever.search(
        SNAPSHOT_ID,
        [_document()],
        "Theo 168/2024/NĐ-CP, Điều 3 khoản 1 điểm a là gì?",
    )

    assert candidates[0].unit_id == f"{DOCUMENT_ID}::article::3::clause::1::point::a"
    assert candidates[0].exact_rank == 1
    assert candidates[0].lexical_rank == 1
    assert candidates[0].lexical_score == 2.0
    assert candidates[1].unit_type == "clause"
    assert candidates[1].lexical_rank == 2
    assert candidates[1].lexical_score == 1.0
    assert not any(query.startswith("CREATE FULLTEXT INDEX") for query in driver.queries)
    assert any(
        isinstance(fulltext_query := parameters.get("fulltext_query"), str)
        and 'snapshot_id:"traffic-2026-08-13-v1"' in fulltext_query
        and 'document_id:"168/2024/NĐ-CP"' in fulltext_query
        for parameters in driver.parameters
    )


def test_build_rejects_a_graph_snapshot_with_the_wrong_unit_count() -> None:
    retriever = Neo4jLexicalRetriever(cast(Driver, _Driver(graph_unit_count=2)))

    with pytest.raises(LexicalIndexError, match="graph unit count"):
        retriever.build_index(SNAPSHOT_ID, [_document()])


def test_build_rejects_an_existing_index_with_the_wrong_analyzer() -> None:
    retriever = Neo4jLexicalRetriever(cast(Driver, _Driver(analyzer="english")))

    with pytest.raises(LexicalIndexError, match="does not match"):
        retriever.build_index(SNAPSHOT_ID, [_document()])
