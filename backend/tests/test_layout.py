from pathlib import Path

import pymupdf

from app.anonymizer.layout import lines

SYNTHETIC = Path(__file__).resolve().parent / "fixtures" / "synthetic.pdf"


def test_iban_is_single_line_with_char_bboxes() -> None:
    doc = pymupdf.open(SYNTHETIC)
    page_lines = lines(doc[0])
    iban_lines = [line for line in page_lines if "TR33" in line.text]
    assert len(iban_lines) == 1
    line = iban_lines[0]
    assert len(line.char_bboxes) == len(line.text)
    doc.close()


def test_neighbour_line_survives_redaction() -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    font = pymupdf.Font("helv")
    for index, text in enumerate(["ALPHA LINE", "SECRET LINE", "GAMMA LINE"]):
        writer = pymupdf.TextWriter(page.rect)
        writer.append((50, 100 + index * 12), text, font=font, fontsize=10)
        writer.write_text(page)
    middle = [line for line in lines(page) if "SECRET" in line.text][0]
    rect = pymupdf.Rect(middle.char_bboxes[0])
    for box in middle.char_bboxes[1:]:
        rect.include_rect(box)
    rect = rect + (1, 1, -1, -1)
    page.add_redact_annot(rect, fill=(0, 0, 0))
    page.apply_redactions(
        images=pymupdf.PDF_REDACT_IMAGE_NONE,
        graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
        text=pymupdf.PDF_REDACT_TEXT_REMOVE,
    )
    text = page.get_text("text")
    assert "ALPHA" in text
    assert "GAMMA" in text
    assert "SECRET" not in text
    doc.close()
