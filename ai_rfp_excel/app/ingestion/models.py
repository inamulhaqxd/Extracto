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
    bbox: dict[str, Any] | None = None


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
    bbox: dict[str, Any] | None = None


class ProvenanceRecord(BaseModel):
    entity_type: str
    entity_id: str | None = None
    document_id: str
    page_number: int
    bbox: dict[str, Any] | None = None
    source: str
    extraction_method: str
    confidence: float
    content_preview: str | None = None


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

    def get_provenance_records(self) -> list[ProvenanceRecord]:
        records: list[ProvenanceRecord] = []

        for page in self.pdf_pages:
            if page.native_text and page.native_text.text.strip():
                records.append(
                    ProvenanceRecord(
                        entity_type="text",
                        entity_id=f"TXT-{page.page_number:04d}",
                        document_id=self.document_id,
                        page_number=page.page_number,
                        bbox=page.native_text.bbox,
                        source=page.native_text.source,
                        extraction_method="native_pdf",
                        confidence=page.native_text.confidence,
                        content_preview=page.native_text.text[:100],
                    )
                )

            for tbl in page.tables:
                records.append(
                    ProvenanceRecord(
                        entity_type="table",
                        entity_id=tbl.table_id,
                        document_id=self.document_id,
                        page_number=tbl.page_number,
                        bbox=tbl.bbox,
                        source="pdf_table",
                        extraction_method="pdfplumber",
                        confidence=1.0,
                        content_preview=f"Headers: {', '.join(tbl.headers[:3])}",
                    )
                )

            for img in page.images:
                records.append(
                    ProvenanceRecord(
                        entity_type="image",
                        entity_id=img.image_id,
                        document_id=self.document_id,
                        page_number=img.page_number,
                        bbox=img.bbox,
                        source="pdf_image",
                        extraction_method=img.extraction_method,
                        confidence=1.0,
                        content_preview=img.image_path,
                    )
                )

            if page.ocr_result and page.ocr_result.text.strip():
                records.append(
                    ProvenanceRecord(
                        entity_type="ocr",
                        entity_id=f"OCR-{page.page_number:04d}",
                        document_id=self.document_id,
                        page_number=page.page_number,
                        bbox=page.ocr_result.bbox,
                        source="ocr",
                        extraction_method=page.ocr_result.engine,
                        confidence=page.ocr_result.confidence,
                        content_preview=page.ocr_result.text[:100],
                    )
                )

        return records

    def to_checkpoint_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_checkpoint_dict(cls, data: dict[str, Any]) -> "ProcessingContext":
        return cls.model_validate(data)

