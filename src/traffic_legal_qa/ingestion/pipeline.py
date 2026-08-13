"""The ordered, fail-closed ingestion path for one reviewed source."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from traffic_legal_qa.ingestion.models import ReviewedSource
from traffic_legal_qa.ingestion.normalize import apply_reviewed_replacements, normalize_html
from traffic_legal_qa.ingestion.parser import LegalHierarchyParser
from traffic_legal_qa.ingestion.portal import PortalError, parse_detail_response
from traffic_legal_qa.ingestion.storage import ArtifactStore


class PortalTitleMismatch(PortalError):
    """A raw response is retained but cannot be promoted under a mismatched catalog title."""


@dataclass(frozen=True)
class IngestionResult:
    raw_path: Path
    normalized_path: Path
    parsed_path: Path
    manifest_path: Path
    unit_count: int


class IngestionPipeline:
    """Stores raw bytes before any validation and promotes only validated hierarchy."""

    def __init__(self, fetch_raw: Callable[[ReviewedSource], bytes], store: ArtifactStore) -> None:
        self._fetch_raw = fetch_raw
        self._store = store
        self._parser = LegalHierarchyParser()

    def ingest(self, source: ReviewedSource) -> IngestionResult:
        raw_bytes = self._fetch_raw(source)
        raw_path = self._store.store_raw(raw_bytes)
        detail = parse_detail_response(raw_bytes, source)
        if not detail.title_matches_expected:
            raise PortalTitleMismatch("portal title differs from reviewed catalog entry")
        normalized_text = apply_reviewed_replacements(
            normalize_html(detail.html), source.reviewed_text_replacements
        )
        parsed = self._parser.parse(normalized_text, detail.metadata)
        normalized_path = self._store.store_normalized(
            detail.metadata.content_sha256,
            normalized_text,
        )
        parsed_path = self._store.write_parsed(parsed)
        manifest_path = self._store.update_manifest(parsed, parsed_path)
        return IngestionResult(
            raw_path=raw_path,
            normalized_path=normalized_path,
            parsed_path=parsed_path,
            manifest_path=manifest_path,
            unit_count=len(parsed.units),
        )
