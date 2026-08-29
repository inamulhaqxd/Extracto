import hashlib
from pathlib import Path

VALID_EXCEL_EXTENSIONS = {".xlsx", ".xlsm", ".xltx", ".xltm"}
MAX_EXCEL_SIZE_MB = 50


def calculate_workbook_hash(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(8192), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def validate_excel_file(
    file_path: str,
    max_size_mb: int = MAX_EXCEL_SIZE_MB,
) -> tuple[bool, str | None]:
    path = Path(file_path)

    if not path.exists():
        return False, f"Excel file does not exist: {file_path}"

    if path.suffix.lower() not in VALID_EXCEL_EXTENSIONS:
        return False, (
            f"Invalid file extension '{path.suffix}'. "
            f"Allowed Excel extensions: {', '.join(sorted(VALID_EXCEL_EXTENSIONS))}"
        )

    file_size_bytes = path.stat().st_size
    max_size_bytes = max_size_mb * 1024 * 1024

    if file_size_bytes > max_size_bytes:
        file_size_mb = round(file_size_bytes / (1024 * 1024), 2)
        return False, (
            f"File size of {file_size_mb}MB exceeds maximum allowed limit of {max_size_mb}MB. "
            "Please upload a smaller workbook."
        )

    return True, None
