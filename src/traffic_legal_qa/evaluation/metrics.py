"""Deterministic retrieval metrics over source-backed gold provision IDs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from traffic_legal_qa.evaluation.datasets import GoldQuestion
from traffic_legal_qa.retrieval.lexical import RetrievalCandidate

_K_VALUES: Final = (1, 3, 5, 10)


@dataclass(frozen=True)
class EvaluationCase:
    """One held-out query and the candidate IDs needed for error analysis."""

    question_id: str
    question_type: str
    difficulty: str
    gold_document_ids: tuple[str, ...]
    gold_unit_ids: tuple[str, ...]
    ranked_document_ids: tuple[str, ...]
    ranked_unit_ids: tuple[str, ...]
    status: str

    def model_dump(self) -> dict[str, object]:
        return {
            "question_id": self.question_id,
            "question_type": self.question_type,
            "difficulty": self.difficulty,
            "gold_document_ids": list(self.gold_document_ids),
            "gold_unit_ids": list(self.gold_unit_ids),
            "ranked_document_ids": list(self.ranked_document_ids),
            "ranked_unit_ids": list(self.ranked_unit_ids),
            "status": self.status,
        }


@dataclass(frozen=True)
class RetrievalMetrics:
    """Macro recall and MRR, reported separately for units and documents."""

    unit_recall_at: dict[int, float]
    document_recall_at: dict[int, float]
    mrr_at_10: float
    full_hit_count_at_10: int
    partial_hit_count_at_10: int
    miss_count_at_10: int

    def model_dump(self) -> dict[str, object]:
        return {
            "unit_recall_at": {str(key): value for key, value in self.unit_recall_at.items()},
            "document_recall_at": {
                str(key): value for key, value in self.document_recall_at.items()
            },
            "mrr_at_10": self.mrr_at_10,
            "full_hit_count_at_10": self.full_hit_count_at_10,
            "partial_hit_count_at_10": self.partial_hit_count_at_10,
            "miss_count_at_10": self.miss_count_at_10,
        }


@dataclass(frozen=True)
class RetrievalEvaluation:
    """Metric result plus per-question evidence for a single retrieval run."""

    metrics: RetrievalMetrics
    cases: tuple[EvaluationCase, ...]


def evaluate_retrieval(
    questions: tuple[GoldQuestion, ...],
    candidates_by_question_id: dict[str, tuple[RetrievalCandidate, ...]],
) -> RetrievalEvaluation:
    """Score only resolvable gold IDs; no model judge or generated prose is involved."""

    if not questions:
        raise ValueError("cannot evaluate an empty question set")
    question_ids = {question.question_id for question in questions}
    if set(candidates_by_question_id) != question_ids:
        raise ValueError("retrieval results do not match the requested question IDs")

    unit_recall_totals = {k: 0.0 for k in _K_VALUES}
    document_recall_totals = {k: 0.0 for k in _K_VALUES}
    reciprocal_rank_total = 0.0
    cases: list[EvaluationCase] = []
    full_hit_count = 0
    partial_hit_count = 0
    miss_count = 0

    for question in questions:
        candidates = candidates_by_question_id[question.question_id]
        ranked_unit_ids = tuple(candidate.unit_id for candidate in candidates)
        ranked_document_ids = tuple(candidate.document_id for candidate in candidates)
        gold_units = set(question.gold_unit_ids)
        gold_documents = set(question.gold_document_ids)
        for k in _K_VALUES:
            unit_recall_totals[k] += len(gold_units.intersection(ranked_unit_ids[:k])) / len(
                gold_units
            )
            document_recall_totals[k] += len(
                gold_documents.intersection(ranked_document_ids[:k])
            ) / len(gold_documents)
        first_gold_rank = next(
            (
                rank
                for rank, unit_id in enumerate(ranked_unit_ids[:10], start=1)
                if unit_id in gold_units
            ),
            None,
        )
        if first_gold_rank is not None:
            reciprocal_rank_total += 1 / first_gold_rank
        matched_at_10 = gold_units.intersection(ranked_unit_ids[:10])
        if matched_at_10 == gold_units:
            status = "full_hit"
            full_hit_count += 1
        elif matched_at_10:
            status = "partial_hit"
            partial_hit_count += 1
        else:
            status = "miss"
            miss_count += 1
        cases.append(
            EvaluationCase(
                question_id=question.question_id,
                question_type=question.question_type,
                difficulty=question.difficulty,
                gold_document_ids=question.gold_document_ids,
                gold_unit_ids=question.gold_unit_ids,
                ranked_document_ids=ranked_document_ids,
                ranked_unit_ids=ranked_unit_ids,
                status=status,
            )
        )

    count = len(questions)
    return RetrievalEvaluation(
        metrics=RetrievalMetrics(
            unit_recall_at={key: total / count for key, total in unit_recall_totals.items()},
            document_recall_at={
                key: total / count for key, total in document_recall_totals.items()
            },
            mrr_at_10=reciprocal_rank_total / count,
            full_hit_count_at_10=full_hit_count,
            partial_hit_count_at_10=partial_hit_count,
            miss_count_at_10=miss_count,
        ),
        cases=tuple(cases),
    )
