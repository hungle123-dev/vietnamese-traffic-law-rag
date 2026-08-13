"""Curator commands for the first ingestion slice."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from neo4j import GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError
from pydantic import ValidationError

from traffic_legal_qa.evaluation.datasets import (
    load_gold_question_artifact,
    resolve_gold_questions,
)
from traffic_legal_qa.evaluation.runner import run_r0_lexical, write_evaluation_run
from traffic_legal_qa.graph.importer import GraphImportError, GraphSnapshotImporter, expected_counts
from traffic_legal_qa.ingestion.models import ParsedDocument, ReviewedSource
from traffic_legal_qa.ingestion.pipeline import IngestionPipeline
from traffic_legal_qa.ingestion.portal import PortalClient, PortalError
from traffic_legal_qa.ingestion.relations import (
    ApprovedRelation,
    load_approved_relation_artifact,
    resolve_approved_relations,
)
from traffic_legal_qa.ingestion.storage import ArtifactStore
from traffic_legal_qa.retrieval.lexical import LexicalIndexError, Neo4jLexicalRetriever

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _load_sources(catalog_path: Path) -> list[ReviewedSource]:
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        snapshot_id = catalog["snapshot_id"]
        sources = catalog["sources"]
        if not isinstance(snapshot_id, str) or not isinstance(sources, list):
            raise ValueError("catalog must have snapshot_id and sources")
        reviewed_sources = [
            ReviewedSource.model_validate({**source, "snapshot_id": snapshot_id})
            for source in sources
        ]
        if not reviewed_sources:
            raise ValueError("catalog must include at least one reviewed source")
        document_ids = [source.expected_document_id for source in reviewed_sources]
        if len(document_ids) != len(set(document_ids)):
            raise ValueError("catalog contains duplicate document IDs")
        return reviewed_sources
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as exc:
        raise typer.BadParameter(f"invalid reviewed catalog: {catalog_path}") from exc


def _select_source(catalog_path: Path, document_id: str) -> ReviewedSource:
    for source in _load_sources(catalog_path):
        if source.expected_document_id == document_id:
            return source
    raise typer.BadParameter(f"document ID is not in the reviewed catalog: {document_id}")


def _validated_snapshot(
    snapshot_id: str, data_root: Path
) -> list[tuple[dict[str, str], ParsedDocument]]:
    manifest_path = data_root / "manifests" / f"{snapshot_id}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents = manifest["documents"]
    if manifest["snapshot_id"] != snapshot_id or not isinstance(documents, list):
        raise ValueError("invalid manifest envelope")

    fields = (
        "document_id",
        "portal_document_guid",
        "content_sha256",
        "parsed_path",
        "normalizer_version",
        "parser_version",
        "artifact_version",
    )
    validated: list[tuple[dict[str, str], ParsedDocument]] = []
    document_ids: set[str] = set()
    for document in documents:
        if not isinstance(document, dict) or not all(
            isinstance(document.get(key), str) for key in fields
        ):
            raise ValueError("invalid manifest document")
        entry = {key: document[key] for key in fields}
        document_id = entry["document_id"]
        if document_id in document_ids:
            raise ValueError(f"duplicate manifest document: {document_id}")
        document_ids.add(document_id)
        raw_hash = entry["content_sha256"]
        parsed_path = (data_root / entry["parsed_path"]).resolve()
        if not parsed_path.is_relative_to(data_root.resolve()):
            raise ValueError("manifest path escapes data root")
        raw_path = data_root / "raw" / f"{raw_hash}.json"
        if hashlib.sha256(raw_path.read_bytes()).hexdigest() != raw_hash:
            raise ValueError(f"raw hash mismatch: {document_id}")
        receipt_path = data_root / "receipts" / f"{raw_hash}.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if not isinstance(receipt, dict) or receipt.get("content_sha256") != raw_hash:
            raise ValueError(f"raw receipt mismatch: {document_id}")
        receipt_time = receipt.get("retrieved_at")
        if not isinstance(receipt_time, str) or datetime.fromisoformat(receipt_time).tzinfo is None:
            raise ValueError(f"raw receipt timestamp mismatch: {document_id}")
        parsed = ParsedDocument.model_validate_json(parsed_path.read_text(encoding="utf-8"))
        if parsed.metadata.document_id != document_id:
            raise ValueError(f"parsed document mismatch: {document_id}")
        if parsed.metadata.portal_document_guid != entry["portal_document_guid"]:
            raise ValueError(f"parsed portal GUID mismatch: {document_id}")
        if parsed.metadata.content_sha256 != raw_hash:
            raise ValueError(f"parsed raw hash mismatch: {document_id}")
        if parsed.metadata.snapshot_id != snapshot_id:
            raise ValueError(f"parsed snapshot mismatch: {document_id}")
        if parsed.normalizer_version != entry["normalizer_version"]:
            raise ValueError(f"parsed normalizer version mismatch: {document_id}")
        if parsed.parser_version != entry["parser_version"]:
            raise ValueError(f"parsed parser version mismatch: {document_id}")
        if parsed.artifact_version != entry["artifact_version"]:
            raise ValueError(f"parsed artifact version mismatch: {document_id}")
        validated.append((entry, parsed))
    return validated


def _parsed_documents(snapshot_id: str, data_root: Path) -> list[ParsedDocument]:
    return [parsed for _, parsed in _validated_snapshot(snapshot_id, data_root)]


def _approved_relations(
    relation_artifact: Path | None, documents: list[ParsedDocument]
) -> tuple[ApprovedRelation, ...]:
    if relation_artifact is None:
        return ()
    return resolve_approved_relations(load_approved_relation_artifact(relation_artifact), documents)


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


@app.command("fetch-portal")
def fetch_portal(
    document_id: Annotated[str, typer.Option(help="Exact reviewed legal identifier.")],
    catalog: Annotated[
        Path,
        typer.Option(
            exists=True,
            dir_okay=False,
            readable=True,
            help="Reviewed source catalog JSON.",
        ),
    ],
    data_root: Annotated[Path, typer.Option(help="Artifact root.")] = Path("data"),
) -> None:
    """Ingest one reviewed document; arbitrary URLs and search terms are not accepted."""

    source = _select_source(catalog, document_id)
    client = PortalClient()
    result = IngestionPipeline(client.fetch_raw, ArtifactStore(data_root)).ingest(source)
    typer.echo(
        json.dumps(
            {
                "document_id": source.expected_document_id,
                "raw_path": str(result.raw_path),
                "normalized_path": str(result.normalized_path),
                "parsed_path": str(result.parsed_path),
                "manifest_path": str(result.manifest_path),
                "unit_count": result.unit_count,
            },
            ensure_ascii=False,
        )
    )


@app.command("fetch-catalog")
def fetch_catalog(
    catalog: Annotated[
        Path,
        typer.Option(
            exists=True,
            dir_okay=False,
            readable=True,
            help="Reviewed source catalog JSON.",
        ),
    ],
    data_root: Annotated[Path, typer.Option(help="Artifact root.")] = Path("data"),
) -> None:
    """Ingest every reviewed source in one catalog into its draft snapshot."""

    sources = _load_sources(catalog)
    pipeline = IngestionPipeline(PortalClient().fetch_raw, ArtifactStore(data_root))
    succeeded: list[dict[str, str | int]] = []
    failed: list[dict[str, str]] = []
    for source in sources:
        try:
            result = pipeline.ingest(source)
        except (OSError, PortalError, ValueError) as exc:
            failed.append(
                {
                    "document_id": source.expected_document_id,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            continue
        succeeded.append(
            {
                "document_id": source.expected_document_id,
                "unit_count": result.unit_count,
            }
        )

    typer.echo(
        json.dumps(
            {
                "snapshot_id": sources[0].snapshot_id,
                "succeeded": succeeded,
                "failed": failed,
            },
            ensure_ascii=False,
        )
    )
    if failed:
        raise typer.Exit(code=1)


@app.command("rebuild-snapshot")
def rebuild_snapshot(
    snapshot_id: Annotated[str, typer.Option(help="Existing draft snapshot identifier.")],
    catalog: Annotated[
        Path,
        typer.Option(
            exists=True,
            dir_okay=False,
            readable=True,
            help="Reviewed source catalog JSON matching the snapshot.",
        ),
    ],
    data_root: Annotated[Path, typer.Option(help="Artifact root.")] = Path("data"),
) -> None:
    """Re-derive parsed artifacts from frozen raw bytes without network access."""

    try:
        sources = _load_sources(catalog)
        if any(source.snapshot_id != snapshot_id for source in sources):
            raise ValueError("catalog snapshot does not match requested snapshot")
        manifest_path = data_root / "manifests" / f"{snapshot_id}.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        documents = manifest["documents"]
        if manifest.get("snapshot_id") != snapshot_id or not isinstance(documents, list):
            raise ValueError("invalid manifest envelope")
        source_by_id = {source.expected_document_id: source for source in sources}
        raw_by_id: dict[str, bytes] = {}
        for document in documents:
            if not isinstance(document, dict):
                raise ValueError("invalid manifest document")
            document_id = document.get("document_id")
            document_guid = document.get("portal_document_guid")
            content_sha256 = document.get("content_sha256")
            if (
                not isinstance(document_id, str)
                or not isinstance(document_guid, str)
                or not isinstance(content_sha256, str)
            ):
                raise ValueError("invalid manifest document")
            source = source_by_id.get(document_id)
            if source is None or document_guid != source.document_guid:
                raise ValueError("catalog and manifest document identities differ")
            raw_bytes = (data_root / "raw" / f"{content_sha256}.json").read_bytes()
            if hashlib.sha256(raw_bytes).hexdigest() != content_sha256:
                raise ValueError(f"raw hash mismatch: {document_id}")
            raw_by_id[document_id] = raw_bytes
        if source_by_id.keys() != raw_by_id.keys():
            raise ValueError("catalog and manifest document IDs differ")
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(f"cannot rebuild snapshot: {snapshot_id}") from exc

    pipeline = IngestionPipeline(
        lambda source: raw_by_id[source.expected_document_id], ArtifactStore(data_root)
    )
    rebuilt: list[dict[str, str | int]] = []
    for source in sources:
        try:
            result = pipeline.ingest(source)
        except (OSError, PortalError, ValueError) as exc:
            raise typer.BadParameter(
                f"cannot rebuild {source.expected_document_id}: {exc}"
            ) from exc
        rebuilt.append(
            {"document_id": source.expected_document_id, "unit_count": result.unit_count}
        )
    typer.echo(json.dumps({"snapshot_id": snapshot_id, "rebuilt": rebuilt}, ensure_ascii=False))


@app.command("validate-snapshot")
def validate_snapshot(
    snapshot_id: Annotated[str, typer.Option(help="Draft snapshot identifier.")],
    data_root: Annotated[Path, typer.Option(help="Artifact root.")] = Path("data"),
) -> None:
    """Verify that a manifest points only to matching raw and parsed artifacts."""

    try:
        documents = _validated_snapshot(snapshot_id, data_root)
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError, ValidationError) as exc:
        raise typer.BadParameter(f"invalid snapshot: {snapshot_id}") from exc

    typer.echo(json.dumps({"snapshot_id": snapshot_id, "document_count": len(documents)}))


@app.command("import-graph")
def import_graph(
    snapshot_id: Annotated[str, typer.Option(help="Validated draft snapshot identifier.")],
    neo4j_password: Annotated[
        str,
        typer.Option(envvar="NEO4J_PASSWORD", help="Neo4j password; prefer NEO4J_PASSWORD."),
    ],
    data_root: Annotated[Path, typer.Option(help="Artifact root.")] = Path("data"),
    relation_artifact: Annotated[
        Path | None,
        typer.Option(help="Approved AMENDS artifact; omit to project structure only."),
    ] = None,
    neo4j_uri: Annotated[str, typer.Option(help="Bolt URI.")] = "bolt://localhost:7687",
    neo4j_username: Annotated[str, typer.Option(help="Neo4j username.")] = "neo4j",
    neo4j_database: Annotated[str, typer.Option(help="Neo4j database.")] = "neo4j",
) -> None:
    """Project one validated snapshot's hierarchy and portal metadata into Neo4j."""

    try:
        documents = _parsed_documents(snapshot_id, data_root)
        relations = _approved_relations(relation_artifact, documents)
        with GraphDatabase.driver(neo4j_uri, auth=(neo4j_username, neo4j_password)) as driver:
            driver.verify_connectivity()
            verification = GraphSnapshotImporter(driver, database=neo4j_database).import_snapshot(
                snapshot_id, documents, relations
            )
    except (
        DriverError,
        GraphImportError,
        Neo4jError,
        OSError,
        ValueError,
        json.JSONDecodeError,
        ValidationError,
    ) as exc:
        raise typer.BadParameter(f"cannot import graph: {snapshot_id}") from exc
    typer.echo(json.dumps(verification.model_dump(), ensure_ascii=False))


