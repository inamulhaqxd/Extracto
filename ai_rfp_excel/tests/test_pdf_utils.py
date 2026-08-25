import tempfile
from pathlib import Path

import pytest

from ai_rfp_excel.app.ingestion.pdf.utils import calculate_file_hash, get_file_info, is_duplicate


def test_calculate_file_hash() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        f.write(b"test content")
        file_path = f.name

    hash1 = calculate_file_hash(file_path)
    hash2 = calculate_file_hash(file_path)

    assert hash1 == hash2
    assert len(hash1) == 64

    Path(file_path).unlink()


def test_get_file_info() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        f.write(b"test content")
        file_path = f.name

    info = get_file_info(file_path)

    assert info["filename"].endswith(".pdf")
    assert len(info["file_hash"]) == 64
    assert info["file_size"] > 0
    assert info["content_type"] == "application/pdf"

    Path(file_path).unlink()


def test_is_duplicate_false() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        f.write(b"test content")
        file_path = f.name

    is_dup, doc_id = is_duplicate(file_path, {})

    assert is_dup is False
    assert doc_id is None

    Path(file_path).unlink()


def test_is_duplicate_true() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        f.write(b"test content")
        file_path = f.name

    file_hash = calculate_file_hash(file_path)
    existing_hashes = {file_hash: "existing-doc-id"}

    is_dup, doc_id = is_duplicate(file_path, existing_hashes)

    assert is_dup is True
    assert doc_id == "existing-doc-id"

    Path(file_path).unlink()
