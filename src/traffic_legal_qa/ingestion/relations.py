"""Reviewed legal-change relation artifacts bound to one parsed snapshot."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from traffic_legal_qa.ingestion.models import ParsedDocument

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
AmendmentType = Literal["sửa đổi", "bổ sung", "bãi bỏ", "thay thế", "sửa đổi, bổ sung"]


class RelationArtifactError(ValueError):
    """A reviewed relation artifact cannot be trusted for graph projection."""


def _require_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("must not be blank")
    return normalized


class RelationEndpoint(BaseModel):
    """One document-level or provision-level endpoint in a legal-change relation."""

    model_config = ConfigDict(frozen=True)

    document_id: str
    unit_id: str | None = None

    _validate_document_id = field_validator("document_id")(_require_text)

    @field_validator("unit_id")
    @classmethod
    def _normalize_optional_unit_id(cls, value: str | None) -> str | None:
        return _require_text(value) if value is not None else None


class ApprovedRelation(BaseModel):
    """One human-reviewed AMENDS edge with immutable primary-source evidence."""

    model_config = ConfigDict(frozen=True)

    relation_id: str
    relation_type: Literal["AMENDS"]
    amendment_type: AmendmentType
    source: RelationEndpoint
    target: RelationEndpoint
    evidence_unit_id: str
    source_url: str
    raw_sha256: str
    provenance: Literal["reviewed_primary_source"]
    review_status: Literal["approved"]
    reviewed_by: str
    reviewed_at: date
    note: str | None = None

    _validate_text = field_validator(
        "relation_id", "evidence_unit_id", "source_url", "reviewed_by"
    )(_require_text)

    @field_validator("source_url")
    @classmethod
    def _require_https_url(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("must use HTTPS")
        return value

    @field_validator("raw_sha256")
    @classmethod
    def _require_sha256(cls, value: str) -> str:
        if not _SHA256.fullmatch(value):
            raise ValueError("must be a lowercase SHA-256 hex digest")
        return value


class ApprovedRelationArtifact(BaseModel):
    """The only relation artifact that a graph import may consume."""

    model_config = ConfigDict(frozen=True)

    artifact_version: Literal["1"]
    snapshot_id: str
    relations: tuple[ApprovedRelation, ...] = Field(min_length=1)

    _validate_snapshot_id = field_validator("snapshot_id")(_require_text)


def load_approved_relation_artifact(path: Path) -> ApprovedRelationArtifact:
    """Parse one approved relation file without resolving it against a snapshot yet."""

    try:
        return ApprovedRelationArtifact.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise RelationArtifactError(f"invalid approved relation artifact: {path}") from exc


def resolve_approved_relations(
    artifact: ApprovedRelationArtifact, documents: list[ParsedDocument]
) -> tuple[ApprovedRelation, ...]:
    """Reject records whose evidence or endpoints do not resolve in the requested snapshot."""

    if not documents:
        raise RelationArtifactError("cannot resolve relations against an empty snapshot")
    if artifact.snapshot_id != documents[0].metadata.snapshot_id:
        raise RelationArtifactError("relation artifact and parsed snapshot IDs differ")
    validate_approved_relations(artifact.relations, documents)
    return artifact.relations


def validate_approved_relations(
    relations: tuple[ApprovedRelation, ...], documents: list[ParsedDocument]
) -> None:
    """Reject relation rows that cannot be safely attached to parsed snapshot records."""

    if not documents:
        raise RelationArtifactError("cannot resolve relations against an empty snapshot")
    documents_by_id = {document.metadata.document_id: document for document in documents}
    if len(documents_by_id) != len(documents):
        raise RelationArtifactError("snapshot has duplicate document IDs")
    if len({document.metadata.snapshot_id for document in documents}) != 1:
        raise RelationArtifactError("relations must resolve against one snapshot")

    relation_ids = [relation.relation_id for relation in relations]
    if len(relation_ids) != len(set(relation_ids)):
        raise RelationArtifactError("relation artifact has duplicate relation IDs")

    unit_ids_by_document = {
        document_id: {unit.unit_id for unit in document.units}
        for document_id, document in documents_by_id.items()
    }
    for relation in relations:
        source_document = documents_by_id.get(relation.source.document_id)
        target_document = documents_by_id.get(relation.target.document_id)
        if source_document is None or target_document is None:
            raise RelationArtifactError(
                f"relation references an unknown document: {relation.relation_id}"
            )
        if relation.source.document_id == relation.target.document_id:
            raise RelationArtifactError(f"relation is not cross-document: {relation.relation_id}")
        if relation.raw_sha256 != source_document.metadata.content_sha256:
            raise RelationArtifactError(
                f"relation raw hash differs from source: {relation.relation_id}"
            )
        if relation.source_url != source_document.metadata.source_url:
            raise RelationArtifactError(
                f"relation source URL differs from source: {relation.relation_id}"
            )
        _require_resolved_unit(
            relation.source.unit_id, unit_ids_by_document[relation.source.document_id], relation
        )
        _require_resolved_unit(
            relation.target.unit_id, unit_ids_by_document[relation.target.document_id], relation
        )
        if relation.evidence_unit_id not in unit_ids_by_document[relation.source.document_id]:
            raise RelationArtifactError(
                f"relation evidence unit is unresolved: {relation.relation_id}"
            )


def _require_resolved_unit(
    unit_id: str | None, available_unit_ids: set[str], relation: ApprovedRelation
) -> None:
    if unit_id is not None and unit_id not in available_unit_ids:
        raise RelationArtifactError(f"relation endpoint unit is unresolved: {relation.relation_id}")
