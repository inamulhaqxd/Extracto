from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PageContent(BaseModel):
    page_number: int
    content_type: str
    text: Optional[str] = None
    ocr_text: Optional[str] = None
    extraction_method: str
    confidence: Optional[float] = None


class TableData(BaseModel):
    table_id: str
    page_number: int
    headers: list[str]
    rows: list[list[str]]
    position: Optional[dict] = None
    surrounding_heading: Optional[str] = None


class ImageData(BaseModel):
    image_id: str
    page_number: int
    image_path: str
    bounding_box: Optional[dict] = None
    extraction_method: str
    ocr_text: Optional[str] = None
    vision_analysis: Optional[dict] = None


class ProcessingContext(BaseModel):
    document_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    run_id: UUID = Field(default_factory=uuid4)
    pdf_pages: list[PageContent] = Field(default_factory=list)
    extracted_tables: list[TableData] = Field(default_factory=list)
    extracted_images: list[ImageData] = Field(default_factory=list)
    ocr_results: list[PageContent] = Field(default_factory=list)
    canonical_data: dict[str, Any] = Field(default_factory=dict)
    excel_structure: dict[str, Any] = Field(default_factory=dict)
    requirements: list[dict[str, Any]] = Field(default_factory=list)
    compliance_results: list[dict[str, Any]] = Field(default_factory=list)
    current_step: str = "upload"
    status: StepStatus = StepStatus.PENDING
    errors: list[dict[str, Any]] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_error(self, step: str, message: str, details: Any = None):
        self.errors.append({
            "step": step,
            "message": message,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def set_step(self, step: str):
        self.current_step = step

    def mark_processing(self):
        self.status = StepStatus.PROCESSING
        if self.started_at is None:
            self.started_at = datetime.utcnow()

    def mark_completed(self):
        self.status = StepStatus.COMPLETED
        self.completed_at = datetime.utcnow()

    def mark_failed(self, step: str, error: str):
        self.status = StepStatus.FAILED
        self.add_error(step, error)
        self.completed_at = datetime.utcnow()
