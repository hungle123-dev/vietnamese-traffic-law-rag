from dataclasses import dataclass
from pathlib import Path

from traffic_legal_qa.ingestion.models import LegalDocumentMetadata, ParsedDocument
from traffic_legal_qa.ingestion.parser import LegalHierarchyParser
from traffic_legal_qa.ingestion.sources import extract_pdf_text
from traffic_legal_qa.ingestion.storage import ManifestStore, ParsedDocumentStore, RawDocumentStore


@dataclass(frozen=True)
class IngestionResult:
    document_id: str
    snapshot_id: str
    raw_path: str
    parsed_path: str
    unit_count: int


class IngestionPipeline:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.raw_store = RawDocumentStore(data_dir / "raw")
        self.parsed_store = ParsedDocumentStore(data_dir / "parsed")
        self.manifest_store = ManifestStore(data_dir / "manifests" / "manifest.json")

    def ingest_file(
        self,
        source_path: Path,
        metadata: LegalDocumentMetadata,
    ) -> IngestionResult:
        raw_content = source_path.read_bytes()
        raw_path, content_hash = self.raw_store.store_bytes(
            raw_content,
            source_path.suffix or ".txt",
        )
        return self._ingest_stored_content(
            raw_path, content_hash, raw_content.decode("utf-8"), metadata
        )

    def ingest_content(
        self,
        raw_content: bytes,
        content: str,
        metadata: LegalDocumentMetadata,
        *,
        raw_suffix: str,
    ) -> IngestionResult:
        raw_path, content_hash = self.raw_store.store_bytes(raw_content, raw_suffix)
        return self._ingest_stored_content(raw_path, content_hash, content, metadata)

    def ingest_pdf(self, raw_content: bytes, metadata: LegalDocumentMetadata) -> IngestionResult:
        raw_path, content_hash = self.raw_store.store_bytes(raw_content, ".pdf")
        extracted = extract_pdf_text(raw_content)
        return self._ingest_stored_content(raw_path, content_hash, extracted.text, metadata)

    def _ingest_stored_content(
        self,
        raw_path: str,
        content_hash: str,
        content: str,
        metadata: LegalDocumentMetadata,
    ) -> IngestionResult:
        finalized_metadata = metadata.model_copy(update={"content_sha256": content_hash})
        units = LegalHierarchyParser(finalized_metadata.document_id).parse(content)
        document = ParsedDocument(metadata=finalized_metadata, units=units)
        parsed_path = self.parsed_store.store(document)
        self.manifest_store.upsert(finalized_metadata)
        return IngestionResult(
            document_id=finalized_metadata.document_id,
            snapshot_id=finalized_metadata.snapshot_id,
            raw_path=raw_path,
            parsed_path=parsed_path,
            unit_count=len(units),
        )
