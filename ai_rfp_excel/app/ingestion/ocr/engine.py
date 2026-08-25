from pathlib import Path
from typing import Optional

from app.document.processing_context import PageContent, ImageData
from app.config import settings


class OCREngine:
    def __init__(self):
        self.ocr_dir = Path(settings.ocr_dir)
        self.ocr_dir.mkdir(parents=True, exist_ok=True)

    def ocr_page(self, pdf_path: str, page_number: int) -> Optional[PageContent]:
        rendered_path = self._render_page(pdf_path, page_number)
        if not rendered_path:
            return None

        text = self._ocr_with_tesseract(rendered_path)

        if not text or len(text.strip()) < 10:
            paddle_text = self._ocr_with_paddleocr(rendered_path)
            if paddle_text and len(paddle_text.strip()) > len(text.strip()):
                text = paddle_text

        Path(rendered_path).unlink(missing_ok=True)

        if not text or not text.strip():
            return None

        return PageContent(
            page_number=page_number + 1,
            content_type="scanned",
            ocr_text=text,
            extraction_method="ocr",
            confidence=0.8,
        )

    def ocr_image(self, image_path: str) -> Optional[str]:
        text = self._ocr_with_tesseract(image_path)

        if not text or len(text.strip()) < 10:
            paddle_text = self._ocr_with_paddleocr(image_path)
            if paddle_text and len(paddle_text.strip()) > len(text.strip()):
                text = paddle_text

        return text if text and text.strip() else None

    def _render_page(self, pdf_path: str, page_number: int) -> Optional[str]:
        try:
            import fitz

            doc = fitz.open(pdf_path)
            if page_number >= len(doc):
                doc.close()
                return None

            page = doc[page_number]
            pix = page.get_pixmap(dpi=300)

            output_path = self.ocr_dir / f"rendered_p{page_number + 1}.png"
            pix.save(str(output_path))

            doc.close()
            return str(output_path)
        except Exception:
            return None

    def _ocr_with_tesseract(self, image_path: str) -> Optional[str]:
        try:
            import pytesseract
            from PIL import Image

            img = Image.open(image_path)
            text = pytesseract.image_to_string(img)
            return text
        except Exception:
            return None

    def _ocr_with_paddleocr(self, image_path: str) -> Optional[str]:
        try:
            from paddleocr import PaddleOCR

            ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            result = ocr.ocr(image_path, cls=True)

            if not result or not result[0]:
                return None

            text_parts = []
            for line in result[0]:
                if line[1]:
                    text_parts.append(line[1][0])

            return "\n".join(text_parts)
        except Exception:
            return None
