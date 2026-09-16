"""Reject unsafe PDF features before masking."""

from __future__ import annotations

import pymupdf


class UnsafePdf(Exception):
    """PDF contains JavaScript, attachments, embedded files, or form fields."""


def check(doc: pymupdf.Document) -> None:
    if doc.embfile_count() > 0:
        raise UnsafePdf("embedded file")
    cat = doc.pdf_catalog()
    js_names = doc.xref_get_key(cat, "Names/JavaScript")
    if js_names[0] != "null":
        raise UnsafePdf("javascript")
    if doc.xref_get_key(cat, "OpenAction/S")[1] == "/JavaScript":
        raise UnsafePdf("javascript")
    for xref in range(1, doc.xref_length()):
        if doc.xref_get_key(xref, "S")[1] == "/JavaScript":
            raise UnsafePdf("javascript")
    if doc.is_form_pdf:
        raise UnsafePdf("form")
    for page in doc:
        annots = page.annots(types=[pymupdf.PDF_ANNOT_FILE_ATTACHMENT])
        if annots is None:
            continue
        if any(True for _ in annots):
            raise UnsafePdf("file attachment")
