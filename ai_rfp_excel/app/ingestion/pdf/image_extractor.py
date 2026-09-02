try:
    import fitz
except Exception:
    fitz = None

import pypdfium2

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
            if not base_image:
                continue

            width = base_image.get("width", 0)
            height = base_image.get("height", 0)

            # Filter out tiny icons, decorative headers, bullets, or thin line borders
            if filter_small:
                if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
                    continue
                if (width * height) < MIN_IMAGE_PIXELS:
                    continue
                aspect = max(width, height) / max(min(width, height), 1)
                if aspect > 15:  # Line or divider bar
                    continue

            image_bytes = base_image["image"]
            image_ext = base_image["ext"]

            image_id = f"IMG{page_number + 1:02d}-{img_idx + 1:02d}"
            image_filename = f"{image_id}.{image_ext}"
            image_filepath = output_path / image_filename

            with open(image_filepath, "wb") as f:
                f.write(image_bytes)

            bbox_dict = {
                "x": img[2] if len(img) > 2 else 0,
                "y": img[3] if len(img) > 3 else 0,
                "width": width,
                "height": height,
            }

            images.append(
                ExtractedImage(
                    page_number=page_number,
                    image_id=image_id,
                    image_path=str(image_filepath),
                    bbox=bbox_dict,
                    extraction_method="pymupdf",
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
    all_images: list[ExtractedImage] = []

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()

    for page_num in range(total_pages):
        page_images = extract_images_from_page(pdf_path, page_num, output_dir, filter_small)
        all_images.extend(page_images)

    return all_images


def has_images(pdf_path: str, page_number: int) -> bool:
    doc = fitz.open(pdf_path)
    if page_number >= len(doc):
        doc.close()
        return False
    page = doc[page_number]
    image_list = page.get_images(full=True)
    doc.close()
    return bool(image_list)
