"""Initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-08-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("is_admin", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer, default=1),
        sa.Column("total_pages", sa.Integer, nullable=True),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "document_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer, nullable=False),
        sa.Column("native_text", sa.Text, nullable=True),
        sa.Column("ocr_text", sa.Text, nullable=True),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("is_scanned", sa.Boolean, default=False),
        sa.Column("ocr_confidence", sa.Float, nullable=True),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "document_tables",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_pages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_index", sa.Integer, nullable=False),
        sa.Column("table_id", sa.String(50), nullable=False),
        sa.Column("headers", postgresql.JSONB, nullable=False),
        sa.Column("rows", postgresql.JSONB, nullable=False),
        sa.Column("merged_cells", postgresql.JSONB, nullable=True),
        sa.Column("section_heading", sa.Text, nullable=True),
        sa.Column("bbox", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "document_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_pages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image_index", sa.Integer, nullable=False),
        sa.Column("image_id", sa.String(50), nullable=False),
        sa.Column("image_path", sa.String(1000), nullable=False),
        sa.Column("bbox", postgresql.JSONB, nullable=True),
        sa.Column("extraction_method", sa.String(50), nullable=False),
        sa.Column("ocr_text", sa.Text, nullable=True),
        sa.Column("vision_analysis", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "equipment",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("vendor", sa.String(200), nullable=True),
        sa.Column("model", sa.String(200), nullable=True),
        sa.Column("part_number", sa.String(200), nullable=True),
        sa.Column("quantity", sa.Integer, nullable=True),
        sa.Column("specifications", postgresql.JSONB, nullable=True),
        sa.Column("normalized_name", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "extracted_facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("equipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("equipment.id", ondelete="SET NULL"), nullable=True),
        sa.Column("field_name", sa.String(200), nullable=False),
        sa.Column("original_value", sa.Text, nullable=False),
        sa.Column("normalized_value", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_page", sa.Integer, nullable=True),
        sa.Column("source_table_id", sa.String(50), nullable=True),
        sa.Column("source_image_id", sa.String(50), nullable=True),
        sa.Column("extraction_method", sa.String(50), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "workbooks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("version", sa.Integer, default=1),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "workbook_sheets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workbook_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workbooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sheet_name", sa.String(200), nullable=False),
        sa.Column("sheet_index", sa.Integer, nullable=False),
        sa.Column("dimensions", postgresql.JSONB, nullable=True),
        sa.Column("merged_cells", postgresql.JSONB, nullable=True),
        sa.Column("hidden_rows", postgresql.JSONB, nullable=True),
        sa.Column("hidden_columns", postgresql.JSONB, nullable=True),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sheet_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workbook_sheets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requirement_index", sa.Integer, nullable=False),
        sa.Column("requirement_text", sa.Text, nullable=False),
        sa.Column("section", sa.String(200), nullable=True),
        sa.Column("subsection", sa.String(200), nullable=True),
        sa.Column("row_number", sa.Integer, nullable=True),
        sa.Column("source_cell", sa.String(20), nullable=True),
        sa.Column("source_range", sa.String(50), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("requirement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_sheet", sa.String(200), nullable=False),
        sa.Column("target_cell", sa.String(20), nullable=False),
        sa.Column("target_column_name", sa.String(200), nullable=True),
        sa.Column("vendor_column", sa.String(200), nullable=True),
        sa.Column("mapping_type", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "processing_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pdf_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("workbook_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workbooks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("progress", sa.Float, default=0.0),
        sa.Column("current_step", sa.String(100), nullable=True),
        sa.Column("model_used", sa.String(200), nullable=True),
        sa.Column("prompt_version", sa.String(50), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "compliance_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("mapping_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mappings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("processing_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("ai_reasoning", sa.Text, nullable=True),
        sa.Column("structured_constraints", postgresql.JSONB, nullable=True),
        sa.Column("needs_review", sa.Boolean, default=False),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text, nullable=True),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("compliance_result_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("compliance_results.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_page", sa.Integer, nullable=True),
        sa.Column("source_table_id", sa.String(50), nullable=True),
        sa.Column("source_image_id", sa.String(50), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("extraction_method", sa.String(50), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "validation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("processing_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("check_name", sa.String(200), nullable=False),
        sa.Column("check_category", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("details", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("validation_results")
    op.drop_table("evidence")
    op.drop_table("compliance_results")
    op.drop_table("processing_runs")
    op.drop_table("mappings")
    op.drop_table("requirements")
    op.drop_table("workbook_sheets")
    op.drop_table("workbooks")
    op.drop_table("extracted_facts")
    op.drop_table("equipment")
    op.drop_table("document_images")
    op.drop_table("document_tables")
    op.drop_table("document_pages")
    op.drop_table("documents")
    op.drop_table("users")