@app.command("verify-graph")
def verify_graph(
    snapshot_id: Annotated[str, typer.Option(help="Validated draft snapshot identifier.")],
    neo4j_password: Annotated[
        str,
        typer.Option(envvar="NEO4J_PASSWORD", help="Neo4j password; prefer NEO4J_PASSWORD."),
    ],
    data_root: Annotated[Path, typer.Option(help="Artifact root.")] = Path("data"),
    relation_artifact: Annotated[
        Path | None,
        typer.Option(help="Approved AMENDS artifact expected in the graph."),
    ] = None,
    neo4j_uri: Annotated[str, typer.Option(help="Bolt URI.")] = "bolt://localhost:7687",
    neo4j_username: Annotated[str, typer.Option(help="Neo4j username.")] = "neo4j",
    neo4j_database: Annotated[str, typer.Option(help="Neo4j database.")] = "neo4j",
) -> None:
    """Reconcile Neo4j's structural graph with the validated snapshot artifacts."""

    try:
        documents = _parsed_documents(snapshot_id, data_root)
        relations = _approved_relations(relation_artifact, documents)
        with GraphDatabase.driver(neo4j_uri, auth=(neo4j_username, neo4j_password)) as driver:
            driver.verify_connectivity()
            verification = GraphSnapshotImporter(driver, database=neo4j_database).verify_snapshot(
                snapshot_id, expected_counts(documents, relations)
            )
    except (
        DriverError,
        GraphImportError,
        Neo4jError,
        OSError,
        ValueError,
        json.JSONDecodeError,
        ValidationError,
    ) as exc:
        raise typer.BadParameter(f"cannot verify graph: {snapshot_id}") from exc
    typer.echo(json.dumps(verification.model_dump(), ensure_ascii=False))
    if not verification.is_valid:
        raise typer.Exit(code=1)


