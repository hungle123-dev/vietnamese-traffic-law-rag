from __future__ import annotations

from datetime import UTC, datetime

import pytest

from traffic_legal_qa.evaluation.datasets import (
    GoldQuestionArtifact,
    GoldSetError,
    resolve_gold_questions,
)
from traffic_legal_qa.ingestion.models import CanonicalMetadata, LegalUnit, ParsedDocument

SNAPSHOT_ID = "traffic-2026-08-13-v1"


def _document(document_id: str) -> ParsedDocument:
    unit_id = f"{document_id}::article::1::clause::1"
    return ParsedDocument(
        artifact_version="2",
        metadata=CanonicalMetadata(
            document_id=document_id,
            portal_document_guid=f"guid-{document_id}",
            title=f"Document {document_id}",
            document_type="decree",
            status="current",
            source_url=f"https://phapluat.gov.vn/legal-documents/{document_id}",
            content_url=f"https://phapluat.gov.vn/api/{document_id}",
            retrieved_at=datetime(2026, 8, 13, tzinfo=UTC),
            content_sha256="a" * 64,
            snapshot_id=SNAPSHOT_ID,
        ),
        normalizer_version="1",
        parser_version="2",
        units=(
            LegalUnit(
                unit_id=unit_id,
                document_id=document_id,
                unit_type="clause",
                number="1",
                text="Source text.",
                path=(f"{document_id}::article::1", unit_id),
            ),
        ),
    )


def _artifact(document_id: str, unit_id: str) -> GoldQuestionArtifact:
    return GoldQuestionArtifact.model_validate(
        {
            "artifact_version": "1",
            "snapshot_id": SNAPSHOT_ID,
            "evaluation_scope": "retrieval_only",
            "questions": [
                {
                    "question_id": "traffic-2026-08-13-v1::q001",
                    "question": "What does the source provision require?",
                    "question_type": "obligation",
                    "difficulty": "easy",
                    "split": "dev",
                    "effective_at": "2026-08-13",
                    "gold_document_ids": [document_id],
                    "gold_unit_ids": [unit_id],
                    "reviewer_notes": "Citation has been source-verified.",
                    "review_status": "source_verified",
                }
            ],
        }
    )


def test_resolve_gold_questions_requires_resolvable_snapshot_citations() -> None:
    document = _document("new/2026/NĐ-CP")
    artifact = _artifact(document.metadata.document_id, document.units[0].unit_id)

    assert resolve_gold_questions(artifact, [document]) == artifact.questions


def test_resolve_gold_questions_rejects_a_unit_from_another_document() -> None:
    source = _document("new/2026/NĐ-CP")
    other = _document("old/2024/NĐ-CP")
    artifact = _artifact(source.metadata.document_id, other.units[0].unit_id)

    with pytest.raises(GoldSetError, match="does not belong to a gold document"):
        resolve_gold_questions(artifact, [source, other])
