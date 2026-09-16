import pymupdf
import pytest

from app.anonymizer.sanitize import UnsafePdf, check


def _bytes(doc: pymupdf.Document) -> bytes:
    data = doc.tobytes()
    doc.close()
    return data


def test_embedded_file_rejected() -> None:
    doc = pymupdf.open()
    doc.new_page()
    doc.embfile_add("secret.txt", b"hidden")
    data = _bytes(doc)
    opened = pymupdf.open(stream=data, filetype="pdf")
    with pytest.raises(UnsafePdf):
        check(opened)
    opened.close()


def test_javascript_openaction_rejected() -> None:
    doc = pymupdf.open()
    doc.new_page()
    xref = doc.get_new_xref()
    doc.update_object(xref, "<< /Type /Action /S /JavaScript /JS (app.alert('x');) >>")
    doc.xref_set_key(doc.pdf_catalog(), "OpenAction", f"{xref} 0 R")
    data = _bytes(doc)
    opened = pymupdf.open(stream=data, filetype="pdf")
    with pytest.raises(UnsafePdf):
        check(opened)
    opened.close()


def test_goto_openaction_allowed() -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    xref = doc.get_new_xref()
    doc.update_object(xref, "<< /Type /Action /S /GoTo /D [ 0 /Fit ] >>")
    doc.xref_set_key(doc.pdf_catalog(), "OpenAction", f"{xref} 0 R")
    data = _bytes(doc)
    opened = pymupdf.open(stream=data, filetype="pdf")
    check(opened)
    opened.close()


def test_form_rejected() -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    widget = pymupdf.Widget()
    widget.field_name = "field"
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.rect = pymupdf.Rect(50, 50, 200, 80)
    page.add_widget(widget)
    data = _bytes(doc)
    opened = pymupdf.open(stream=data, filetype="pdf")
    with pytest.raises(UnsafePdf):
        check(opened)
    opened.close()
