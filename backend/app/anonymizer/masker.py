"""Mask a statement PDF in memory with PyMuPDF redactions."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

import pymupdf

from app.anonymizer.layout import lines
from app.anonymizer.patterns import iter_matches
from app.anonymizer.profile import MaskRegex, Profile, extra_term_pattern
from app.anonymizer.sanitize import check
from app.anonymizer.verify import LeakDetected, leak_scan


class PasswordRequired(Exception):
    """Encrypted PDF and no password was provided."""


class WrongPassword(Exception):
    """Encrypted PDF password was rejected."""


class ScannedPdf(Exception):
    def __init__(self, message: str = "Taranmış ekstre desteklenmiyor"):
        super().__init__(message)


@dataclass
class MaskResult:
    pdf_bytes: bytes
    bank: str
    page_count: int
    redaction_count: int
    warnings: list[str] = field(default_factory=list)
    masked_sha256: str = ""


def _overlaps(start: int, end: int, kept: list[tuple[int, int]]) -> bool:
    for keep_start, keep_end in kept:
        if start < keep_end and end > keep_start:
            return True
    return False


def _ranges_for_line(text: str, profile: Profile, extras: list[MaskRegex]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for name in profile.mask.builtin:
        for match in iter_matches(name, text):
            ranges.append((match.start(), match.end()))
    for spec in profile.mask.regex:
        pattern = re.compile(spec.pattern, re.MULTILINE)
        for match in pattern.finditer(text):
            if spec.group:
                ranges.append((match.start(spec.group), match.end(spec.group)))
            else:
                ranges.append((match.start(), match.end()))
    for spec in extras:
        pattern = re.compile(spec.pattern, re.MULTILINE | re.IGNORECASE)
        for match in pattern.finditer(text):
            if spec.group:
                ranges.append((match.start(spec.group), match.end(spec.group)))
            else:
                ranges.append((match.start(), match.end()))
    return ranges


def mask(
    pdf_bytes: bytes,
    profile: Profile,
    password: str | None = None,
    extra_terms: list[str] | None = None,
) -> MaskResult:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        if not doc.is_pdf:
            raise ValueError("not a pdf")
        if doc.needs_pass:
            if not password:
                raise PasswordRequired()
            if doc.authenticate(password) == 0:
                raise WrongPassword()
        check(doc)
        word_count = 0
        for index in range(min(2, doc.page_count)):
            word_count += len(doc[index].get_text("text").split())
        if word_count < 20:
            raise ScannedPdf()

        extras = [
            MaskRegex(name="extra_term", pattern=extra_term_pattern(term), group=0)
            for term in extra_terms or []
        ]
        redaction_count = 0
        pad = profile.padding_pt
        for page in doc:
            for line in lines(page):
                kept = [
                    (match.start(), match.end())
                    for keep in profile.keep
                    for match in re.finditer(keep, line.text, re.MULTILINE)
                ]
                for start, end in _ranges_for_line(line.text, profile, extras):
                    if start >= end or _overlaps(start, end, kept):
                        continue
                    boxes = line.char_bboxes[start:end]
                    if not boxes:
                        continue
                    rect = pymupdf.Rect(boxes[0])
                    for box in boxes[1:]:
                        rect.include_rect(box)
                    rect = rect + (pad, pad, -pad, -pad)
                    page.add_redact_annot(rect, fill=(0, 0, 0))
                    redaction_count += 1
            page.apply_redactions(
                images=pymupdf.PDF_REDACT_IMAGE_NONE,
                graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
                text=pymupdf.PDF_REDACT_TEXT_REMOVE,
            )
        doc.scrub(
            metadata=True,
            xml_metadata=True,
            javascript=True,
            embedded_files=True,
            attached_files=True,
            hidden_text=True,
            remove_links=True,
            redactions=False,
        )
        out = doc.tobytes(garbage=3, deflate=True)
        page_count = doc.page_count
        bank = profile.bank
    finally:
        doc.close()
        password = None

    findings = leak_scan(out, profile)
    if findings:
        raise LeakDetected(findings)
    return MaskResult(
        pdf_bytes=out,
        bank=bank,
        page_count=page_count,
        redaction_count=redaction_count,
        masked_sha256=hashlib.sha256(out).hexdigest(),
    )
