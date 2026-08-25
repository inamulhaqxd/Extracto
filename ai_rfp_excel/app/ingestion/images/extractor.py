import hashlib
from pathlib import Path
from typing import Optional

from app.document.processing_context import ImageData
from app.config import settings


class ImageExtractor:
    def __init__(self):
        self.images_dir = Path(settings.images_dir)
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def extract_images(self, pdf_path: str, page_number: int, document_id: str) -> list[ImageData]:
        images = []

        try:
            images.extend(self._extract_with_pymupdf(pdf_path, page_number, document_id))
        except Exception:
            pass

        return images

    def _extract_with_pymupdf(self, pdf_path: str, page_number: int, document_id: str) -> list[ImageData]:
        import fitz

        images = []
        doc = fitz.open(pdf_path)

        if page_number >= len(doc):
            doc.close()
            return images

        page = doc[page_number]
        image_list = page.get_images()

        for idx, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]

            img_hash = hashlib.md5(image_bytes).hexdigest()
            image_filename = f"{document_id}_p{page_number + 1}_img{idx + 1}.{image_ext}"
            image_path = self.images_dir / image_filename

            with open(image_path, "wb") as f:
                f.write(image_bytes)

            images.append(ImageData(
                image_id=f"IMG{page_number + 1:02d}-{idx + 1:02d}",
                page_number=page_number + 1,
                image_path=str(image_path),
                extraction_method="pymupdf",
            ))

        doc.close()
        return images
