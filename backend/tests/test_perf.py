from pathlib import Path

import pytest

from tests.fixtures.make_statement import build_pdf
from app.anonymizer.masker import mask
from app.anonymizer.profile import load_profile

GENERIC = load_profile(Path(__file__).resolve().parents[1] / "profiles" / "generic.yaml")


def test_ten_page_mask_under_two_seconds() -> None:
    doc = build_pdf(pages=10)
    pdf_bytes = doc.tobytes()
    doc.close()
    assert pymupdf_page_count(pdf_bytes) == 10
    import time

    start = time.perf_counter()
    mask(pdf_bytes, GENERIC)
    elapsed = time.perf_counter() - start
    assert elapsed < 2, elapsed


def pymupdf_page_count(pdf_bytes: bytes) -> int:
    import pymupdf

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    count = doc.page_count
    doc.close()
    return count
