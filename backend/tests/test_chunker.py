import pymupdf

from app.extractor.chunker import split
from tests.fixtures.make_statement import build_pdf


def test_twenty_five_pages_three_chunks() -> None:
    doc = build_pdf(pages=25)
    pdf_bytes = doc.tobytes()
    original_first = doc[0].get_text("text")
    doc.close()
    parts = split(pdf_bytes)
    assert len(parts) == 3
    counts = []
    first_pages = []
    for part in parts:
        opened = pymupdf.open(stream=part, filetype="pdf")
        counts.append(opened.page_count)
        first_pages.append(opened[0].get_text("text"))
        opened.close()
    assert counts == [10, 11, 6]
    assert first_pages[1] == original_first
    assert first_pages[2] == original_first
