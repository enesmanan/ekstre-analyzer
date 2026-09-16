"""Line model from PyMuPDF rawdict character bboxes."""

from __future__ import annotations

from dataclasses import dataclass

import pymupdf

pymupdf.TOOLS.set_small_glyph_heights(True)


@dataclass
class Line:
    text: str
    spans: list[tuple[str, pymupdf.Rect]]
    char_bboxes: list[pymupdf.Rect]


def lines(page: pymupdf.Page) -> list[Line]:
    raw = page.get_text("rawdict")
    result: list[Line] = []
    for block in raw.get("blocks", []):
        if block.get("type", 0) != 0:
            continue
        for line in block.get("lines", []):
            span_pairs: list[tuple[str, pymupdf.Rect]] = []
            char_bboxes: list[pymupdf.Rect] = []
            texts: list[str] = []
            for span in line.get("spans", []):
                chars = span.get("chars") or []
                span_text = "".join(c["c"] for c in chars)
                if chars:
                    rect = pymupdf.Rect(chars[0]["bbox"])
                    for char in chars[1:]:
                        rect.include_rect(char["bbox"])
                    for char in chars:
                        char_bboxes.append(pymupdf.Rect(char["bbox"]))
                else:
                    rect = pymupdf.Rect(span.get("bbox", (0, 0, 0, 0)))
                span_pairs.append((span_text, rect))
                texts.append(span_text)
            result.append(Line(text="".join(texts), spans=span_pairs, char_bboxes=char_bboxes))
    return result