@app.command("validate-relations")
def validate_relations(
    snapshot_id: Annotated[str, typer.Option(help="Validated draft snapshot identifier.")],
    relation_artifact: Annotated[
        Path,
        typer.Option(
            exists=True,
            dir_okay=False,
            readable=True,
            help="Approved AMENDS artifact JSON.",
        ),
    ],
    data_root: Annotated[Path, typer.Option(help="Artifact root.")] = Path("data"),
) -> None:
    """Resolve every approved AMENDS record against its frozen parsed snapshot."""

    try:
        documents = _parsed_documents(snapshot_id, data_root)
        relations = _approved_relations(relation_artifact, documents)
    except (
        KeyError,
        TypeError,
        ValueError,
        OSError,
        json.JSONDecodeError,
        ValidationError,
    ) as exc:
        raise typer.BadParameter(f"invalid relation artifact: {relation_artifact}") from exc
    typer.echo(
        json.dumps(
            {
                "snapshot_id": snapshot_id,
                "relation_count": len(relations),
                "relation_ids": [relation.relation_id for relation in relations],
            },
            ensure_ascii=False,
        )
    )


@app.command("validate-gold-set")
def validate_gold_set(
    snapshot_id: Annotated[str, typer.Option(help="Validated draft snapshot identifier.")],
    gold_set: Annotated[
        Path,
        typer.Option(
            exists=True,
            dir_okay=False,
            readable=True,
            help="Citation-backed retrieval gold-set JSON.",
        ),
    ],
    data_root: Annotated[Path, typer.Option(help="Artifact root.")] = Path("data"),
) -> None:
    """Resolve every retrieval citation against one frozen parsed snapshot."""

    try:
        documents = _parsed_documents(snapshot_id, data_root)
        artifact = load_gold_question_artifact(gold_set)
        questions = resolve_gold_questions(artifact, documents)
    except (
        KeyError,
        TypeError,
        ValueError,
        OSError,
        json.JSONDecodeError,
        ValidationError,
    ) as exc:
        raise typer.BadParameter(f"invalid gold question artifact: {gold_set}") from exc
    typer.echo(
        json.dumps(
            {
                "snapshot_id": snapshot_id,
                "question_count": len(questions),
                "gold_unit_count": len(
                    {unit_id for question in questions for unit_id in question.gold_unit_ids}
                ),
                "split_counts": dict(
                    sorted(Counter(question.split for question in questions).items())
                ),
                "question_type_counts": dict(
                    sorted(Counter(question.question_type for question in questions).items())
                ),
                "review_status_counts": dict(
                    sorted(Counter(question.review_status for question in questions).items())
                ),
            },
            ensure_ascii=False,
        )
    )


