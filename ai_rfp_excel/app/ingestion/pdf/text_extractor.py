import fitz

from ai_rfp_excel.app.ingestion.models import ExtractedText


def extract_text_from_page(pdf_path: str, page_number: int) -> ExtractedText:
    doc = fitz.open(pdf_path)
    page = doc[page_number]
    text = page.get_text()
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

    return ExtractedText(
        page_number=page_number,
        text=text.strip(),
        source="native_pdf",
        confidence=1.0 if text.strip() else 0.0,
        bbox=bbox,
    )



def extract_text_from_pdf(pdf_path: str) -> list[ExtractedText]:
    results: list[ExtractedText] = []
    doc = fitz.open(pdf_path)

    for page_num in range(len(doc)):
        result = extract_text_from_page(pdf_path, page_num)
        results.append(result)

    doc.close()
    return results


def has_text_content(pdf_path: str, page_number: int, min_chars: int = 50) -> bool:
    doc = fitz.open(pdf_path)
    page = doc[page_number]
    text = page.get_text()
    doc.close()
    return len(text.strip()) >= min_chars
