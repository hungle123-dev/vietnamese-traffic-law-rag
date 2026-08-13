"""Snapshot-safe BKAI dense retrieval over answer-sized legal provisions."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Final, cast

from neo4j import Driver, Record

from traffic_legal_qa.ingestion.models import LegalUnit, ParsedDocument, UnitType
from traffic_legal_qa.retrieval.lexical import RetrievalCandidate, normalize_retrieval_query

DENSE_INDEX_NAME: Final = "legal_units_bkai_v1"
DENSE_INDEX_FORMAT: Final = "neo4j-vector-bkai-pyvi-v1"
DENSE_EMBEDDING_PROPERTY: Final = "embedding_bkai_v1"
DENSE_MODEL_NAME: Final = "bkai-foundation-models/vietnamese-bi-encoder"
DENSE_MODEL_REVISION: Final = "84f9d9ada0d1a3c37557398b9ae9fcedcdf40be0"
DENSE_DIMENSIONS: Final = 768
DENSE_MAX_SEQUENCE_LENGTH: Final = 256
_DENSE_UNIT_TYPES: Final = frozenset(("article", "clause", "point"))
_UNIT_LABELS: Final[dict[UnitType, str]] = {
    "part": "Phần",
    "chapter": "Chương",
    "section": "Mục",
    "article": "Điều",
    "clause": "Khoản",
    "point": "Điểm",
}


class DenseIndexError(RuntimeError):
    """The dense index does not safely match the requested graph snapshot."""


@dataclass(frozen=True)
class DenseIndexStatus:
    """Verified BKAI vector-index state for one frozen graph snapshot."""

    snapshot_id: str
    index_name: str
    index_format: str
    state: str
    model_name: str
    model_revision: str
    dimensions: int
    expected_unit_count: int
    graph_unit_count: int
    embedded_unit_count: int

    def model_dump(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "index_name": self.index_name,
            "index_format": self.index_format,
            "state": self.state,
            "model_name": self.model_name,
            "model_revision": self.model_revision,
            "dimensions": self.dimensions,
            "expected_unit_count": self.expected_unit_count,
            "graph_unit_count": self.graph_unit_count,
            "embedded_unit_count": self.embedded_unit_count,
        }


@dataclass(frozen=True)
class _EmbeddingInput:
    unit_id: str
    text: str


class BKAIEncoder:
    """The project-selected BKAI model with its required PyVi segmentation."""

    def __init__(self, device: str | None = None) -> None:
        try:
            model_module = import_module("sentence_transformers")
            tokenizer_module = import_module("pyvi.ViTokenizer")
        except ImportError as exc:
            raise DenseIndexError(
                "dense dependencies are missing; run uv sync --all-groups"
            ) from exc
        model_class = cast(Any, model_module).SentenceTransformer
        tokenizer = cast(Any, tokenizer_module).ViTokenizer
        self.device = device or _default_device()
        self._tokenize: Callable[[str], str] = tokenizer.tokenize
        self._model: Any = model_class(
            DENSE_MODEL_NAME,
            revision=DENSE_MODEL_REVISION,
            device=self.device,
        )
        self._model.max_seq_length = DENSE_MAX_SEQUENCE_LENGTH

    def encode(self, texts: list[str], batch_size: int = 32) -> tuple[tuple[float, ...], ...]:
        """Segment then L2-normalize texts exactly as the BKAI model requires."""

        if not texts:
            return ()
        vectors = self._model.encode(
            [self._tokenize(text) for text in texts],
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return tuple(tuple(float(value) for value in vector) for vector in vectors)


class Neo4jDenseRetriever:
    """One BKAI vector index built offline; the query path only reads it."""

    def __init__(self, driver: Driver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    def build_index(
        self,
        snapshot_id: str,
        documents: list[ParsedDocument],
        encoder: BKAIEncoder,
        *,
        batch_size: int = 32,
        wait_seconds: float = 30.0,
    ) -> DenseIndexStatus:
        """Embed one frozen snapshot and create its fixed vector index offline."""

        if not 1 <= batch_size <= 128:
            raise DenseIndexError("batch_size must be between 1 and 128")
        if wait_seconds <= 0:
            raise DenseIndexError("wait_seconds must be positive")
        inputs = _embedding_inputs(snapshot_id, documents)
        expected_unit_count = len(inputs)
        if self._graph_unit_count(snapshot_id) != expected_unit_count:
            raise DenseIndexError(
                "graph dense-unit count does not match the validated snapshot; "
                "import the graph first"
            )
        self._assert_embedding_scope(snapshot_id)
        self._execute(
            "CREATE VECTOR INDEX legal_units_bkai_v1 IF NOT EXISTS "
            "FOR (unit:LegalUnit) ON (unit.embedding_bkai_v1) "
            "OPTIONS {indexConfig: {`vector.dimensions`: 768, "
            "`vector.similarity_function`: 'cosine', `vector.quantization.enabled`: false}}"
        )
        self._await_online(wait_seconds)
        embedded_unit_ids = self._embedded_unit_ids(snapshot_id)
        missing_inputs = [item for item in inputs if item.unit_id not in embedded_unit_ids]
        for batch in _batches(missing_inputs, batch_size):
            vectors = encoder.encode([item.text for item in batch], batch_size=batch_size)
            if len(vectors) != len(batch):
                raise DenseIndexError("embedding model returned the wrong number of vectors")
            rows = [
                {"unit_id": item.unit_id, "embedding": _validated_vector(vector)}
                for item, vector in zip(batch, vectors, strict=True)
            ]
            record = self._one(
                "UNWIND $rows AS row "
                "MATCH (unit:LegalUnit {snapshot_id: $snapshot_id, unit_id: row.unit_id}) "
                "SET unit.embedding_bkai_v1 = row.embedding "
                "RETURN count(unit) AS count",
                snapshot_id=snapshot_id,
                rows=rows,
            )
            if record is None or record["count"] != len(rows):
                raise DenseIndexError("not every validated legal unit received an embedding")
        return self.verify_index(snapshot_id, documents, wait_seconds=wait_seconds)

    def verify_index(
        self,
        snapshot_id: str,
        documents: list[ParsedDocument],
        *,
        wait_seconds: float = 0.0,
    ) -> DenseIndexStatus:
        """Confirm index schema, vector coverage, and safe snapshot isolation."""

        if wait_seconds < 0:
            raise DenseIndexError("wait_seconds must not be negative")
        expected_unit_count = len(_embedding_inputs(snapshot_id, documents))
        graph_unit_count = self._graph_unit_count(snapshot_id)
        if graph_unit_count != expected_unit_count:
            raise DenseIndexError(
                "graph dense-unit count does not match the validated snapshot; "
                "import the graph first"
            )
        self._assert_embedding_scope(snapshot_id)
        embedded_unit_count = self._embedded_unit_count(snapshot_id)
        if embedded_unit_count != expected_unit_count:
            raise DenseIndexError("dense embeddings do not cover the validated snapshot")
        return DenseIndexStatus(
            snapshot_id=snapshot_id,
            index_name=DENSE_INDEX_NAME,
            index_format=DENSE_INDEX_FORMAT,
            state=self._await_online(wait_seconds),
            model_name=DENSE_MODEL_NAME,
            model_revision=DENSE_MODEL_REVISION,
            dimensions=DENSE_DIMENSIONS,
            expected_unit_count=expected_unit_count,
            graph_unit_count=graph_unit_count,
            embedded_unit_count=embedded_unit_count,
        )

    def search(
        self,
        snapshot_id: str,
        query: str,
        encoder: BKAIEncoder,
        *,
        top_k: int = 10,
    ) -> tuple[RetrievalCandidate, ...]:
        """Return dense-only answer-sized candidates from the already-built index."""

        if not 1 <= top_k <= 50:
            raise DenseIndexError("top_k must be between 1 and 50")
        try:
            normalized_query = normalize_retrieval_query(query)
        except ValueError as exc:
            raise DenseIndexError(str(exc)) from exc
        vectors = encoder.encode([normalized_query], batch_size=1)
        if len(vectors) != 1:
            raise DenseIndexError("embedding model returned the wrong number of query vectors")
        vector = _validated_vector(vectors[0])
        records = self._records(
            "CALL db.index.vector.queryNodes($index_name, $limit, $embedding) "
            "YIELD node, score "
            "WITH node, score "
            "WHERE node.snapshot_id = $snapshot_id "
            "MATCH (document:Document {snapshot_id: $snapshot_id, document_id: node.document_id}) "
            "RETURN node.unit_id AS unit_id, node.document_id AS document_id, "
            "node.unit_type AS unit_type, node.title AS title, node.text AS text, "
            "document.source_url AS source_url, score "
            "ORDER BY score DESC, unit_id ASC "
            "LIMIT $limit",
            index_name=DENSE_INDEX_NAME,
            limit=top_k,
            embedding=vector,
            snapshot_id=snapshot_id,
        )
        return tuple(
            _candidate_from_record(record, snapshot_id, dense_rank=rank)
            for rank, record in enumerate(records, start=1)
        )

    def _await_online(self, wait_seconds: float) -> str:
        deadline = time.monotonic() + wait_seconds
        while True:
            record = self._one(
                "SHOW VECTOR INDEXES YIELD name, state, labelsOrTypes, properties, options "
                "WHERE name = $index_name "
                "RETURN state, labelsOrTypes, properties, options",
                index_name=DENSE_INDEX_NAME,
            )
            if record is None:
                raise DenseIndexError("vector index was not created")
            _validate_index_schema(record)
            state = record["state"]
            if not isinstance(state, str):
                raise DenseIndexError("vector index returned a malformed state")
            if state == "ONLINE":
                return state
            if time.monotonic() >= deadline:
                raise DenseIndexError(f"vector index did not become ONLINE: {state}")
            time.sleep(0.1)

    def _graph_unit_count(self, snapshot_id: str) -> int:
        record = self._one(
            "MATCH (unit:LegalUnit)-[:IN_SNAPSHOT]->(:Snapshot {snapshot_id: $snapshot_id}) "
            "RETURN count(unit) AS count",
            snapshot_id=snapshot_id,
        )
        return _count_from_record(record, "graph dense-unit count")

    def _embedded_unit_count(self, snapshot_id: str) -> int:
        record = self._one(
            "MATCH (unit:LegalUnit {snapshot_id: $snapshot_id}) "
            "WHERE unit.embedding_bkai_v1 IS NOT NULL "
            "RETURN count(unit) AS count",
            snapshot_id=snapshot_id,
        )
        return _count_from_record(record, "embedded dense-unit count")

    def _embedded_unit_ids(self, snapshot_id: str) -> set[str]:
        records = self._records(
            "MATCH (unit:LegalUnit {snapshot_id: $snapshot_id}) "
            "WHERE unit.embedding_bkai_v1 IS NOT NULL "
            "RETURN unit.unit_id AS unit_id",
            snapshot_id=snapshot_id,
        )
        unit_ids = {record["unit_id"] for record in records}
        if not all(isinstance(unit_id, str) and unit_id for unit_id in unit_ids):
            raise DenseIndexError("embedded dense-unit query returned malformed unit IDs")
        return cast(set[str], unit_ids)

    def _assert_embedding_scope(self, snapshot_id: str) -> None:
        record = self._one(
            "MATCH (unit:LegalUnit) "
            "WHERE unit.embedding_bkai_v1 IS NOT NULL "
            "RETURN collect(DISTINCT unit.snapshot_id) AS snapshot_ids"
        )
        if record is None:
            raise DenseIndexError("dense embedding scope query returned no record")
        snapshot_ids = record["snapshot_ids"]
        if not isinstance(snapshot_ids, list) or not all(
            isinstance(value, str) and value for value in snapshot_ids
        ):
            raise DenseIndexError("dense embedding scope query returned malformed snapshot IDs")
        # ponytail: Neo4j 5.26 vector indexes cannot filter by snapshot; reject multiple
        # embedded snapshots until a filtered vector index or separate database is justified.
        if snapshot_ids and set(snapshot_ids) != {snapshot_id}:
            raise DenseIndexError("vector index contains embeddings from a different snapshot")

    def _one(self, query: str, **parameters: object) -> Record | None:
        records = self._records(query, **parameters)
        if len(records) > 1:
            raise DenseIndexError("expected one graph record")
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


def _default_device() -> str:
    try:
        torch = cast(Any, import_module("torch"))
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _embedding_inputs(snapshot_id: str, documents: list[ParsedDocument]) -> list[_EmbeddingInput]:
    if not documents:
        raise DenseIndexError("cannot index an empty snapshot")
    if {document.metadata.snapshot_id for document in documents} != {snapshot_id}:
        raise DenseIndexError("parsed documents do not share the requested snapshot")
    units_by_id = {unit.unit_id: unit for document in documents for unit in document.units}
    if len(units_by_id) != sum(len(document.units) for document in documents):
        raise DenseIndexError("snapshot has duplicate unit IDs")
    inputs: list[_EmbeddingInput] = []
    for document in documents:
        for unit in document.units:
            if unit.unit_type not in _DENSE_UNIT_TYPES:
                continue
            if unit.document_id != document.metadata.document_id:
                raise DenseIndexError("legal unit belongs to the wrong parsed document")
            inputs.append(
                _EmbeddingInput(
                    unit_id=unit.unit_id,
                    text=_embedding_text(document, unit, units_by_id),
                )
            )
    if not inputs:
        raise DenseIndexError("snapshot has no Article, Clause, or Point units to embed")
    return inputs


def _embedding_text(
    document: ParsedDocument, unit: LegalUnit, units_by_id: dict[str, LegalUnit]
) -> str:
    try:
        locator = " > ".join(_unit_locator(units_by_id[unit_id]) for unit_id in unit.path)
    except KeyError as exc:
        raise DenseIndexError("legal unit path refers to a missing parent") from exc
    parts = [f"Văn bản: {document.metadata.title}", f"Vị trí: {locator}"]
    if unit.title is not None:
        parts.append(unit.title)
    parts.append(unit.text)
    return "\n".join(parts)


def _unit_locator(unit: LegalUnit) -> str:
    return f"{_UNIT_LABELS[unit.unit_type]} {unit.number}"


def _batches(items: list[_EmbeddingInput], size: int) -> tuple[list[_EmbeddingInput], ...]:
    return tuple(items[start : start + size] for start in range(0, len(items), size))


def _validated_vector(vector: tuple[float, ...]) -> list[float]:
    if len(vector) != DENSE_DIMENSIONS or not all(math.isfinite(value) for value in vector):
        raise DenseIndexError("embedding model returned a malformed 768-dimensional vector")
    return list(vector)


def _count_from_record(record: Record | None, description: str) -> int:
    if record is None or not isinstance(record["count"], int):
        raise DenseIndexError(f"{description} query returned no integer")
    return record["count"]


def _validate_index_schema(record: Record) -> None:
    labels = record["labelsOrTypes"]
    properties = record["properties"]
    options = record["options"]
    index_config = options.get("indexConfig") if isinstance(options, dict) else None
    similarity = (
        index_config.get("vector.similarity_function") if isinstance(index_config, dict) else None
    )
    if (
        labels != ["LegalUnit"]
        or properties != [DENSE_EMBEDDING_PROPERTY]
        or not isinstance(index_config, dict)
        or index_config.get("vector.dimensions") != DENSE_DIMENSIONS
        or not isinstance(similarity, str)
        or similarity.casefold() != "cosine"
        or index_config.get("vector.quantization.enabled") is not False
    ):
        raise DenseIndexError("vector index does not match the R1 dense retrieval contract")


def _candidate_from_record(
    record: Record, snapshot_id: str, *, dense_rank: int
) -> RetrievalCandidate:
    unit_id = record["unit_id"]
    document_id = record["document_id"]
    unit_type = record["unit_type"]
    source_url = record["source_url"]
    text = record["text"]
    score = record["score"]
    title = record["title"]
    if not all(
        isinstance(value, str) and value for value in (unit_id, document_id, source_url, text)
    ):
        raise DenseIndexError("retrieval query returned malformed candidate text")
    if unit_type not in _DENSE_UNIT_TYPES:
        raise DenseIndexError("vector index returned a non-answer-sized legal unit")
    if not isinstance(score, (float, int)):
        raise DenseIndexError("retrieval query returned a malformed dense score")
    if title is not None and not isinstance(title, str):
        raise DenseIndexError("retrieval query returned a malformed title")
    return RetrievalCandidate(
        unit_id=unit_id,
        document_id=document_id,
        snapshot_id=snapshot_id,
        text=text,
        unit_type=cast(UnitType, unit_type),
        source_url=source_url,
        title=title,
        dense_rank=dense_rank,
        dense_score=float(score),
    )
