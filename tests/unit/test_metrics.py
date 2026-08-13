from __future__ import annotations

from datetime import date

from traffic_legal_qa.evaluation.datasets import GoldQuestion
from traffic_legal_qa.evaluation.metrics import evaluate_retrieval
from traffic_legal_qa.retrieval.lexical import RetrievalCandidate


def _question(question_id: str, unit_ids: tuple[str, ...]) -> GoldQuestion:
    return GoldQuestion(
        question_id=question_id,
        question="Question",
        question_type="definition",
        difficulty="easy",
        split="test",
        effective_at=date(2026, 8, 13),
        gold_document_ids=("doc",),
        gold_unit_ids=unit_ids,
        reviewer_notes="Source verified.",
        review_status="source_verified",
    )


def _candidate(unit_id: str) -> RetrievalCandidate:
    return RetrievalCandidate(
        unit_id=unit_id,
        document_id="doc",
        snapshot_id="snapshot",
        text="text",
        unit_type="clause",
        source_url="https://example.test/source",
        title=None,
    )


def test_retrieval_metrics_distinguish_full_partial_and_missing_gold_units() -> None:
    questions = (
        _question("q1", ("u1",)),
        _question("q2", ("u2", "u3")),
        _question("q3", ("u4",)),
    )

    evaluation = evaluate_retrieval(
        questions,
        {
            "q1": (_candidate("u1"),),
            "q2": (_candidate("u2"), _candidate("other")),
            "q3": (_candidate("other"),),
        },
    )

    assert evaluation.metrics.unit_recall_at[1] == 0.5
    assert evaluation.metrics.mrr_at_10 == 2 / 3
    assert evaluation.metrics.full_hit_count_at_10 == 1
    assert evaluation.metrics.partial_hit_count_at_10 == 1
    assert evaluation.metrics.miss_count_at_10 == 1
    assert [case.status for case in evaluation.cases] == ["full_hit", "partial_hit", "miss"]
