"""Split a masked statement PDF into Gemini-sized parts in memory."""

from __future__ import annotations

import pymupdf


def split(
    pdf_bytes: bytes,
    single_request_max: int = 15,
    chunk_pages: int = 10,
    context_first_page: bool = True,
) -> list[bytes]:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        page_count = doc.page_count
        if page_count <= single_request_max:
            return [doc.tobytes(garbage=3, deflate=True)]

        parts: list[bytes] = []
        start = 0
        chunk_index = 0
        while start < page_count:
            end = min(start + chunk_pages, page_count) - 1
            part = pymupdf.open()
            if chunk_index > 0 and context_first_page:
                part.insert_pdf(doc, from_page=0, to_page=0)
            part.insert_pdf(doc, from_page=start, to_page=end)
            parts.append(part.tobytes(garbage=3, deflate=True))
            part.close()
            start = end + 1
            chunk_index += 1
        return parts
    finally:
        doc.close()