@app.command("build-lexical-index")
def build_lexical_index(
    snapshot_id: Annotated[str, typer.Option(help="Validated draft snapshot identifier.")],
    neo4j_password: Annotated[
        str,
        typer.Option(envvar="NEO4J_PASSWORD", help="Neo4j password; prefer NEO4J_PASSWORD."),
    ],
    data_root: Annotated[Path, typer.Option(help="Artifact root.")] = Path("data"),
    neo4j_uri: Annotated[str, typer.Option(help="Bolt URI.")] = "bolt://localhost:7687",
    neo4j_username: Annotated[str, typer.Option(help="Neo4j username.")] = "neo4j",
    neo4j_database: Annotated[str, typer.Option(help="Neo4j database.")] = "neo4j",
) -> None:
    """Build the snapshot-safe Neo4j full-text index outside the query path."""

    try:
        documents = _parsed_documents(snapshot_id, data_root)
        with GraphDatabase.driver(neo4j_uri, auth=(neo4j_username, neo4j_password)) as driver:
            driver.verify_connectivity()
            status = Neo4jLexicalRetriever(driver, database=neo4j_database).build_index(
                snapshot_id, documents
            )
    except (
        DriverError,
        LexicalIndexError,
        Neo4jError,
        OSError,
        ValueError,
        json.JSONDecodeError,
        ValidationError,
    ) as exc:
        raise typer.BadParameter(f"cannot build lexical index: {snapshot_id}") from exc
    typer.echo(json.dumps(status.model_dump(), ensure_ascii=False))


