from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum

from app.database.types import PortableJSON, PortableUUID


class Base(DeclarativeBase):
    pass


class RunStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PARTIAL = "PARTIAL"


class ComplianceState(str, enum.Enum):
    COMPLIANT = "COMPLIANT"
    PARTIALLY_COMPLIANT = "PARTIALLY_COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    NOT_FOUND = "NOT_FOUND"
    AMBIGUOUS = "AMBIGUOUS"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid4] = mapped_column(PortableUUID, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    preferred_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents: Mapped[list["Document"]] = relationship(back_populates="user")
    runs: Mapped[list["ProcessingRun"]] = relationship(back_populates="user")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid4] = mapped_column(PortableUUID, primary_key=True, default=uuid4)
    user_id: Mapped[uuid4] = mapped_column(PortableUUID, ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="uploaded")
    metadata_json: Mapped[Optional[dict]] = mapped_column(PortableJSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="documents")
    pages: Mapped[list["DocumentPage"]] = relationship(back_populates="document")
    tables: Mapped[list["DocumentTable"]] = relationship(back_populates="document")
    images: Mapped[list["DocumentImage"]] = relationship(back_populates="document")


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id: Mapped[uuid4] = mapped_column(PortableUUID, primary_key=True, default=uuid4)
    document_id: Mapped[uuid4] = mapped_column(PortableUUID, ForeignKey("documents.id"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped["Document"] = relationship(back_populates="pages")
    tables: Mapped[list["DocumentTable"]] = relationship(back_populates="page")
    images: Mapped[list["DocumentImage"]] = relationship(back_populates="page")


class DocumentTable(Base):
    __tablename__ = "document_tables"

    id: Mapped[uuid4] = mapped_column(PortableUUID, primary_key=True, default=uuid4)
    document_id: Mapped[uuid4] = mapped_column(PortableUUID, ForeignKey("documents.id"), nullable=False)
    page_id: Mapped[uuid4] = mapped_column(PortableUUID, ForeignKey("document_pages.id"), nullable=False)
    table_id: Mapped[str] = mapped_column(String(50), nullable=False)
    headers: Mapped[list] = mapped_column(PortableJSON, nullable=False)
    rows: Mapped[list] = mapped_column(PortableJSON, nullable=False)
    position: Mapped[Optional[dict]] = mapped_column(PortableJSON, nullable=True)
    surrounding_heading: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped["Document"] = relationship(back_populates="tables")
    page: Mapped["DocumentPage"] = relationship(back_populates="tables")


class DocumentImage(Base):
    __tablename__ = "document_images"

    id: Mapped[uuid4] = mapped_column(PortableUUID, primary_key=True, default=uuid4)
    document_id: Mapped[uuid4] = mapped_column(PortableUUID, ForeignKey("documents.id"), nullable=False)
    page_id: Mapped[uuid4] = mapped_column(PortableUUID, ForeignKey("document_pages.id"), nullable=False)
    image_id: Mapped[str] = mapped_column(String(50), nullable=False)
    image_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    bounding_box: Mapped[Optional[dict]] = mapped_column(PortableJSON, nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(50), nullable=False)
    ocr_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vision_analysis: Mapped[Optional[dict]] = mapped_column(PortableJSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped["Document"] = relationship(back_populates="images")
    page: Mapped["DocumentPage"] = relationship(back_populates="images")


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[uuid4] = mapped_column(PortableUUID, primary_key=True, default=uuid4)
    document_id: Mapped[uuid4] = mapped_column(PortableUUID, ForeignKey("documents.id"), nullable=False)
    sheet_name: Mapped[str] = mapped_column(String(255), nullable=False)
    row: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_cell: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_range: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Workbook(Base):
    __tablename__ = "workbooks"

    id: Mapped[uuid4] = mapped_column(PortableUUID, primary_key=True, default=uuid4)
    user_id: Mapped[uuid4] = mapped_column(PortableUUID, ForeignKey("users.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    sheet_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    sheets: Mapped[list["WorkbookSheet"]] = relationship(back_populates="workbook")


class WorkbookSheet(Base):
    __tablename__ = "workbook_sheets"

    id: Mapped[uuid4] = mapped_column(PortableUUID, primary_key=True, default=uuid4)
    workbook_id: Mapped[uuid4] = mapped_column(PortableUUID, ForeignKey("workbooks.id"), nullable=False)
    sheet_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sheet_index: Mapped[int] = mapped_column(Integer, nullable=False)
    has_requirements: Mapped[bool] = mapped_column(default=False)
    requirement_count: Mapped[int] = mapped_column(Integer, default=0)
    headers: Mapped[Optional[list]] = mapped_column(PortableJSON, nullable=True)
    vendor_columns: Mapped[Optional[list]] = mapped_column(PortableJSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    workbook: Mapped["Workbook"] = relationship(back_populates="sheets")


class Mapping(Base):
    __tablename__ = "mappings"

    id: Mapped[uuid4] = mapped_column(PortableUUID, primary_key=True, default=uuid4)
    requirement_id: Mapped[uuid4] = mapped_column(PortableUUID, ForeignKey("requirements.id"), nullable=False)
    canonical_field: Mapped[str] = mapped_column(String(255), nullable=False)
    excel_location: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    mapping_method: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ComplianceResult(Base):
    __tablename__ = "compliance_results"

    id: Mapped[uuid4] = mapped_column(PortableUUID, primary_key=True, default=uuid4)
    run_id: Mapped[uuid4] = mapped_column(PortableUUID, ForeignKey("processing_runs.id"), nullable=False)
    requirement_id: Mapped[uuid4] = mapped_column(PortableUUID, ForeignKey("requirements.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    ai_decision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    human_decision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_approved: Mapped[bool] = mapped_column(default=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    run: Mapped["ProcessingRun"] = relationship(back_populates="compliance_results")
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="compliance_result")


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid4] = mapped_column(PortableUUID, primary_key=True, default=uuid4)
    compliance_result_id: Mapped[uuid4] = mapped_column(PortableUUID, ForeignKey("compliance_results.id"), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    table_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    image_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    compliance_result: Mapped["ComplianceResult"] = relationship(back_populates="evidence")


class ProcessingRun(Base):
    __tablename__ = "processing_runs"

    id: Mapped[uuid4] = mapped_column(PortableUUID, primary_key=True, default=uuid4)
    user_id: Mapped[uuid4] = mapped_column(PortableUUID, ForeignKey("users.id"), nullable=False)
    document_id: Mapped[uuid4] = mapped_column(PortableUUID, ForeignKey("documents.id"), nullable=False)
    workbook_id: Mapped[uuid4] = mapped_column(PortableUUID, ForeignKey("workbooks.id"), nullable=False)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=RunStatus.PENDING.value)
    current_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processing_context: Mapped[Optional[dict]] = mapped_column(PortableJSON, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="runs")
    compliance_results: Mapped[list["ComplianceResult"]] = relationship(back_populates="run")
    validation_results: Mapped[list["ValidationResult"]] = relationship(back_populates="run")


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id: Mapped[uuid4] = mapped_column(PortableUUID, primary_key=True, default=uuid4)
    run_id: Mapped[uuid4] = mapped_column(PortableUUID, ForeignKey("processing_runs.id"), nullable=False)
    check_name: Mapped[str] = mapped_column(String(255), nullable=False)
    passed: Mapped[bool] = mapped_column(default=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(50), default="error")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    run: Mapped["ProcessingRun"] = relationship(back_populates="validation_results")


class ExtractedFact(Base):
    __tablename__ = "extracted_facts"

    id: Mapped[uuid4] = mapped_column(PortableUUID, primary_key=True, default=uuid4)
    document_id: Mapped[uuid4] = mapped_column(PortableUUID, ForeignKey("documents.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    field: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[dict] = mapped_column(PortableJSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[uuid4] = mapped_column(PortableUUID, primary_key=True, default=uuid4)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    vendor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    specifications: Mapped[Optional[dict]] = mapped_column(PortableJSON, nullable=True)
    source_evidence: Mapped[list] = mapped_column(PortableJSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
