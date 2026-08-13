"""Idempotent Neo4j projection for validated legal snapshots."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Final

from neo4j import Driver

from traffic_legal_qa.ingestion.models import LegalUnit, ParsedDocument, UnitType

_UNIT_LABELS: Final[dict[UnitType, str]] = {
    "part": "Part",
    "chapter": "Chapter",
    "section": "Section",
    "article": "Article",
    "clause": "Clause",
    "point": "Point",
}
_HIERARCHY_RELATIONSHIPS: Final[dict[UnitType, str]] = {
    "part": "HAS_PART",
    "chapter": "HAS_CHAPTER",
    "section": "HAS_SECTION",
    "article": "HAS_ARTICLE",
    "clause": "HAS_CLAUSE",
    "point": "HAS_POINT",
}
_METADATA_RELATIONSHIPS: Final[dict[str, str]] = {
    "DocumentType": "HAS_TYPE",
    "EffectStatus": "HAS_STATUS",
    "Field": "IN_FIELD",
    "Organization": "ISSUED_BY",
    "Signer": "SIGNED_BY",
}


class GraphImportError(RuntimeError):
    """A validated snapshot could not be projected or reconciled with Neo4j."""


@dataclass(frozen=True)
class GraphCounts:
    """Expected or observed structural graph counts for one snapshot."""

    node_counts: dict[str, int]
    relationship_counts: dict[str, int]


@dataclass(frozen=True)
class GraphVerification:
    """A graph count reconciliation that can be serialized by the CLI."""

    snapshot_id: str
    expected: GraphCounts
    actual: GraphCounts

    @property
    def is_valid(self) -> bool:
        return self.expected == self.actual

    def model_dump(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "is_valid": self.is_valid,
            "expected": {
                "node_counts": self.expected.node_counts,
                "relationship_counts": self.expected.relationship_counts,
            },
            "actual": {
                "node_counts": self.actual.node_counts,
                "relationship_counts": self.actual.relationship_counts,
            },
        }


def expected_counts(documents: list[ParsedDocument]) -> GraphCounts:
    """Derive the only graph counts Phase 2A is allowed to create."""

    _validate_documents(documents)
    unit_counts = Counter(unit.unit_type for document in documents for unit in document.units)
    field_names: set[str] = set()
    organization_names: set[str] = set()
    signer_names: set[str] = set()
    document_types: set[str] = set()
    effect_statuses: set[str] = set()
    field_relationship_count = 0

    for document in documents:
        metadata = document.metadata
        if metadata.portal_document_type is not None:
            document_types.add(metadata.portal_document_type)
        if metadata.source_effect_status is not None:
            effect_statuses.add(metadata.source_effect_status)
        organization_names.update(metadata.issuing_organs)
        signer_names.update(signer.name for signer in metadata.signers)
        field_sources: defaultdict[str, set[str]] = defaultdict(set)
        for source, names in (("fields", metadata.fields), ("majors", metadata.majors)):
            for name in names:
                field_sources[name].add(source)
        field_names.update(field_sources)
        field_relationship_count += len(field_sources)

    node_counts = {
        "Snapshot": 1,
        "Document": len(documents),
        "DocumentType": len(document_types),
        "EffectStatus": len(effect_statuses),
        "Field": len(field_names),
        "Organization": len(organization_names),
        "Signer": len(signer_names),
        **{_UNIT_LABELS[unit_type]: unit_counts[unit_type] for unit_type in _UNIT_LABELS},
    }
    relationship_counts = {
        "IN_SNAPSHOT": len(documents) + sum(unit_counts.values()),
        "HAS_TYPE": sum(
            document.metadata.portal_document_type is not None for document in documents
        ),
        "HAS_STATUS": sum(
            document.metadata.source_effect_status is not None for document in documents
        ),
        "IN_FIELD": field_relationship_count,
        "ISSUED_BY": sum(len(document.metadata.issuing_organs) for document in documents),
        "SIGNED_BY": sum(len(document.metadata.signers) for document in documents),
        **{
            _HIERARCHY_RELATIONSHIPS[unit_type]: unit_counts[unit_type]
            for unit_type in _UNIT_LABELS
        },
    }
    return GraphCounts(node_counts=node_counts, relationship_counts=relationship_counts)


class GraphSnapshotImporter:
    """Projects one validated snapshot into a single concrete Neo4j database."""

    def __init__(self, driver: Driver, *, database: str = "neo4j") -> None:
        if not database.strip():
            raise ValueError("database must not be blank")
        self._driver = driver
        self._database = database

    def import_snapshot(
        self, snapshot_id: str, documents: list[ParsedDocument]
    ) -> GraphVerification:
        """MERGE the structural graph, then reject any count mismatch immediately."""

        _validate_documents(documents, snapshot_id)
        expected = expected_counts(documents)
        self._create_constraints()
        # ponytail: resumable MERGE batches are safe before snapshot promotion; use one transaction
        # only when an active-snapshot pointer could expose a partial import.
        self._write_snapshot(snapshot_id, documents)
        self._write_documents(snapshot_id, documents)
        self._write_metadata(documents)
        self._write_units(snapshot_id, documents)
        self._write_hierarchy(snapshot_id, documents)
        verification = self.verify_snapshot(snapshot_id, expected)
        if not verification.is_valid:
            raise GraphImportError(f"graph count mismatch: {verification.model_dump()}")
        return verification

    def verify_snapshot(self, snapshot_id: str, expected: GraphCounts) -> GraphVerification:
        """Count the scoped graph subgraph without trusting importer write counters."""

        actual_nodes = {
            label: self._node_count(snapshot_id, label) for label in expected.node_counts
        }
        actual_relationships = {
            relationship: self._relationship_count(
                snapshot_id,
                relationship,
                use_dynamic_type=expected.relationship_counts[relationship] == 0,
            )
            for relationship in expected.relationship_counts
        }
        return GraphVerification(
            snapshot_id=snapshot_id,
            expected=expected,
            actual=GraphCounts(actual_nodes, actual_relationships),
        )

    def _create_constraints(self) -> None:
        constraints = [
            "CREATE CONSTRAINT snapshot_id IF NOT EXISTS FOR (node:Snapshot) "
            "REQUIRE node.snapshot_id IS UNIQUE",
            "CREATE CONSTRAINT document_key IF NOT EXISTS FOR (node:Document) "
            "REQUIRE node.document_key IS UNIQUE",
            *[
                f"CREATE CONSTRAINT {label.lower()}_unit_key IF NOT EXISTS "
                f"FOR (node:{label}) REQUIRE node.unit_key IS UNIQUE"
                for label in _UNIT_LABELS.values()
            ],
            *[
                f"CREATE CONSTRAINT {label.lower()}_name IF NOT EXISTS "
                f"FOR (node:{label}) REQUIRE node.name IS UNIQUE"
                for label in _METADATA_RELATIONSHIPS
            ],
        ]
        for query in constraints:
            self._execute(query)

    def _write_snapshot(self, snapshot_id: str, documents: list[ParsedDocument]) -> None:
        self._execute(
            "MERGE (snapshot:Snapshot {snapshot_id: $snapshot_id}) "
            "SET snapshot.artifact_version = $artifact_version, "
            "snapshot.document_count = $document_count",
            snapshot_id=snapshot_id,
            artifact_version=documents[0].artifact_version,
            document_count=len(documents),
        )

    def _write_documents(self, snapshot_id: str, documents: list[ParsedDocument]) -> None:
        rows = [_document_row(document) for document in documents]
        self._execute(
            "UNWIND $rows AS row "
            "MERGE (document:Document {document_key: row.document_key}) "
            "SET document += row.properties "
            "WITH document "
            "MATCH (snapshot:Snapshot {snapshot_id: $snapshot_id}) "
            "MERGE (document)-[:IN_SNAPSHOT]->(snapshot)",
            rows=rows,
            snapshot_id=snapshot_id,
        )

    def _write_metadata(self, documents: list[ParsedDocument]) -> None:
        metadata_rows = {
            "DocumentType": _document_type_rows(documents),
            "EffectStatus": _effect_status_rows(documents),
            "Field": _field_rows(documents),
            "Organization": _organization_rows(documents),
            "Signer": _signer_rows(documents),
        }
        for label, rows in metadata_rows.items():
            if not rows:
                continue
            relationship = _METADATA_RELATIONSHIPS[label]
            extra_set = " SET relation.sources = row.sources" if label == "Field" else ""
            if label == "Signer":
                extra_set = " SET relation.job_title = row.job_title"
            self._execute(
                "UNWIND $rows AS row "
                "MATCH (document:Document {document_key: row.document_key}) "
                f"MERGE (node:{label} {{name: row.name}}) "
                f"MERGE (document)-[relation:{relationship}]->(node)" + extra_set,
                rows=rows,
            )

    def _write_units(self, snapshot_id: str, documents: list[ParsedDocument]) -> None:
        for unit_type, label in _UNIT_LABELS.items():
            rows = [
                _unit_row(document, unit)
                for document in documents
                for unit in document.units
                if unit.unit_type == unit_type
            ]
            if not rows:
                continue
            self._execute(
                "UNWIND $rows AS row "
                f"MERGE (unit:{label} {{unit_key: row.unit_key}}) "
                "SET unit += row.properties "
                "WITH unit "
                "MATCH (snapshot:Snapshot {snapshot_id: $snapshot_id}) "
                "MERGE (unit)-[:IN_SNAPSHOT]->(snapshot)",
                rows=rows,
                snapshot_id=snapshot_id,
            )

    def _write_hierarchy(self, snapshot_id: str, documents: list[ParsedDocument]) -> None:
        for unit_type, label in _UNIT_LABELS.items():
            relationship = _HIERARCHY_RELATIONSHIPS[unit_type]
            rows = [
                _unit_row(document, unit)
                for document in documents
                for unit in document.units
                if unit.unit_type == unit_type
            ]
            roots = [row for row in rows if row["parent_unit_key"] is None]
            children = [row for row in rows if row["parent_unit_key"] is not None]
            if roots:
                self._execute(
                    "UNWIND $rows AS row "
                    "MATCH (document:Document {document_key: row.document_key}) "
                    f"MATCH (unit:{label} {{unit_key: row.unit_key}}) "
                    f"MERGE (document)-[:{relationship}]->(unit)",
                    rows=roots,
                )
            if children:
                self._execute(
                    "UNWIND $rows AS row "
                    "MATCH (parent {unit_key: row.parent_unit_key, snapshot_id: $snapshot_id}) "
                    f"MATCH (unit:{label} {{unit_key: row.unit_key}}) "
                    f"MERGE (parent)-[:{relationship}]->(unit)",
                    rows=children,
                    snapshot_id=snapshot_id,
                )

    def _node_count(self, snapshot_id: str, label: str) -> int:
        if label == "Snapshot":
            query = "MATCH (node:Snapshot {snapshot_id: $snapshot_id}) RETURN count(node) AS count"
        elif label == "Document":
            query = (
                "MATCH (node:Document)-[:IN_SNAPSHOT]->(:Snapshot {snapshot_id: $snapshot_id}) "
                "RETURN count(node) AS count"
            )
        elif label in _METADATA_RELATIONSHIPS:
            query = (
                f"MATCH (:Document {{snapshot_id: $snapshot_id}})"
                f"-[:{_METADATA_RELATIONSHIPS[label]}]"
                f"->(node:{label}) RETURN count(DISTINCT node) AS count"
            )
        else:
            query = (
                f"MATCH (node:{label})-[:IN_SNAPSHOT]->(:Snapshot {{snapshot_id: $snapshot_id}}) "
                "RETURN count(node) AS count"
            )
        return self._count(query, snapshot_id=snapshot_id)

    def _relationship_count(
        self, snapshot_id: str, relationship: str, *, use_dynamic_type: bool
    ) -> int:
        if relationship == "IN_SNAPSHOT":
            query = (
                "MATCH ()-[relation:IN_SNAPSHOT]->(:Snapshot {snapshot_id: $snapshot_id}) "
                "RETURN count(relation) AS count"
            )
        elif relationship in _METADATA_RELATIONSHIPS.values():
            query = (
                f"MATCH (:Document {{snapshot_id: $snapshot_id}})-[relation:{relationship}]->() "
                "RETURN count(relation) AS count"
            )
        else:
            unit_type = next(
                unit_type
                for unit_type, hierarchy_relationship in _HIERARCHY_RELATIONSHIPS.items()
                if hierarchy_relationship == relationship
            )
            label = _UNIT_LABELS[unit_type]
            relationship_pattern = (
                "-[relation]->" if use_dynamic_type else f"-[relation:{relationship}]->"
            )
            type_filter = "WHERE type(relation) = $relationship " if use_dynamic_type else ""
            query = (
                f"MATCH (source {{snapshot_id: $snapshot_id}}){relationship_pattern}"
                f"(:{label} {{snapshot_id: $snapshot_id}}) {type_filter}"
                "RETURN count(relation) AS count"
            )
        parameters: dict[str, object] = {"snapshot_id": snapshot_id}
        if use_dynamic_type:
            parameters["relationship"] = relationship
        return self._count(query, **parameters)

    def _count(self, query: str, **parameters: object) -> int:
        records, _, _ = self._driver.execute_query(
            query,
            parameters_=parameters,
            database_=self._database,
        )
        if len(records) != 1:
            raise GraphImportError("graph count query did not return one row")
        count = records[0]["count"]
        if not isinstance(count, int):
            raise GraphImportError("graph count query did not return an integer")
        return count

    def _execute(self, query: str, **parameters: object) -> None:
        self._driver.execute_query(
            query,
            parameters_=parameters,
            database_=self._database,
        )


def _validate_documents(documents: list[ParsedDocument], snapshot_id: str | None = None) -> None:
    if not documents:
        raise GraphImportError("cannot project an empty snapshot")
    document_ids = {document.metadata.document_id for document in documents}
    if len(document_ids) != len(documents):
        raise GraphImportError("snapshot has duplicate document IDs")
    snapshots = {document.metadata.snapshot_id for document in documents}
    if len(snapshots) != 1 or (snapshot_id is not None and snapshots != {snapshot_id}):
        raise GraphImportError("parsed documents do not share the requested snapshot")


def _document_key(document: ParsedDocument) -> str:
    return f"{document.metadata.snapshot_id}::{document.metadata.document_id}"


def _document_row(document: ParsedDocument) -> dict[str, object]:
    metadata = document.metadata
    return {
        "document_key": _document_key(document),
        "properties": {
            "document_key": _document_key(document),
            "document_id": metadata.document_id,
            "portal_document_guid": metadata.portal_document_guid,
            "title": metadata.title,
            "document_type": metadata.document_type,
            "portal_document_type": metadata.portal_document_type,
            "issuer": metadata.issuer,
            "issued_date": metadata.issued_date,
            "effective_from": metadata.effective_from,
            "effective_to": metadata.effective_to,
            "status": metadata.status,
            "source_effect_status": metadata.source_effect_status,
            "source_url": metadata.source_url,
            "content_url": metadata.content_url,
            "content_sha256": metadata.content_sha256,
            "snapshot_id": metadata.snapshot_id,
            "artifact_version": document.artifact_version,
            "parser_version": document.parser_version,
        },
    }


def _unit_row(document: ParsedDocument, unit: LegalUnit) -> dict[str, object]:
    return {
        "document_key": _document_key(document),
        "unit_key": f"{document.metadata.snapshot_id}::{unit.unit_id}",
        "parent_unit_key": (
            f"{document.metadata.snapshot_id}::{unit.parent_id}"
            if unit.parent_id is not None
            else None
        ),
        "properties": {
            "unit_key": f"{document.metadata.snapshot_id}::{unit.unit_id}",
            "unit_id": unit.unit_id,
            "document_id": unit.document_id,
            "unit_type": unit.unit_type,
            "number": unit.number,
            "title": unit.title,
            "text": unit.text,
            "parent_id": unit.parent_id,
            "path": list(unit.path),
            "parser_version": document.parser_version,
            "snapshot_id": document.metadata.snapshot_id,
        },
    }


def _document_type_rows(documents: list[ParsedDocument]) -> list[dict[str, object]]:
    return [
        {"document_key": _document_key(document), "name": document.metadata.portal_document_type}
        for document in documents
        if document.metadata.portal_document_type is not None
    ]


def _effect_status_rows(documents: list[ParsedDocument]) -> list[dict[str, object]]:
    return [
        {"document_key": _document_key(document), "name": document.metadata.source_effect_status}
        for document in documents
        if document.metadata.source_effect_status is not None
    ]


def _field_rows(documents: list[ParsedDocument]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for document in documents:
        sources_by_name: defaultdict[str, set[str]] = defaultdict(set)
        metadata_groups = (
            ("fields", document.metadata.fields),
            ("majors", document.metadata.majors),
        )
        for source, names in metadata_groups:
            for name in names:
                sources_by_name[name].add(source)
        rows.extend(
            {
                "document_key": _document_key(document),
                "name": name,
                "sources": sorted(sources),
            }
            for name, sources in sorted(sources_by_name.items())
        )
    return rows


def _organization_rows(documents: list[ParsedDocument]) -> list[dict[str, object]]:
    return [
        {"document_key": _document_key(document), "name": name}
        for document in documents
        for name in document.metadata.issuing_organs
    ]


def _signer_rows(documents: list[ParsedDocument]) -> list[dict[str, object]]:
    return [
        {
            "document_key": _document_key(document),
            "name": signer.name,
            "job_title": signer.job_title,
        }
        for document in documents
        for signer in document.metadata.signers
    ]
