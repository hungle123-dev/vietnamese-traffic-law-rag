from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated

import typer

from traffic_legal_qa.config import settings
from traffic_legal_qa.ingestion.models import LegalDocumentMetadata
from traffic_legal_qa.ingestion.pipeline import IngestionPipeline
from traffic_legal_qa.ingestion.sources import download_pdf

app = typer.Typer(no_args_is_help=True)


def _parse_iso_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise typer.BadParameter("must use YYYY-MM-DD") from error


@app.callback()
def _main() -> None:
    """Vietnamese traffic-law ingestion CLI."""


@app.command()
def ingest(
    source: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, readable=True),
    ],
    document_id: Annotated[str, typer.Option()],
    title: Annotated[str, typer.Option()],
    source_url: Annotated[str, typer.Option()],
    snapshot_id: Annotated[str, typer.Option()],
    document_type: Annotated[str, typer.Option()] = "law",
    issuer: Annotated[str, typer.Option()] = "Unknown issuer",
    issued_date: Annotated[str | None, typer.Option()] = None,
    effective_from: Annotated[str | None, typer.Option()] = None,
    status: Annotated[str, typer.Option()] = "unknown",
) -> None:
    """Ingest one UTF-8 traffic-law text document."""
    metadata = LegalDocumentMetadata(
        document_id=document_id,
        title=title,
        document_type=document_type,
        issuer=issuer,
        issued_date=_parse_iso_date(issued_date),
        effective_from=_parse_iso_date(effective_from),
        status=status,
        source_url=source_url,
        retrieved_at=datetime.now(UTC),
        snapshot_id=snapshot_id,
    )
    result = IngestionPipeline(settings.data_dir).ingest_file(source, metadata)
    typer.echo(f"Ingested {result.document_id}: {result.unit_count} units")
    typer.echo(f"Raw: {result.raw_path}")
    typer.echo(f"Parsed: {result.parsed_path}")


@app.command("fetch-pdf")
def fetch_pdf(
    content_url: Annotated[str, typer.Option()],
    document_id: Annotated[str, typer.Option()],
    title: Annotated[str, typer.Option()],
    source_url: Annotated[str, typer.Option()],
    snapshot_id: Annotated[str, typer.Option()],
    document_type: Annotated[str, typer.Option()] = "law",
    issuer: Annotated[str, typer.Option()] = "Unknown issuer",
    issued_date: Annotated[str | None, typer.Option()] = None,
    effective_from: Annotated[str | None, typer.Option()] = None,
    status: Annotated[str, typer.Option()] = "unknown",
) -> None:
    """Fetch one official PDF, extract its text, and ingest it."""
    raw_content = download_pdf(content_url)
    metadata = LegalDocumentMetadata(
        document_id=document_id,
        title=title,
        document_type=document_type,
        issuer=issuer,
        issued_date=_parse_iso_date(issued_date),
        effective_from=_parse_iso_date(effective_from),
        status=status,
        source_url=source_url,
        content_url=content_url,
        retrieved_at=datetime.now(UTC),
        snapshot_id=snapshot_id,
    )
    result = IngestionPipeline(settings.data_dir).ingest_pdf(raw_content, metadata)
    typer.echo(f"Ingested {result.document_id}: {result.unit_count} units")
    typer.echo(f"Raw: {result.raw_path}")
    typer.echo(f"Parsed: {result.parsed_path}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
