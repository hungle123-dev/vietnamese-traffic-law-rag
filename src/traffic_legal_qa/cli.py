"""Curator commands for the first ingestion slice."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from traffic_legal_qa.ingestion.models import ParsedDocument, ReviewedSource
from traffic_legal_qa.ingestion.pipeline import IngestionPipeline
from traffic_legal_qa.ingestion.portal import PortalClient
from traffic_legal_qa.ingestion.storage import ArtifactStore

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _load_sources(catalog_path: Path) -> list[ReviewedSource]:
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        snapshot_id = catalog["snapshot_id"]
        sources = catalog["sources"]
        if not isinstance(snapshot_id, str) or not isinstance(sources, list):
            raise ValueError("catalog must have snapshot_id and sources")
        return [
            ReviewedSource.model_validate({**source, "snapshot_id": snapshot_id})
            for source in sources
        ]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as exc:
        raise typer.BadParameter(f"invalid reviewed catalog: {catalog_path}") from exc


def _select_source(catalog_path: Path, document_id: str) -> ReviewedSource:
    for source in _load_sources(catalog_path):
        if source.expected_document_id == document_id:
            return source
    raise typer.BadParameter(f"document ID is not in the reviewed catalog: {document_id}")


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


@app.command("validate-snapshot")
def validate_snapshot(
    snapshot_id: Annotated[str, typer.Option(help="Draft snapshot identifier.")],
    data_root: Annotated[Path, typer.Option(help="Artifact root.")] = Path("data"),
) -> None:
    """Verify that a manifest points only to matching raw and parsed artifacts."""

    manifest_path = data_root / "manifests" / f"{snapshot_id}.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        documents = manifest["documents"]
        if manifest["snapshot_id"] != snapshot_id or not isinstance(documents, list):
            raise ValueError("invalid manifest envelope")
        for document in documents:
            document_id = document["document_id"]
            raw_hash = document["content_sha256"]
            parsed_path = (data_root / document["parsed_path"]).resolve()
            if not parsed_path.is_relative_to(data_root.resolve()):
                raise ValueError("manifest path escapes data root")
            raw_path = data_root / "raw" / f"{raw_hash}.json"
            if hashlib.sha256(raw_path.read_bytes()).hexdigest() != raw_hash:
                raise ValueError(f"raw hash mismatch: {document_id}")
            parsed = ParsedDocument.model_validate_json(parsed_path.read_text(encoding="utf-8"))
            if parsed.metadata.document_id != document_id:
                raise ValueError(f"parsed document mismatch: {document_id}")
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError, ValidationError) as exc:
        raise typer.BadParameter(f"invalid snapshot: {snapshot_id}") from exc

    typer.echo(json.dumps({"snapshot_id": snapshot_id, "document_count": len(documents)}))
