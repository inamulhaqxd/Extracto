from pathlib import Path

try:
    import fitz
except Exception:
    fitz = None


from ai_rfp_excel.app.config import settings
from ai_rfp_excel.app.ingestion.models import ExtractedImage

MIN_IMAGE_WIDTH = 100
MIN_IMAGE_HEIGHT = 100
MIN_IMAGE_PIXELS = 15000


def extract_images_from_page(
    pdf_path: str,
    page_number: int,
    output_dir: str | None = None,
    filter_small: bool = True,
) -> list[ExtractedImage]:
    images: list[ExtractedImage] = []
    output_path = Path(output_dir or settings.IMAGES_DIR)
    output_path.mkdir(parents=True, exist_ok=True)

    if fitz is None:
        return []

    doc = fitz.open(pdf_path)
    if page_number >= len(doc):
        doc.close()
        return []

    page = doc[page_number]
    image_list = page.get_images(full=True)

    for img_idx, img in enumerate(image_list):
        xref = img[0]
        try:
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            width = base_image["width"]
            height = base_image["height"]

            if filter_small and (
                width < MIN_IMAGE_WIDTH
                or height < MIN_IMAGE_HEIGHT
                or (width * height) < MIN_IMAGE_PIXELS
            ):
                continue

            image_filename = f"page_{page_number + 1:04d}_img_{img_idx + 1:02d}.{image_ext}"
            image_file_path = output_path / image_filename

            with open(image_file_path, "wb") as f:
                f.write(image_bytes)

            images.append(
                ExtractedImage(
                    image_id=f"IMG-P{page_number + 1:02d}-{img_idx + 1:02d}",
                    page_number=page_number,
                    image_path=str(image_file_path),
                )
            )
        except Exception:
            continue

    doc.close()
    return images


def extract_images_from_pdf(
    pdf_path: str,
    output_dir: str | None = None,
    filter_small: bool = True,
) -> list[ExtractedImage]:
    if fitz is None:
        return []

    all_images: list[ExtractedImage] = []

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()

    for page_num in range(total_pages):
        page_images = extract_images_from_page(pdf_path, page_num, output_dir, filter_small)
        all_images.extend(page_images)

    return all_images


def has_images(pdf_path: str, page_number: int) -> bool:
    if fitz is None:
        return False
    doc = fitz.open(pdf_path)
    if page_number >= len(doc):
        doc.close()
        return False
    page = doc[page_number]
    image_list = page.get_images(full=True)
    doc.close()
    return bool(image_list)
