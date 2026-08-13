"""Validated boundaries for portal records and deterministic legal artifacts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

CorpusStatus = Literal["current", "repealed", "amended", "unknown"]
UnitType = Literal["part", "chapter", "section", "article", "clause", "point"]


def _require_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("must not be blank")
    return normalized


class ReviewedTextReplacement(BaseModel):
    """A curator-approved literal correction backed by an external primary source."""

    model_config = ConfigDict(frozen=True)

    find: str
    replace: str
    expected_count: int = Field(ge=1)
    evidence_url: str
    reason: str

    _validate_text = field_validator("find", "replace", "evidence_url", "reason")(_require_text)

    @field_validator("evidence_url")
    @classmethod
    def _require_https_url(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("must use HTTPS")
        return value


class ReviewedSource(BaseModel):
    """A human-approved portal record; discovery by title is intentionally excluded."""

    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    document_guid: str
    expected_document_id: str
    expected_title: str
    expected_public_url: str
    review_status: Literal["approved"] = "approved"
    reviewed_text_replacements: tuple[ReviewedTextReplacement, ...] = ()

    _validate_text = field_validator(
        "snapshot_id",
        "document_guid",
        "expected_document_id",
        "expected_title",
        "expected_public_url",
    )(_require_text)

    @field_validator("expected_public_url")
    @classmethod
    def _require_https_url(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("must use HTTPS")
        return value


class PortalEffectStatus(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    name: str = Field(alias="effectStatusName")

    _validate_name = field_validator("name")(_require_text)


class PortalNamedEntity(BaseModel):
    """A named metadata entity exposed by the current portal detail response."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore", frozen=True)

    name: str = Field(
        validation_alias=AliasChoices("docTypeName", "fieldName", "majorName", "organName")
    )

    _validate_name = field_validator("name")(_require_text)


class PortalSigner(BaseModel):
    """A signer and optional role as published by the portal."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore", frozen=True)

    name: str = Field(alias="signerName")
    job_title: str | None = Field(default=None, alias="jobTitleName")

    _validate_name = field_validator("name")(_require_text)

    @field_validator("job_title", mode="before")
    @classmethod
    def _empty_job_title_is_none(cls, value: object) -> object:
        return None if value == "" else value


class PortalDocumentData(BaseModel):
    """Only the portal fields needed by the ingestion contract."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    document_guid: str = Field(alias="docGUId")
    document_id: str = Field(alias="docIdentity")
    title: str = Field(alias="docName")
    html: str = Field(alias="docContent")
    issued_date: date | None = Field(default=None, alias="issueDate")
    effective_from: date | None = Field(default=None, alias="effectDate")
    effective_to: date | None = Field(default=None, alias="expireDate")
    effect_status: PortalEffectStatus | None = Field(default=None, alias="effectStatus")
    document_type_metadata: PortalNamedEntity | None = Field(default=None, alias="docType")
    fields: tuple[PortalNamedEntity, ...] = Field(default_factory=tuple)
    majors: tuple[PortalNamedEntity, ...] = Field(default_factory=tuple)
    issuing_organs: tuple[PortalNamedEntity, ...] = Field(default_factory=tuple, alias="organs")
    signers: tuple[PortalSigner, ...] = Field(default_factory=tuple)

    _validate_text = field_validator("document_guid", "document_id", "title", "html")(_require_text)

    @field_validator("issued_date", "effective_from", "effective_to", mode="before")
    @classmethod
    def _empty_date_is_none(cls, value: object) -> object:
        return None if value == "" else value


class PortalDetailEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: Literal[True]
    data: PortalDocumentData
    tab_name: str = Field(alias="tabName")


class CanonicalMetadata(BaseModel):
    """Source facts carried into every persisted artifact."""

    model_config = ConfigDict(frozen=True)

    document_id: str
    portal_document_guid: str
    title: str
    document_type: str
    portal_document_type: str | None = None
    issuer: str | None = None
    fields: tuple[str, ...] = ()
    majors: tuple[str, ...] = ()
    issuing_organs: tuple[str, ...] = ()
    signers: tuple[PortalSigner, ...] = ()
    issued_date: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    status: CorpusStatus
    source_effect_status: str | None = None
    source_url: str
    content_url: str
    retrieved_at: datetime
    content_sha256: str
    snapshot_id: str


class PortalDetail(BaseModel):
    """Validated response plus exact bytes for content-addressed storage."""

    model_config = ConfigDict(frozen=True)

    metadata: CanonicalMetadata
    html: str
    raw_bytes: bytes
    title_matches_expected: bool


class LegalUnit(BaseModel):
    """A deterministic node in the legal hierarchy."""

    model_config = ConfigDict(frozen=True)

    unit_id: str
    document_id: str
    unit_type: UnitType
    number: str
    title: str | None = None
    text: str
    parent_id: str | None = None
    path: tuple[str, ...]


class ParsedDocument(BaseModel):
    """Validated hierarchy ready to enter a draft manifest."""

    model_config = ConfigDict(frozen=True)

    artifact_version: Literal["2"]
    metadata: CanonicalMetadata
    normalizer_version: str
    parser_version: str
    units: tuple[LegalUnit, ...]
