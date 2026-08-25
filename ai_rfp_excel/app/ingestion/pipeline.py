from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.document.processing_context import ProcessingContext, PageContent, TableData, ImageData
from app.ingestion.pdf.router import PDFRouter
from app.ingestion.tables.extractor import TableExtractor
from app.ingestion.images.extractor import ImageExtractor
from app.ingestion.ocr.engine import OCREngine
from app.ingestion.duplicate_detector import DuplicateDetector
from app.database.models import Document, DocumentPage, DocumentTable, DocumentImage
from app.logging_config import get_logger

logger = get_logger()


class PDFIngestionPipeline:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.pdf_router = PDFRouter()
        self.table_extractor = TableExtractor()
        self.image_extractor = ImageExtractor()
        self.ocr_engine = OCREngine()
        self.duplicate_detector = DuplicateDetector(db)

    async def ingest(
        self,
        pdf_path: str,
        user_id: str,
        context: Optional[ProcessingContext] = None,
    ) -> ProcessingContext:
        if context is None:
            context = ProcessingContext(user_id=user_id)

        context.mark_processing()
        context.set_step("ingestion")

        logger.info("starting_pdf_ingestion", pdf_path=pdf_path, user_id=user_id)

        try:
            file_hash = self.duplicate_detector.compute_file_hash(pdf_path)
            existing_doc = await self.duplicate_detector.check_duplicate(file_hash, user_id)

            if existing_doc:
                logger.info("duplicate_pdf_found", document_id=str(existing_doc.id))
                context.metadata["duplicate_document_id"] = str(existing_doc.id)
                context.metadata["warning"] = "Duplicate PDF detected. Previous results may be reused."

            doc = Document(
                id=context.document_id,
                user_id=user_id,
                filename=Path(pdf_path).name,
                file_hash=file_hash,
                file_size=Path(pdf_path).stat().st_size,
                file_path=pdf_path,
                status="processing",
                created_at=datetime.utcnow(),
            )
            self.db.add(doc)
            await self.db.flush()

            batch_size = settings.batch_size
            import fitz
            pdf_doc = fitz.open(pdf_path)
            total_pages = len(pdf_doc)
            pdf_doc.close()

            for batch_start in range(0, total_pages, batch_size):
                batch_end = min(batch_start + batch_size, total_pages)
                await self._process_batch(
                    pdf_path, batch_start, batch_end, context, doc
                )

            doc.page_count = total_pages
            doc.status = "processed"
            await self.db.flush()

            context.mark_completed()
            logger.info(
                "pdf_ingestion_completed",
                document_id=str(context.document_id),
                pages=total_pages,
                tables=len(context.extracted_tables),
                images=len(context.extracted_images),
            )

        except Exception as e:
            context.mark_failed("ingestion", str(e))
            logger.error("pdf_ingestion_failed", error=str(e))
            raise

        return context

    async def _process_batch(
        self,
        pdf_path: str,
        batch_start: int,
        batch_end: int,
        context: ProcessingContext,
        doc: Document,
    ):
        for page_num in range(batch_start, batch_end):
            try:
                await self._process_page(pdf_path, page_num, context, doc)
            except Exception as e:
                context.add_error(
                    f"page_{page_num + 1}",
                    f"Failed to process page {page_num + 1}: {str(e)}",
                )
                logger.error("page_processing_failed", page=page_num + 1, error=str(e))

    async def _process_page(
        self,
        pdf_path: str,
        page_num: int,
        context: ProcessingContext,
        doc: Document,
    ):
        page_results = self.pdf_router.parse_page(pdf_path, page_num)

        needs_ocr = not page_results or all(
            not r.text or len(r.text.strip()) < 10 for r in page_results
        )

        if needs_ocr:
            ocr_result = self.ocr_engine.ocr_page(pdf_path, page_num)
            if ocr_result:
                page_results.append(ocr_result)
                context.ocr_results.append(ocr_result)

        for page_content in page_results:
            context.pdf_pages.append(page_content)

            db_page = DocumentPage(
                id=uuid4(),
                document_id=doc.id,
                page_number=page_content.page_number,
                content_type=page_content.content_type,
                text=page_content.text,
                ocr_text=page_content.ocr_text,
                extraction_method=page_content.extraction_method,
                confidence=page_content.confidence,
                created_at=datetime.utcnow(),
            )
            self.db.add(db_page)

        tables = self.table_extractor.extract_tables(pdf_path, page_num)
        for table in tables:
            context.extracted_tables.append(table)

            db_table = DocumentTable(
                id=uuid4(),
                document_id=doc.id,
                page_id=db_page.id if page_results else uuid4(),
                table_id=table.table_id,
                headers=table.headers,
                rows=table.rows,
                position=table.position,
                surrounding_heading=table.surrounding_heading,
                created_at=datetime.utcnow(),
            )
            self.db.add(db_table)

        images = self.image_extractor.extract_images(pdf_path, page_num, str(doc.id))
        for image in images:
            context.extracted_images.append(image)

            ocr_text = self.ocr_engine.ocr_image(image.image_path)

            db_image = DocumentImage(
                id=uuid4(),
                document_id=doc.id,
                page_id=db_page.id if page_results else uuid4(),
                image_id=image.image_id,
                image_path=image.image_path,
                bounding_box=image.bounding_box,
                extraction_method=image.extraction_method,
                ocr_text=ocr_text,
                created_at=datetime.utcnow(),
            )
            self.db.add(db_image)

        await self.db.flush()
