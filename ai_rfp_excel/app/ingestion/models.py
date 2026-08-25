from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PageType(str, Enum):
    NATIVE_TEXT = "native_text"
    TABLE = "table"
    IMAGE = "image"
    SCANNED = "scanned"
    MIXED = "mixed"


class ExtractedText(BaseModel):
    page_number: int
    text: str
    source: str = "native_pdf"
    confidence: float = 1.0


class ExtractedTable(BaseModel):
    page_number: int
    table_id: str
    headers: list[str]
    rows: list[list[str]]
    merged_cells: list[dict[str, Any]] | None = None
    section_heading: str | None = None
    bbox: dict[str, Any] | None = None


class ExtractedImage(BaseModel):
    page_number: int
    image_id: str
    image_path: str
    bbox: dict[str, Any] | None = None
    extraction_method: str = "embedded"
    ocr_text: str | None = None


class OCRResult(BaseModel):
    page_number: int
    text: str
    confidence: float
    engine: str = "tesseract"


class PageResult(BaseModel):
    page_number: int
    page_type: PageType
    native_text: ExtractedText | None = None
    tables: list[ExtractedTable] = Field(default_factory=list)
    images: list[ExtractedImage] = Field(default_factory=list)
    ocr_result: OCRResult | None = None
    rendered_path: str | None = None
    errors: list[str] = Field(default_factory=list)


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    EXTRACTING_TEXT = "extracting_text"
    EXTRACTING_TABLES = "extracting_tables"
    EXTRACTING_IMAGES = "extracting_images"
    RUNNING_OCR = "running_ocr"
    RENDERING_PAGES = "rendering_pages"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class ProcessingContext(BaseModel):
    document_id: str
    user_id: str
    run_id: str
    pdf_pages: list[PageResult] = Field(default_factory=list)
    extracted_tables: list[ExtractedTable] = Field(default_factory=list)
    extracted_images: list[ExtractedImage] = Field(default_factory=list)
    ocr_results: list[OCRResult] = Field(default_factory=list)
    canonical_data: dict[str, Any] = Field(default_factory=dict)
    excel_structure: dict[str, Any] = Field(default_factory=dict)
    requirements: list[dict[str, Any]] = Field(default_factory=list)
    compliance_results: list[dict[str, Any]] = Field(default_factory=list)
    current_step: ProcessingStatus = ProcessingStatus.PENDING
    status: ProcessingStatus = ProcessingStatus.PENDING
    errors: list[str] = Field(default_factory=list)
    total_pages: int = 0
    processed_pages: int = 0
    failed_pages: list[int] = Field(default_factory=list)
