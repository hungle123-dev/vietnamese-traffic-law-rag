"""Reproducible R0 lexical evaluation orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from traffic_legal_qa.evaluation.datasets import GoldQuestion
from traffic_legal_qa.evaluation.metrics import RetrievalEvaluation, evaluate_retrieval
from traffic_legal_qa.ingestion.models import ParsedDocument
from traffic_legal_qa.retrieval.lexical import LexicalIndexStatus, Neo4jLexicalRetriever


@dataclass(frozen=True)
class R0EvaluationRun:
    """One lexical-only result with enough metadata to reproduce its inputs."""

    run_id: str
    snapshot_id: str
    split: str
    question_set_sha256: str
    git_commit: str | None
    created_at: datetime
    index: LexicalIndexStatus
    evaluation: RetrievalEvaluation

    def model_dump(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "snapshot_id": self.snapshot_id,
            "split": self.split,
            "question_set_sha256": self.question_set_sha256,
            "git_commit": self.git_commit,
            "created_at": self.created_at.isoformat(),
            "retrieval_config": {
                "name": "r0-lexical",
                "exact_lookup": "document-id plus optional Article/Clause/Point locator",
                "lexical_index": self.index.index_name,
                "lexical_index_format": self.index.index_format,
                "top_k": 10,
            },
            "index": self.index.model_dump(),
            "metrics": self.evaluation.metrics.model_dump(),
            "cases": [case.model_dump() for case in self.evaluation.cases],
        }


def run_r0_lexical(
    retriever: Neo4jLexicalRetriever,
    snapshot_id: str,
    documents: list[ParsedDocument],
    questions: tuple[GoldQuestion, ...],
    split: str,
    question_set_sha256: str,
    git_commit: str | None,
) -> R0EvaluationRun:
    """Search a fixed split and score it without tuning against its held-out questions."""

    if split not in {"dev", "test"}:
        raise ValueError("split must be dev or test")
    selected_questions = tuple(question for question in questions if question.split == split)
    if not selected_questions:
        raise ValueError(f"gold set has no {split} questions")
    index = retriever.verify_index(snapshot_id, documents)
    candidates_by_question_id = {
        question.question_id: retriever.search(snapshot_id, documents, question.question)
        for question in selected_questions
    }
    evaluation = evaluate_retrieval(selected_questions, candidates_by_question_id)
    return R0EvaluationRun(
        run_id=f"{snapshot_id}::r0-lexical::{split}::{question_set_sha256[:12]}",
        snapshot_id=snapshot_id,
        split=split,
        question_set_sha256=question_set_sha256,
        git_commit=git_commit,
        created_at=datetime.now(UTC),
        index=index,
        evaluation=evaluation,
    )


def write_evaluation_run(path: Path, run: R0EvaluationRun) -> Path:
    """Persist one generated report outside version-controlled source inputs."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(run.model_dump(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
