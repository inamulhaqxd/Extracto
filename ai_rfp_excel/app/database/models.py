import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ai_rfp_excel.app.database.connection import Base


def generate_uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    processing_runs: Mapped[list["ProcessingRun"]] = relationship(back_populates="user")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    pages: Mapped[list["DocumentPage"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    tables: Mapped[list["DocumentTable"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    images: Mapped[list["DocumentImage"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    extracted_facts: Mapped[list["ExtractedFact"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    processing_runs_pdf: Mapped[list["ProcessingRun"]] = relationship(
        back_populates="pdf_document", foreign_keys="ProcessingRun.pdf_document_id"
    )


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    native_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_scanned: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["Document"] = relationship(back_populates="pages")
    tables: Mapped[list["DocumentTable"]] = relationship(back_populates="page")
    images: Mapped[list["DocumentImage"]] = relationship(back_populates="page")


class DocumentTable(Base):
    __tablename__ = "document_tables"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_pages.id", ondelete="CASCADE"), nullable=False
    )
    table_index: Mapped[int] = mapped_column(Integer, nullable=False)
    table_id: Mapped[str] = mapped_column(String(50), nullable=False)
    headers: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    rows: Mapped[list[list[Any]]] = mapped_column(JSONB, nullable=False)
    merged_cells: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    section_heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    bbox: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["Document"] = relationship(back_populates="tables")
    page: Mapped["DocumentPage"] = relationship(back_populates="tables")


class DocumentImage(Base):
    __tablename__ = "document_images"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_pages.id", ondelete="CASCADE"), nullable=False
    )
    image_index: Mapped[int] = mapped_column(Integer, nullable=False)
    image_id: Mapped[str] = mapped_column(String(50), nullable=False)
    image_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    bbox: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(50), nullable=False)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    vision_analysis: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["Document"] = relationship(back_populates="images")
    page: Mapped["DocumentPage"] = relationship(back_populates="images")


class ExtractedFact(Base):
    __tablename__ = "extracted_facts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    equipment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("equipment.id", ondelete="SET NULL"), nullable=True
    )
    field_name: Mapped[str] = mapped_column(String(200), nullable=False)
    original_value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_table_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_image_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(50), nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["Document"] = relationship(back_populates="extracted_facts")
    equipment: Mapped["Equipment | None"] = relationship(back_populates="extracted_facts")


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    vendor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    part_number: Mapped[str | None] = mapped_column(String(200), nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    specifications: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    normalized_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    extracted_facts: Mapped[list["ExtractedFact"]] = relationship(back_populates="equipment")


class Workbook(Base):
    __tablename__ = "workbooks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sheets: Mapped[list["WorkbookSheet"]] = relationship(back_populates="workbook", cascade="all, delete-orphan")
    processing_runs_wb: Mapped[list["ProcessingRun"]] = relationship(
        back_populates="workbook", foreign_keys="ProcessingRun.workbook_id"
    )


class WorkbookSheet(Base):
    __tablename__ = "workbook_sheets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    workbook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workbooks.id", ondelete="CASCADE"), nullable=False
    )
    sheet_name: Mapped[str] = mapped_column(String(200), nullable=False)
    sheet_index: Mapped[int] = mapped_column(Integer, nullable=False)
    dimensions: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    merged_cells: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    hidden_rows: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True)
    hidden_columns: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    workbook: Mapped["Workbook"] = relationship(back_populates="sheets")
    requirements: Mapped[list["Requirement"]] = relationship(back_populates="sheet", cascade="all, delete-orphan")


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    sheet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workbook_sheets.id", ondelete="CASCADE"), nullable=False
    )
    requirement_index: Mapped[int] = mapped_column(Integer, nullable=False)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    section: Mapped[str | None] = mapped_column(String(200), nullable=True)
    subsection: Mapped[str | None] = mapped_column(String(200), nullable=True)
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_cell: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_range: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sheet: Mapped["WorkbookSheet"] = relationship(back_populates="requirements")
    mappings: Mapped[list["Mapping"]] = relationship(back_populates="requirement", cascade="all, delete-orphan")


class Mapping(Base):
    __tablename__ = "mappings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False
    )
    target_sheet: Mapped[str] = mapped_column(String(200), nullable=False)
    target_cell: Mapped[str] = mapped_column(String(20), nullable=False)
    target_column_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    vendor_column: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mapping_type: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    requirement: Mapped["Requirement"] = relationship(back_populates="mappings")
    compliance_results: Mapped[list["ComplianceResult"]] = relationship(
        back_populates="mapping", cascade="all, delete-orphan"
    )


class ComplianceResult(Base):
    __tablename__ = "compliance_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    mapping_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mappings.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("processing_runs.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    ai_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_constraints: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    mapping: Mapped["Mapping"] = relationship(back_populates="compliance_results")
    run: Mapped["ProcessingRun"] = relationship(back_populates="compliance_results")
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="compliance_result", cascade="all, delete-orphan")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    compliance_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("compliance_results.id", ondelete="CASCADE"), nullable=False
    )
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_table_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_image_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(50), nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    compliance_result: Mapped["ComplianceResult"] = relationship(back_populates="evidence")
    document: Mapped["Document | None"] = relationship(foreign_keys=[source_document_id])


class ProcessingRun(Base):
    __tablename__ = "processing_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    pdf_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    workbook_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workbooks.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    current_step: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(200), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User | None"] = relationship(back_populates="processing_runs")
    pdf_document: Mapped["Document | None"] = relationship(
        foreign_keys=[pdf_document_id], back_populates="processing_runs_pdf"
    )
    workbook: Mapped["Workbook | None"] = relationship(
        foreign_keys=[workbook_id], back_populates="processing_runs_wb"
    )
    compliance_results: Mapped[list["ComplianceResult"]] = relationship(back_populates="run")
    validation_results: Mapped[list["ValidationResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_uuid)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("processing_runs.id", ondelete="CASCADE"), nullable=False
    )
    check_name: Mapped[str] = mapped_column(String(200), nullable=False)
    check_category: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped["ProcessingRun"] = relationship(back_populates="validation_results")