@app.command("search-lexical")
def search_lexical(
    snapshot_id: Annotated[str, typer.Option(help="Validated draft snapshot identifier.")],
    query: Annotated[str, typer.Option(help="Vietnamese legal retrieval query.")],
    neo4j_password: Annotated[
        str,
        typer.Option(envvar="NEO4J_PASSWORD", help="Neo4j password; prefer NEO4J_PASSWORD."),
    ],
    top_k: Annotated[int, typer.Option(help="Maximum candidates, from 1 through 50.")] = 10,
    data_root: Annotated[Path, typer.Option(help="Artifact root.")] = Path("data"),
    neo4j_uri: Annotated[str, typer.Option(help="Bolt URI.")] = "bolt://localhost:7687",
    neo4j_username: Annotated[str, typer.Option(help="Neo4j username.")] = "neo4j",
    neo4j_database: Annotated[str, typer.Option(help="Neo4j database.")] = "neo4j",
) -> None:
    """Retrieve exact locators and Neo4j full-text candidates from one snapshot."""

    try:
        documents = _parsed_documents(snapshot_id, data_root)
        with GraphDatabase.driver(neo4j_uri, auth=(neo4j_username, neo4j_password)) as driver:
            driver.verify_connectivity()
            retriever = Neo4jLexicalRetriever(driver, database=neo4j_database)
            retriever.verify_index(snapshot_id, documents)
            candidates = retriever.search(snapshot_id, documents, query, top_k=top_k)
    except (
        DriverError,
        LexicalIndexError,
        Neo4jError,
        OSError,
        ValueError,
        json.JSONDecodeError,
        ValidationError,
    ) as exc:
        raise typer.BadParameter(f"cannot search lexical index: {snapshot_id}") from exc
    typer.echo(
        json.dumps(
            {
                "snapshot_id": snapshot_id,
                "retrieval_config": "r0-lexical",
                "query": query,
                "candidate_count": len(candidates),
                "candidates": [candidate.model_dump() for candidate in candidates],
            },
            ensure_ascii=False,
        )
    )


