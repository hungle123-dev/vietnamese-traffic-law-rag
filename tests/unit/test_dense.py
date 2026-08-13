from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest
from neo4j import Driver

from traffic_legal_qa.ingestion.models import CanonicalMetadata, LegalUnit, ParsedDocument
from traffic_legal_qa.retrieval.dense import (
    DENSE_DIMENSIONS,
    DENSE_INDEX_FORMAT,
    DENSE_INDEX_NAME,
    BKAIEncoder,
    DenseIndexError,
    Neo4jDenseRetriever,
)

SNAPSHOT_ID = "traffic-2026-08-13-v1"
DOCUMENT_ID = "168/2024/NĐ-CP"
SOURCE_URL = "https://phapluat.gov.vn/legal-documents/168?tabName=noidung"


class _Record(dict[str, object]):
    pass


class _Driver:
    def __init__(
        self,
        embedding_snapshot_ids: list[str] | None = None,
        embedded_unit_ids: list[str] | None = None,
    ) -> None:
        self.queries: list[str] = []
        self.parameters: list[dict[str, object]] = []
        self.embedding_snapshot_ids = embedding_snapshot_ids or [SNAPSHOT_ID]
        self.embedded_unit_ids = embedded_unit_ids or []

    def execute_query(self, query: str, **parameters: object) -> tuple[list[_Record], None, None]:
        self.queries.append(query)
        passed = parameters.get("parameters_")
        values = cast(dict[str, object], passed) if passed is not None else {}
        self.parameters.append(values)
        if query.startswith("CREATE VECTOR INDEX"):
            return ([], None, None)
        if query.startswith("SHOW VECTOR INDEXES"):
            return (
                [
                    _Record(
                        state="ONLINE",
                        labelsOrTypes=["LegalUnit"],
                        properties=["embedding_bkai_v1"],
                        options={
                            "indexConfig": {
                                "vector.dimensions": DENSE_DIMENSIONS,
                                "vector.similarity_function": "cosine",
                                "vector.quantization.enabled": False,
                            }
                        },
                    )
                ],
                None,
                None,
            )
        if query.startswith("UNWIND $rows"):
            rows = values["rows"]
            assert isinstance(rows, list)
            return ([_Record(count=len(rows))], None, None)
        if "RETURN collect(DISTINCT unit.snapshot_id)" in query:
            return ([_Record(snapshot_ids=self.embedding_snapshot_ids)], None, None)
        if "RETURN unit.unit_id AS unit_id" in query:
            return ([_Record(unit_id=unit_id) for unit_id in self.embedded_unit_ids], None, None)
        if "RETURN count(unit) AS count" in query:
            return ([_Record(count=3)], None, None)
        if query.startswith("CALL db.index.vector.queryNodes"):
            return (
                [
                    _Record(
                        unit_id=f"{DOCUMENT_ID}::article::3::clause::1::point::a",
                        document_id=DOCUMENT_ID,
                        unit_type="point",
                        title=None,
                        text="Cảnh cáo.",
                        source_url=SOURCE_URL,
                        score=0.9,
                    )
                ],
                None,
                None,
            )
        raise AssertionError(f"unexpected query: {query}")


class _Encoder:
    device = "cpu"

    def __init__(self) -> None:
        self.texts: list[str] = []

    def encode(self, texts: list[str], batch_size: int = 32) -> tuple[tuple[float, ...], ...]:
        self.texts.extend(texts)
        return tuple((0.0,) * DENSE_DIMENSIONS for _ in texts)


def _document() -> ParsedDocument:
    article_id = f"{DOCUMENT_ID}::article::3"
    clause_id = f"{article_id}::clause::1"
    point_id = f"{clause_id}::point::a"
    return ParsedDocument(
        artifact_version="2",
        metadata=CanonicalMetadata(
            document_id=DOCUMENT_ID,
            portal_document_guid="173920",
            title="Xử phạt giao thông",
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


def test_build_and_search_keep_a_single_snapshot_of_answer_sized_units() -> None:
    driver = _Driver()
    encoder = _Encoder()
    retriever = Neo4jDenseRetriever(cast(Driver, driver))

    status = retriever.build_index(
        SNAPSHOT_ID,
        [_document()],
        cast(BKAIEncoder, encoder),
        batch_size=2,
    )
    candidates = retriever.search(
        SNAPSHOT_ID,
        "Hình thức xử phạt chính là gì?",
        cast(BKAIEncoder, encoder),
    )

    assert status.index_name == DENSE_INDEX_NAME
    assert status.index_format == DENSE_INDEX_FORMAT
    assert status.expected_unit_count == 3
    assert "Vị trí: Điều 3 > Khoản 1" in encoder.texts[1]
    assert candidates[0].unit_type == "point"
    assert candidates[0].dense_rank == 1
    assert candidates[0].dense_score == 0.9
    assert not any("fulltext" in query for query in driver.queries)


def test_build_rejects_embeddings_from_a_different_snapshot() -> None:
    retriever = Neo4jDenseRetriever(cast(Driver, _Driver(["other-snapshot"])))

    with pytest.raises(DenseIndexError, match="different snapshot"):
        retriever.build_index(SNAPSHOT_ID, [_document()], cast(BKAIEncoder, _Encoder()))


def test_build_resumes_only_missing_embeddings_after_an_interrupted_batch_run() -> None:
    existing_unit_id = f"{DOCUMENT_ID}::article::3"
    driver = _Driver(embedded_unit_ids=[existing_unit_id])
    encoder = _Encoder()

    Neo4jDenseRetriever(cast(Driver, driver)).build_index(
        SNAPSHOT_ID,
        [_document()],
        cast(BKAIEncoder, encoder),
    )

    assert len(encoder.texts) == 2
