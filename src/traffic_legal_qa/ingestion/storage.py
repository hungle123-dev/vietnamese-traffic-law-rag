import hashlib
import json
import re
from pathlib import Path

from traffic_legal_qa.ingestion.models import LegalDocumentMetadata, ParsedDocument


class RawDocumentStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def store_text(self, content: str) -> tuple[str, str]:
        return self.store_bytes(content.encode("utf-8"))

    def store_bytes(self, content: bytes) -> tuple[str, str]:
        content_hash = hashlib.sha256(content).hexdigest()
        destination = self.root / f"{content_hash}.txt"
        if destination.exists():
            if destination.read_bytes() != content:
                raise ValueError(f"Raw content hash collision: {destination}")
        else:
            destination.write_bytes(content)
        return str(destination), content_hash


class ParsedDocumentStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def store(self, document: ParsedDocument) -> str:
        filename = self._safe_name(
            f"{document.metadata.document_id}__{document.metadata.snapshot_id}"
        )
        destination = self.root / f"{filename}.json"
        self._write_json(destination, document.model_dump(mode="json"))
        return str(destination)

    @staticmethod
    def _safe_name(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")

    @staticmethod
    def _write_json(destination: Path, payload: object) -> None:
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)


class ManifestStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def upsert(self, metadata: LegalDocumentMetadata) -> None:
        records = self._read()
        key = (metadata.document_id, metadata.snapshot_id)
        records = [
            record for record in records if (record["document_id"], record["snapshot_id"]) != key
        ]
        records.append(metadata.model_dump(mode="json"))
        records.sort(key=lambda record: (record["snapshot_id"], record["document_id"]))
        ParsedDocumentStore._write_json(self.path, {"documents": records})

    def _read(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        documents = payload.get("documents")
        if not isinstance(documents, list):
            raise ValueError(f"Invalid manifest format: {self.path}")
        return documents
