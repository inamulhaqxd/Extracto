from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ComplianceState(str, Enum):
    COMPLIANT = "COMPLIANT"
    PARTIALLY_COMPLIANT = "PARTIALLY_COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    NOT_FOUND = "NOT_FOUND"
    AMBIGUOUS = "AMBIGUOUS"


class FactItem(BaseModel):
    id: str | None = None
    field_name: str
    value: str
    numeric_value: float | None = None
    unit: str | None = None
    source_document_id: str | None = None
    source_page: int | None = None
    source_table_id: str | None = None
    source_image_id: str | None = None
    source_type: str = "text"  # text, table, image, ocr
    confidence: float = 1.0
    extraction_method: str = "native"
    metadata_json: dict[str, Any] | None = None


class EvidenceItem(BaseModel):
    source_document_id: str | None = None
    source_page: int | None = None
    source_table_id: str | None = None
    source_image_id: str | None = None
    source_type: str = "text"
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    extraction_method: str
    citation: str
    reasoning: str | None = None
    metadata_json: dict[str, Any] | None = None


class LayerResult(BaseModel):
    layer_name: str
    state: ComplianceState
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    matched_value: str | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)


class ComplianceDecision(BaseModel):
    requirement_id: str | None = None
    requirement_text: str
    vendor_name: str | None = None
    state: ComplianceState
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    matched_value: str | None = None
    resolving_layer: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    conflicting_evidence: list[EvidenceItem] = Field(default_factory=list)
    metadata_json: dict[str, Any] | None = None
