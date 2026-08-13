"""Curator commands for the first ingestion slice."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from traffic_legal_qa.ingestion.models import ParsedDocument, ReviewedSource
from traffic_legal_qa.ingestion.pipeline import IngestionPipeline
from traffic_legal_qa.ingestion.portal import PortalClient, PortalError
from traffic_legal_qa.ingestion.storage import ArtifactStore

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
        validated.append((entry, parsed))
    return validated


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
        total_units = 0
        unknown_status_document_count = 0
        for document_id in sorted(documents_by_id):
            entry, parsed = documents_by_id[document_id]
            unit_counts = Counter(unit.unit_type for unit in parsed.units)
            total_unit_counts.update(unit_counts)
            total_units += len(parsed.units)
            unknown_status_document_count += parsed.metadata.status == "unknown"
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
