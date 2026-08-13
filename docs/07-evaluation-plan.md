# 07. Evaluation Plan

## Purpose

Evaluation isolates failure by layer: source contract, parser, retrieval, graph, validity, citation, generation, or operations. A single model-judge score is insufficient evidence for legal QA quality.

## Gold question set

The v1 target is 300–500 reviewed Vietnamese questions. Create 30 pilot questions before measuring or selecting a retrieval configuration. The deterministic structural graph may be imported before the pilot set exists; the pilot set prevents unmeasured claims about retrieval, rerank, or GraphRAG quality.

Each question stores:

    question_id
    question
    gold_document_ids
    gold_unit_ids
    effective_at
    answer_key or reviewer notes
    question_type
    difficulty
    review_status

Question taxonomy includes definitions, obligations, prohibitions, penalties, procedures, temporal validity, comparisons, multi-document questions, ambiguity, and out-of-domain cases.

Paraphrases with the same intent and gold units stay in one split. Temporal versions must not leak across development and test data.

## Metrics by layer

### Source and parser

- portal schema pass rate;
- raw-to-normalized reproducibility;
- hierarchy precision and recall on fixtures;
- duplicate or orphan unit count;
- catalog-to-manifest coverage.

### Retrieval

- unit and document Recall at 1, 3, 5, and 10;
- MRR;
- nDCG when graded labels exist;
- validity-aware recall;
- exact-identifier lookup accuracy.

Report macro and micro scores and inspect query categories separately.

### Citation and answer

| Dimension | Measurement |
|---|---|
| Citation existence | Every ID resolves |
| Citation membership | Every citation was selected evidence |
| Citation support | Reviewer confirms claim support |
| Version correctness | Citation is valid for effective date |
| Unsupported claim rate | Claims without adequate evidence |
| Abstention precision and recall | Abstain only when appropriate |
| Answer correctness | Reviewer rubric, secondary to citation |

ROUGE, BERTScore, and LLM-as-a-judge are supplementary. They cannot override citation review.

### System

- stage and end-to-end p50/p95 latency;
- timeout and error rate;
- active snapshot age;
- ingestion failure rate;
- cache hit rate when cache exists;
- token usage and estimated cost;
- index build duration.

## Ablations

Run R0 through R5 from [05-retrieval-and-reranking.md](05-retrieval-and-reranking.md) with the same snapshot, split, evaluator, and model settings. Add generation only after the best retrieval configuration is selected without test leakage.

## Error analysis

For every meaningful run, sample failures and label one root cause:

1. source response or normalization issue;
2. parser lost structure;
3. gold unit absent from candidate pool;
4. gold unit present but ranked too low;
5. reranker degraded rank;
6. graph expansion added noise or omitted condition;
7. validity relation incorrect or unknown;
8. generator ignored evidence;
9. citation resolver rejected an otherwise valid answer;
10. ambiguity should have triggered clarification.

Convert recurring failures into fixtures or golden cases. Do not simply tune a threshold until the aggregate metric rises.

## Proposed release targets

These are gates to review, not promises:

- unit Recall@10 at least 0.80 on held-out traffic questions;
- citation resolve rate at least 0.98;
- reviewer citation-support rate at least 0.90;
- unsupported claim rate no more than 0.05 on reviewed answers;
- all evaluation results reproducible from their recorded versions.

If a target is missed, report the root-cause analysis and limitation rather than quietly changing the threshold.

## Run record

    run_id
    snapshot_id
    catalog_version
    index_version
    question_set_version
    retrieval_config
    reranker_config
    generator_config
    prompt_version
    metric_version
    git_commit
    timestamp
