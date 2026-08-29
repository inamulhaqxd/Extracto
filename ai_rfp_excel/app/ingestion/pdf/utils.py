import hashlib
from pathlib import Path


def calculate_file_hash(file_path: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(8192), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def is_duplicate(file_path: str, existing_hashes: dict[str, str]) -> tuple[bool, str | None]:
    file_hash = calculate_file_hash(file_path)
    for existing_hash, doc_id in existing_hashes.items():
        if file_hash == existing_hash:
            return True, doc_id
    return False, None


def get_file_info(file_path: str) -> dict[str, str | int]:
    path = Path(file_path)
    stat = path.stat()
    return {
        "filename": path.name,
        "file_hash": calculate_file_hash(file_path),
        "file_size": stat.st_size,
        "content_type": "application/pdf",
    }
