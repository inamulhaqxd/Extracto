from pathlib import Path

import fitz

from ai_rfp_excel.app.config import settings
from ai_rfp_excel.app.ingestion.models import ExtractedImage


def extract_images_from_page(
    pdf_path: str,
    page_number: int,
    output_dir: str | None = None,
) -> list[ExtractedImage]:
    images: list[ExtractedImage] = []
    output_path = Path(output_dir or settings.IMAGES_DIR)
    output_path.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    page = doc[page_number]
    image_list = page.get_images(full=True)

    for img_idx, img in enumerate(image_list):
        xref = img[0]
        base_image = doc.extract_image(xref)
        image_bytes = base_image["image"]
        image_ext = base_image["ext"]

        image_id = f"IMG{page_number + 1:02d}-{img_idx + 1:02d}"
        image_filename = f"{image_id}.{image_ext}"
        image_filepath = output_path / image_filename

        with open(image_filepath, "wb") as f:
            f.write(image_bytes)

        bbox_dict = {
            "x": img[2],
            "y": img[3],
            "width": img[4],
            "height": img[5],
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

    doc.close()
    return images


def extract_images_from_pdf(
    pdf_path: str,
    output_dir: str | None = None,
) -> list[ExtractedImage]:
    all_images: list[ExtractedImage] = []

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    doc.close()

    for page_num in range(total_pages):
        page_images = extract_images_from_page(pdf_path, page_num, output_dir)
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
