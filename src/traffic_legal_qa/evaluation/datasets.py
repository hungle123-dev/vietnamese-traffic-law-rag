"""Snapshot-bound retrieval gold-set artifacts."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from traffic_legal_qa.ingestion.models import ParsedDocument

QuestionType = Literal["definition", "prohibition", "obligation", "procedure", "penalty"]
QuestionDifficulty = Literal["easy", "medium", "hard"]
QuestionSplit = Literal["dev", "test"]
QuestionReviewStatus = Literal["source_verified", "approved"]


class GoldSetError(ValueError):
    """A retrieval gold set cannot be resolved against its frozen snapshot."""


def _require_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("must not be blank")
    return normalized


class GoldQuestion(BaseModel):
    """One citation-backed retrieval target; it is not an answer-quality label."""

    model_config = ConfigDict(frozen=True)

    question_id: str
    question: str
    question_type: QuestionType
    difficulty: QuestionDifficulty
    split: QuestionSplit
    effective_at: date
    gold_document_ids: tuple[str, ...] = Field(min_length=1)
    gold_unit_ids: tuple[str, ...] = Field(min_length=1)
    reviewer_notes: str
    review_status: QuestionReviewStatus

    _validate_text = field_validator("question_id", "question", "reviewer_notes")(_require_text)

    @field_validator("gold_document_ids", "gold_unit_ids")
    @classmethod
    def _require_distinct_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value.strip() for value in values):
            raise ValueError("must not contain blank IDs")
        if len(values) != len(set(values)):
            raise ValueError("must not contain duplicate IDs")
        return values


class GoldQuestionArtifact(BaseModel):
    """Versioned retrieval-only questions for exactly one parsed snapshot."""

    model_config = ConfigDict(frozen=True)

    artifact_version: Literal["1"]
    snapshot_id: str
    evaluation_scope: Literal["retrieval_only"]
    questions: tuple[GoldQuestion, ...] = Field(min_length=1)

    _validate_snapshot_id = field_validator("snapshot_id")(_require_text)


def load_gold_question_artifact(path: Path) -> GoldQuestionArtifact:
    """Parse a tracked gold set before resolving its citation IDs."""

    try:
        return GoldQuestionArtifact.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise GoldSetError(f"invalid gold question artifact: {path}") from exc


def resolve_gold_questions(
    artifact: GoldQuestionArtifact, documents: list[ParsedDocument]
) -> tuple[GoldQuestion, ...]:
    """Reject gold citations that cannot be located in the requested snapshot."""

    if not documents:
        raise GoldSetError("cannot resolve gold questions against an empty snapshot")
    if artifact.snapshot_id != documents[0].metadata.snapshot_id:
        raise GoldSetError("gold question artifact and parsed snapshot IDs differ")
    validate_gold_questions(artifact.questions, documents)
    return artifact.questions


def validate_gold_questions(
    questions: tuple[GoldQuestion, ...], documents: list[ParsedDocument]
) -> None:
    """Require each retrieval target to name resolvable documents and provisions."""

    if not documents:
        raise GoldSetError("cannot resolve gold questions against an empty snapshot")
    documents_by_id = {document.metadata.document_id: document for document in documents}
    if len(documents_by_id) != len(documents):
        raise GoldSetError("snapshot has duplicate document IDs")
    if len({document.metadata.snapshot_id for document in documents}) != 1:
        raise GoldSetError("gold questions must resolve against one snapshot")

    question_ids = [question.question_id for question in questions]
    if len(question_ids) != len(set(question_ids)):
        raise GoldSetError("gold question artifact has duplicate question IDs")

    units_by_id = {
        unit.unit_id: unit.document_id for document in documents for unit in document.units
    }
    if len(units_by_id) != sum(len(document.units) for document in documents):
        raise GoldSetError("snapshot has duplicate unit IDs")

    for question in questions:
        unknown_documents = set(question.gold_document_ids).difference(documents_by_id)
        if unknown_documents:
            raise GoldSetError(
                f"gold question references an unknown document: {question.question_id}"
            )
        for unit_id in question.gold_unit_ids:
            unit_document_id = units_by_id.get(unit_id)
            if unit_document_id is None:
                raise GoldSetError(
                    f"gold question references an unknown unit: {question.question_id}"
                )
            if unit_document_id not in question.gold_document_ids:
                raise GoldSetError(
                    f"gold unit does not belong to a gold document: {question.question_id}"
                )
