from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ColumnType(str, Enum):
    INDEX = "index"
    SECTION = "section"
    REQUIREMENT = "requirement"
    OFFERED_SPEC = "offered_spec"
    VENDOR = "vendor"
    COMPLIANCE = "compliance"
    REMARKS = "remarks"
    UNKNOWN = "unknown"


class DetectedColumn(BaseModel):
    column_letter: str
    column_index: int
    header_name: str
    column_type: ColumnType
    vendor_name: str | None = None


class ExcelRequirement(BaseModel):
    requirement_id: str
    sheet_name: str
    row_number: int
    section: str | None = None
    subsection: str | None = None
    requirement_text: str
    source_cell: str
    source_range: str | None = None
    vendor_cells: dict[str, str] = Field(default_factory=dict)
    offered_spec_cells: dict[str, str] = Field(default_factory=dict)
    compliance_cells: dict[str, str] = Field(default_factory=dict)
    remarks_cells: dict[str, str] = Field(default_factory=dict)
    empty_slots: list[str] = Field(default_factory=list)
    raw_values: dict[str, Any] = Field(default_factory=dict)


class ExcelSection(BaseModel):
    name: str
    start_row: int
    end_row: int | None = None
    subsections: list[str] = Field(default_factory=list)
    requirements: list[ExcelRequirement] = Field(default_factory=list)


class SheetAnalysis(BaseModel):
    sheet_name: str
    sheet_index: int
    dimensions: dict[str, int]
    merged_cells: list[dict[str, Any]] = Field(default_factory=list)
    hidden_rows: list[int] = Field(default_factory=list)
    hidden_columns: list[str] = Field(default_factory=list)
    header_row: int | None = None
    columns: list[DetectedColumn] = Field(default_factory=list)
    sections: list[ExcelSection] = Field(default_factory=list)
    requirements: list[ExcelRequirement] = Field(default_factory=list)


class WorkbookAnalysis(BaseModel):
    workbook_id: str
    filename: str
    file_hash: str
    file_size: int
    version: int = 1
    total_sheets: int
    sheet_names: list[str]
    sheets: list[SheetAnalysis] = Field(default_factory=list)
    total_requirements: int = 0


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ValidationIssue(BaseModel):
    severity: ValidationSeverity
    sheet_name: str | None = None
    cell: str | None = None
    message: str
    rule: str


class ValidationReport(BaseModel):
    is_valid: bool
    total_checks: int
    passed_checks: int
    issues: list[ValidationIssue] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class PopulationResult(BaseModel):
    output_file_path: str
    filename: str
    total_populated_cells: int
    summary_sheet_created: bool
    validation_report: ValidationReport

