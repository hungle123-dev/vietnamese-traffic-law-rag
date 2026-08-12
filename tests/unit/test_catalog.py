import json
from datetime import UTC, datetime
from pathlib import Path

from traffic_legal_qa.ingestion.models import LegalDocumentMetadata

CATALOG_PATH = Path(__file__).parents[2] / "data" / "catalog" / "traffic-2026-08-12-v1.json"


def test_seed_catalog_has_unique_valid_document_records() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    documents = catalog["documents"]

    assert catalog["snapshot_id"] == "traffic-2026-08-12-v1"
    assert len(documents) == 13
    assert len({document["document_id"] for document in documents}) == len(documents)
    for document in documents:
        metadata = LegalDocumentMetadata.model_validate(
            {
                **document,
                "retrieved_at": datetime(2026, 8, 12, tzinfo=UTC),
                "snapshot_id": catalog["snapshot_id"],
            }
        )
        assert metadata.content_url is not None
