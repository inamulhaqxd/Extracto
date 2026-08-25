import fitz

from ai_rfp_excel.app.config import settings
from ai_rfp_excel.app.ingestion.models import OCRResult


def render_page_to_image(
    pdf_path: str,
    page_number: int,
    output_dir: str | None = None,
    dpi: int = 300,
) -> str:
    from pathlib import Path

    output_path = Path(output_dir or settings.PROCESSED_DIR)
    output_path.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    page = doc[page_number]

    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix)

    image_filename = f"page_{page_number + 1:04d}.png"
    image_path = output_path / image_filename

    pix.save(str(image_path))

    doc.close()
    return str(image_path)


def render_pages_batch(
    pdf_path: str,
    page_numbers: list[int],
    output_dir: str | None = None,
    dpi: int = 300,
) -> dict[int, str]:
    rendered: dict[int, str] = {}
    for page_num in page_numbers:
        image_path = render_page_to_image(pdf_path, page_num, output_dir, dpi)
        rendered[page_num] = image_path
    return rendered


def ocr_with_tesseract(image_path: str) -> OCRResult:
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

        confidences = [int(c) for c in data["conf"] if int(c) > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return OCRResult(
            page_number=0,
            text=text.strip(),
            confidence=avg_confidence / 100.0,
            engine="tesseract",
        )
    except Exception:
        return OCRResult(
            page_number=0,
            text="",
            confidence=0.0,
            engine="tesseract",
        )


def ocr_page(
    pdf_path: str,
    page_number: int,
    output_dir: str | None = None,
    min_confidence: float = 0.6,
) -> OCRResult:
    image_path = render_page_to_image(pdf_path, page_number, output_dir)

    result = ocr_with_tesseract(image_path)
    result.page_number = page_number

    return result


def needs_ocr(pdf_path: str, page_number: int, text_threshold: int = 50) -> bool:
    doc = fitz.open(pdf_path)
    page = doc[page_number]
    text = page.get_text()
    doc.close()
    return len(text.strip()) < text_threshold
