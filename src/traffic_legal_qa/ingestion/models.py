from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DocumentStatus = Literal["current", "repealed", "amended", "unknown"]
LegalUnitType = Literal["part", "chapter", "section", "article", "clause", "point"]


class LegalDocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    document_type: str = Field(min_length=1)
    issuer: str = Field(min_length=1)
    issued_date: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    status: DocumentStatus = "unknown"
    domain: Literal["traffic"] = "traffic"
    source_url: str = Field(min_length=1)
    retrieved_at: datetime
    content_sha256: str = ""
    snapshot_id: str = Field(min_length=1)


class LegalUnit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    unit_type: LegalUnitType
    number: str = Field(min_length=1)
    title: str | None = None
    text: str = Field(min_length=1)
    parent_id: str = Field(min_length=1)
    path: tuple[str, ...] = Field(min_length=1)
    parser_version: str = Field(default="parser-1", min_length=1)


class ParsedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: LegalDocumentMetadata
    units: list[LegalUnit]
