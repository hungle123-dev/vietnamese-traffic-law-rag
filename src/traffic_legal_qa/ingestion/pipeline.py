from dataclasses import dataclass
from pathlib import Path

from traffic_legal_qa.ingestion.models import LegalDocumentMetadata, ParsedDocument
from traffic_legal_qa.ingestion.parser import LegalHierarchyParser
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
        raw_path, content_hash = self.raw_store.store_bytes(raw_content)
        content = raw_content.decode("utf-8")
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
