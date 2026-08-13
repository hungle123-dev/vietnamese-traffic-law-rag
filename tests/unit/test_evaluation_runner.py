from __future__ import annotations

from datetime import date
from typing import Literal, cast

from traffic_legal_qa.evaluation.datasets import GoldQuestion
from traffic_legal_qa.evaluation.runner import run_r0_lexical
from traffic_legal_qa.retrieval.lexical import (
    LEXICAL_INDEX_FORMAT,
    LEXICAL_INDEX_NAMES,
    LexicalIndexStatus,
    Neo4jLexicalRetriever,
    RetrievalCandidate,
)


class _Retriever:
    def __init__(self) -> None:
        self.verified = False
        self.queries: list[str] = []

    def verify_index(self, *_: object, **__: object) -> LexicalIndexStatus:
        self.verified = True
        return LexicalIndexStatus(
            snapshot_id="snapshot",
            index_names=LEXICAL_INDEX_NAMES,
            index_format=LEXICAL_INDEX_FORMAT,
            state="ONLINE",
            expected_unit_count=1,
            graph_unit_count=1,
        )

    def search(self, _: str, __: list[object], query: str) -> tuple[RetrievalCandidate, ...]:
        self.queries.append(query)
        return (
            RetrievalCandidate(
                unit_id="u-dev",
                document_id="doc",
                snapshot_id="snapshot",
                text="text",
                unit_type="article",
                source_url="https://example.test/source",
                title=None,
            ),
        )


def _question(question_id: str, split: Literal["dev", "test"], unit_id: str) -> GoldQuestion:
    return GoldQuestion(
        question_id=question_id,
        question=f"Question {question_id}",
        question_type="definition",
        difficulty="easy",
        split=split,
        effective_at=date(2026, 8, 13),
        gold_document_ids=("doc",),
        gold_unit_ids=(unit_id,),
        reviewer_notes="Source verified.",
        review_status="source_verified",
    )


def test_r0_evaluates_only_the_requested_frozen_split() -> None:
    retriever = _Retriever()

    run = run_r0_lexical(
        cast(Neo4jLexicalRetriever, retriever),
        "snapshot",
        [],
        (
            _question("q-dev", "dev", "u-dev"),
            _question("q-test", "test", "u-test"),
        ),
        "dev",
        "a" * 64,
        "commit",
    )

    assert retriever.verified
    assert retriever.queries == ["Question q-dev"]
    assert run.run_id == "snapshot::r0-lexical-3way-rrf::dev::aaaaaaaaaaaa"
    assert run.evaluation.metrics.full_hit_count_at_10 == 1
