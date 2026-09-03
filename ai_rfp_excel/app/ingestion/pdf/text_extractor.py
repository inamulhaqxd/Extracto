from typing import Any

from ai_rfp_excel.app.ingestion.models import ExtractedText


def extract_text_from_page(pdf_path: str, page_number: int) -> ExtractedText:
    text = ""
    bbox: dict[str, Any] = {}

    # Engine 1: pypdfium2 (fast native C backend, zero DLL runtime issues)
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_path)
        if page_number < len(pdf):
            page = pdf[page_number]
            text = page.get_textpage().get_text_range() or ""
            w, h = page.get_size()
            bbox = {"x0": 0.0, "top": 0.0, "x1": round(float(w), 2), "bottom": round(float(h), 2), "width": round(float(w), 2), "height": round(float(h), 2)}
        pdf.close()
    except Exception:
        # Engine 2: fitz / PyMuPDF
        try:
            import fitz
            doc = fitz.open(pdf_path)
            if page_number < len(doc):
                page = doc[page_number]
                text = page.get_text() or ""
                rect = page.rect
                bbox = {
                    "x0": round(float(rect.x0), 2),
                    "top": round(float(rect.y0), 2),
                    "x1": round(float(rect.x1), 2),
                    "bottom": round(float(rect.y1), 2),
                    "width": round(float(rect.width), 2),
                    "height": round(float(rect.height), 2),
                }
            doc.close()
        except Exception:
            # Engine 3: pdfplumber
            try:
                import pdfplumber
                with pdfplumber.open(pdf_path) as pdf:
                    if page_number < len(pdf.pages):
                        page = pdf.pages[page_number]
                        text = page.extract_text() or ""
                        bbox = {"x0": 0.0, "top": 0.0, "x1": float(page.width), "bottom": float(page.height), "width": float(page.width), "height": float(page.height)}
            except Exception:
                text = ""

    return ExtractedText(
        page_number=page_number,
        text=text.strip(),
        source="native_pdf",
        confidence=1.0 if text.strip() else 0.0,
        bbox=bbox,
    )


def extract_text_from_pdf(pdf_path: str) -> list[ExtractedText]:
    results: list[ExtractedText] = []

    # Fast page count detection
    total_pages = 0
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(pdf_path)
        total_pages = len(pdf)
        pdf.close()
    except Exception:
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
        except Exception:
            try:
                import fitz
                doc = fitz.open(pdf_path)
                total_pages = len(doc)
                doc.close()
            except Exception:
                total_pages = 0

    for page_num in range(total_pages):
        result = extract_text_from_page(pdf_path, page_num)
        results.append(result)

    return results


def has_text_content(pdf_path: str, page_number: int, min_chars: int = 50) -> bool:
    extracted = extract_text_from_page(pdf_path, page_number)
    return len(extracted.text.strip()) >= min_chars

