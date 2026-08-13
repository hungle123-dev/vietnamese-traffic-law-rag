"""Content-addressed raw artifacts and deterministic draft-snapshot files."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TypedDict
from urllib.parse import quote

from traffic_legal_qa.ingestion.models import ParsedDocument


class _ManifestDocument(TypedDict):
    document_id: str
    portal_document_guid: str
    content_sha256: str
    parsed_path: str
    normalizer_version: str
    parser_version: str
    artifact_version: str


class _Manifest(TypedDict):
    snapshot_id: str
    documents: list[_ManifestDocument]


@dataclass(frozen=True)
class RawArtifact:
    path: Path
    retrieved_at: datetime


class ArtifactStore:
    """Keeps raw, derived, and manifest artifacts separate under one data root."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def store_raw(self, raw_bytes: bytes, retrieved_at: datetime) -> RawArtifact:
        if retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at must include a timezone")
        digest = hashlib.sha256(raw_bytes).hexdigest()
        path = self._root / "raw" / f"{digest}.json"
        self._write_once(path, raw_bytes)
        receipt_path = self._root / "receipts" / f"{digest}.json"
        if not receipt_path.exists():
            self._write_json(
                receipt_path,
                {"content_sha256": digest, "retrieved_at": retrieved_at.isoformat()},
            )
        receipt = self._read_receipt(receipt_path, digest)
        return RawArtifact(path=path, retrieved_at=receipt)

    def store_normalized(self, content_sha256: str, text: str) -> Path:
        path = self._root / "normalized" / f"{content_sha256}.txt"
        self._write_once(path, f"{text}\n".encode())
        return path

    def write_parsed(self, parsed: ParsedDocument) -> Path:
        filename = (
            f"{_file_component(parsed.metadata.document_id)}__{parsed.metadata.snapshot_id}.json"
        )
        path = self._root / "parsed" / filename
        payload = parsed.model_dump(mode="json")
        self._write_json(path, payload)
        return path

    def update_manifest(self, parsed: ParsedDocument, parsed_path: Path) -> Path:
        path = self._root / "manifests" / f"{parsed.metadata.snapshot_id}.json"
        existing = self._read_manifest(path, parsed.metadata.snapshot_id)
        documents = [
            document
            for document in existing["documents"]
            if document["document_id"] != parsed.metadata.document_id
        ]
        documents.append(
            {
                "document_id": parsed.metadata.document_id,
                "portal_document_guid": parsed.metadata.portal_document_guid,
                "content_sha256": parsed.metadata.content_sha256,
                "parsed_path": parsed_path.relative_to(self._root).as_posix(),
                "normalizer_version": parsed.normalizer_version,
                "parser_version": parsed.parser_version,
                "artifact_version": parsed.artifact_version,
            }
        )
        manifest: _Manifest = {
            "snapshot_id": parsed.metadata.snapshot_id,
            "documents": sorted(documents, key=lambda item: item["document_id"]),
        }
        self._write_json(path, manifest)
        return path

    def write_report(self, snapshot_id: str, payload: object) -> Path:
        path = self._root / "reports" / f"{snapshot_id}.json"
        self._write_json(path, payload)
        return path

    @staticmethod
    def _write_once(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != content:
                raise ValueError(f"artifact hash collision at {path}")
            return
        path.write_bytes(content)

    @staticmethod
    def _read_manifest(path: Path, snapshot_id: str) -> _Manifest:
        if not path.exists():
            return {"snapshot_id": snapshot_id, "documents": []}
        loaded: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"manifest is not an object: {path}")
        loaded_snapshot_id = loaded.get("snapshot_id")
        loaded_documents = loaded.get("documents")
        if loaded_snapshot_id != snapshot_id or not isinstance(loaded_documents, list):
            raise ValueError(f"manifest has an invalid snapshot shape: {path}")

        documents: list[_ManifestDocument] = []
        fields = (
            "document_id",
            "portal_document_guid",
            "content_sha256",
            "parsed_path",
            "normalizer_version",
            "parser_version",
        )
        for item in loaded_documents:
            valid_entry = isinstance(item, dict) and all(
                isinstance(item.get(key), str) for key in fields
            )
            if not valid_entry:
                raise ValueError(f"manifest contains an invalid document entry: {path}")
            documents.append(
                {
                    "document_id": str(item["document_id"]),
                    "portal_document_guid": str(item["portal_document_guid"]),
                    "content_sha256": str(item["content_sha256"]),
                    "parsed_path": str(item["parsed_path"]),
                    "normalizer_version": str(item["normalizer_version"]),
                    "parser_version": str(item["parser_version"]),
                    "artifact_version": str(item.get("artifact_version", "1")),
                }
            )
        return {"snapshot_id": snapshot_id, "documents": documents}

    @staticmethod
    def _read_receipt(path: Path, content_sha256: str) -> datetime:
        loaded: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict) or loaded.get("content_sha256") != content_sha256:
            raise ValueError(f"raw receipt is invalid: {path}")
        received_at = loaded.get("retrieved_at")
        if not isinstance(received_at, str):
            raise ValueError(f"raw receipt is missing retrieved_at: {path}")
        parsed = datetime.fromisoformat(received_at)
        if parsed.tzinfo is None:
            raise ValueError(f"raw receipt has a naive timestamp: {path}")
        return parsed

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _file_component(value: str) -> str:
    """Encode legal identifiers without treating their slash as a directory separator."""

    return quote(value, safe="")