@app.command("evaluate-r0")
def evaluate_r0(
    snapshot_id: Annotated[str, typer.Option(help="Validated draft snapshot identifier.")],
    gold_set: Annotated[
        Path,
        typer.Option(
            exists=True,
            dir_okay=False,
            readable=True,
            help="Citation-backed retrieval gold-set JSON.",
        ),
    ],
    neo4j_password: Annotated[
        str,
        typer.Option(envvar="NEO4J_PASSWORD", help="Neo4j password; prefer NEO4J_PASSWORD."),
    ],
    split: Annotated[str, typer.Option(help="Frozen gold split: dev or test.")] = "dev",
    report_path: Annotated[
        Path | None,
        typer.Option(help="Generated report path; defaults under data/evaluations/."),
    ] = None,
    data_root: Annotated[Path, typer.Option(help="Artifact root.")] = Path("data"),
    neo4j_uri: Annotated[str, typer.Option(help="Bolt URI.")] = "bolt://localhost:7687",
    neo4j_username: Annotated[str, typer.Option(help="Neo4j username.")] = "neo4j",
    neo4j_database: Annotated[str, typer.Option(help="Neo4j database.")] = "neo4j",
) -> None:
    """Evaluate the fixed R0 exact-plus-lexical baseline without test-set tuning."""

    try:
        documents = _parsed_documents(snapshot_id, data_root)
        questions = resolve_gold_questions(load_gold_question_artifact(gold_set), documents)
        with GraphDatabase.driver(neo4j_uri, auth=(neo4j_username, neo4j_password)) as driver:
            driver.verify_connectivity()
            run = run_r0_lexical(
                Neo4jLexicalRetriever(driver, database=neo4j_database),
                snapshot_id,
                documents,
                questions,
                split,
                hashlib.sha256(gold_set.read_bytes()).hexdigest(),
                _git_commit(),
            )
        destination = report_path or (
            data_root / "evaluations" / f"{snapshot_id}.r0-lexical-{split}.json"
        )
        write_evaluation_run(destination, run)
    except (
        DriverError,
        LexicalIndexError,
        Neo4jError,
        OSError,
        ValueError,
        json.JSONDecodeError,
        ValidationError,
    ) as exc:
        raise typer.BadParameter(f"cannot evaluate R0: {snapshot_id}") from exc
    typer.echo(
        json.dumps(
            {
                "run_id": run.run_id,
                "snapshot_id": snapshot_id,
                "split": split,
                "report_path": str(destination),
                "metrics": run.evaluation.metrics.model_dump(),
            },
            ensure_ascii=False,
        )
    )


