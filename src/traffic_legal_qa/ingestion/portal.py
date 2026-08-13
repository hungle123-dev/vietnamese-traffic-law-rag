"""One bounded client for the current Cổng Pháp luật detail endpoint."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Final
from urllib import error, request

from pydantic import ValidationError

from traffic_legal_qa.ingestion.models import (
    CanonicalMetadata,
    CorpusStatus,
    PortalDetail,
    PortalDetailEnvelope,
    PortalNamedEntity,
    ReviewedSource,
)

DETAIL_ENDPOINT: Final = "https://phapluat.gov.vn/api/legal-documents/detail"
DEFAULT_TIMEOUT_SECONDS: Final = 20.0
DEFAULT_MAX_RESPONSE_BYTES: Final = 2_000_000


class PortalError(RuntimeError):
    """Base error for a portal response that cannot proceed through ingestion."""


class PortalFetchError(PortalError):
    """The portal could not provide a bounded successful detail response."""


class PortalSchemaError(PortalError):
    """The portal response does not satisfy the versioned detail contract."""


class PortalIdentityMismatch(PortalError):
    """A stored GUID did not resolve to the catalog's expected legal identifier."""


def detail_url(document_guid: str) -> str:
    """Build the only detail URL the ingestion path is allowed to fetch."""

    return f"{DETAIL_ENDPOINT}?docGUId={document_guid}&tabName=noidung"


def _map_status(effect_status: str | None) -> CorpusStatus:
    if effect_status == "Còn hiệu lực":
        return "current"
    if effect_status == "Hết hiệu lực":
        return "repealed"
    if effect_status == "Hết hiệu lực một phần":
        return "amended"
    return "unknown"


def _document_type(document_id: str) -> str:
    if "/QH" in document_id:
        return "law"
    if "/NĐ-CP" in document_id:
        return "decree"
    if "/TT-" in document_id:
        return "circular"
    if "/QĐ-" in document_id:
        return "decision"
    return "other"


def _names(*groups: Iterable[PortalNamedEntity]) -> tuple[str, ...]:
    """Keep portal lists deterministic while preserving their displayed names."""

    names: list[str] = []
    for group in groups:
        for item in group:
            if item.name not in names:
                names.append(item.name)
    return tuple(names)


def parse_detail_response(
    raw_bytes: bytes,
    source: ReviewedSource,
    *,
    retrieved_at: datetime | None = None,
) -> PortalDetail:
    """Validate portal JSON and map it to the project's canonical source metadata."""

    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
        envelope = PortalDetailEnvelope.model_validate(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        raise PortalSchemaError("PORTAL_SCHEMA_CHANGED") from exc

    document = envelope.data
    if document.document_guid != source.document_guid:
        raise PortalIdentityMismatch("portal GUID differs from reviewed catalog entry")
    if document.document_id != source.expected_document_id:
        raise PortalIdentityMismatch("portal document identity differs from reviewed catalog entry")

    source_effect_status = document.effect_status.name if document.effect_status else None
    issuing_organs = _names(document.issuing_organs)
    metadata = CanonicalMetadata(
        document_id=document.document_id,
        portal_document_guid=document.document_guid,
        title=document.title,
        document_type=_document_type(document.document_id),
        portal_document_type=(
            document.document_type_metadata.name if document.document_type_metadata else None
        ),
        issuer=issuing_organs[0] if issuing_organs else None,
        fields=_names(document.fields),
        majors=_names(document.majors),
        issuing_organs=issuing_organs,
        signers=document.signers,
        issued_date=document.issued_date,
        effective_from=document.effective_from,
        effective_to=document.effective_to,
        status=_map_status(source_effect_status),
        source_effect_status=source_effect_status,
        source_url=source.expected_public_url,
        content_url=detail_url(source.document_guid),
        retrieved_at=retrieved_at or datetime.now(UTC),
        content_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        snapshot_id=source.snapshot_id,
    )
    return PortalDetail(
        metadata=metadata,
        html=document.html,
        raw_bytes=raw_bytes,
        title_matches_expected=" ".join(document.title.split())
        == " ".join(source.expected_title.split()),
    )


class PortalClient:
    """Fetches one pre-approved GUID with TLS, timeout, and response-size limits."""

    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes

    def fetch_raw(self, source: ReviewedSource) -> bytes:
        """Fetch raw response bytes; schema validation belongs after quarantine storage."""

        portal_request = request.Request(
            detail_url(source.document_guid),
            headers={"Accept": "application/json", "User-Agent": "traffic-legal-qa/0.1"},
        )
        try:
            with request.urlopen(portal_request, timeout=self._timeout_seconds) as response:
                if response.status != 200:
                    raise PortalFetchError(f"portal returned HTTP {response.status}")
                raw_bytes = bytes(response.read(self._max_response_bytes + 1))
        except error.HTTPError as exc:
            raise PortalFetchError(f"portal returned HTTP {exc.code}") from exc
        except error.URLError as exc:
            raise PortalFetchError("portal request failed") from exc

        if len(raw_bytes) > self._max_response_bytes:
            raise PortalFetchError("portal response exceeded byte limit")
        return raw_bytes