@app.command("report-snapshot")
def report_snapshot(
    snapshot_id: Annotated[str, typer.Option(help="Draft snapshot identifier.")],
    catalog: Annotated[
        Path,
        typer.Option(
            exists=True,
            dir_okay=False,
            readable=True,
            help="Reviewed source catalog JSON.",
        ),
    ],
    data_root: Annotated[Path, typer.Option(help="Artifact root.")] = Path("data"),
) -> None:
    """Write deterministic counts only after catalog and snapshot integrity checks pass."""

    try:
        sources = _load_sources(catalog)
        if any(source.snapshot_id != snapshot_id for source in sources):
            raise ValueError("catalog snapshot does not match requested snapshot")
        documents = _validated_snapshot(snapshot_id, data_root)
        sources_by_id = {source.expected_document_id: source for source in sources}
        documents_by_id = {entry["document_id"]: (entry, parsed) for entry, parsed in documents}
        if sources_by_id.keys() != documents_by_id.keys():
            raise ValueError("catalog and manifest document IDs differ")

        report_documents: list[dict[str, object]] = []
        total_unit_counts: Counter[str] = Counter()
        metadata_document_counts: Counter[str] = Counter()
        total_units = 0
        unknown_status_document_count = 0
        for document_id in sorted(documents_by_id):
            entry, parsed = documents_by_id[document_id]
            unit_counts = Counter(unit.unit_type for unit in parsed.units)
            total_unit_counts.update(unit_counts)
            total_units += len(parsed.units)
            unknown_status_document_count += parsed.metadata.status == "unknown"
            metadata_document_counts.update(
                {
                    "portal_document_type": parsed.metadata.portal_document_type is not None,
                    "source_effect_status": parsed.metadata.source_effect_status is not None,
                    "fields": bool(parsed.metadata.fields),
                    "majors": bool(parsed.metadata.majors),
                    "issuing_organs": bool(parsed.metadata.issuing_organs),
                    "signers": bool(parsed.metadata.signers),
                }
            )
            report_documents.append(
                {
                    "document_id": document_id,
                    "portal_document_guid": entry["portal_document_guid"],
                    "status": parsed.metadata.status,
                    "source_effect_status": parsed.metadata.source_effect_status,
                    "effective_from": (
                        parsed.metadata.effective_from.isoformat()
                        if parsed.metadata.effective_from is not None
                        else None
                    ),
                    "content_sha256": entry["content_sha256"],
                    "normalizer_version": entry["normalizer_version"],
                    "parser_version": entry["parser_version"],
                    "artifact_version": entry["artifact_version"],
                    "reviewed_correction_count": len(
                        sources_by_id[document_id].reviewed_text_replacements
                    ),
                    "unit_count": len(parsed.units),
                    "unit_counts": dict(sorted(unit_counts.items())),
                }
            )
        report = {
            "snapshot_id": snapshot_id,
            "catalog_sha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
            "catalog_document_count": len(sources),
            "manifest_document_count": len(documents),
            "manifest_sha256": hashlib.sha256(
                (data_root / "manifests" / f"{snapshot_id}.json").read_bytes()
            ).hexdigest(),
            "documents": report_documents,
            "totals": {
                "unit_count": total_units,
                "unit_counts": dict(sorted(total_unit_counts.items())),
                "unknown_status_document_count": unknown_status_document_count,
                "metadata_document_counts": dict(sorted(metadata_document_counts.items())),
            },
        }
        report_path = ArtifactStore(data_root).write_report(snapshot_id, report)
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError, ValidationError) as exc:
        raise typer.BadParameter(f"cannot report snapshot: {snapshot_id}") from exc

    typer.echo(
        json.dumps(
            {
                "snapshot_id": snapshot_id,
                "document_count": len(documents),
                "report_path": str(report_path),
            }
        )
    )
