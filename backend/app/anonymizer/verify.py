"""Leak scan: profile patterns, independent heuristics, expect-absent."""

from __future__ import annotations

import re
from dataclasses import dataclass

import pymupdf

from app.anonymizer.patterns import (
    AMOUNT_RE,
    DATE_RE,
    LONG_DIGITS_RE,
    iter_matches,
    luhn_ok,
)
from app.anonymizer.profile import Profile

ALLCAPS_RUN = re.compile(r"\b[A-ZÇĞİÖŞÜ]{2,}(?:\s+[A-ZÇĞİÖŞÜ]{2,}){1,2}\b")
AT_TOKEN = re.compile(r"\S+@\S+")


class LeakDetected(Exception):
    def __init__(self, findings: list[Finding]):
        self.findings = findings
        super().__init__(f"{len(findings)} leak finding(s)")


@dataclass
class Finding:
    kind: str
    page: int
    snippet: str


def _snippet(value: str) -> str:
    return value[:4] + "…"


def _is_amount_or_date(token: str, line: str) -> bool:
    if AMOUNT_RE.search(token) or DATE_RE.search(token):
        return True
    if AMOUNT_RE.search(line) and token in line:
        # 8+ digit chunks that are part of a formatted amount should not fire
        if AMOUNT_RE.search(line):
            stripped = token.replace(".", "").replace(",", "")
            if AMOUNT_RE.search(line) and stripped.isdigit() and len(token) < 8:
                return True
    return bool(DATE_RE.search(line) and token in DATE_RE.findall(line))


def leak_scan(
    pdf_bytes: bytes,
    profile: Profile,
    absent: list[str] | None = None,
) -> list[Finding]:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    findings: list[Finding] = []
    try:
        full_text_parts: list[str] = []
        for page_index, page in enumerate(doc):
            text = page.get_text("text")
            full_text_parts.append(text)
            for name in profile.mask.builtin:
                for match in iter_matches(name, text):
                    findings.append(Finding(name, page_index, _snippet(match.group(0))))
            for spec in profile.mask.regex:
                pattern = re.compile(spec.pattern, re.MULTILINE)
                for line in text.splitlines():
                    for match in pattern.finditer(line):
                        captured = match.group(spec.group) if spec.group else match.group(0)
                        if captured and captured.strip():
                            findings.append(Finding(spec.name, page_index, _snippet(captured)))
            for match in re.finditer(r"(?<!\d)(?:\d[\s-]?){13,16}(?!\d)", text):
                compact = re.sub(r"[\s-]", "", match.group(0))
                if compact.isdigit() and 13 <= len(compact) <= 16 and luhn_ok(compact):
                    findings.append(Finding("luhn", page_index, _snippet(compact)))
            for line in text.splitlines():
                stripped = line.strip()
                for match in LONG_DIGITS_RE.finditer(line):
                    token = match.group(0)
                    if DATE_RE.search(line) and token in "".join(DATE_RE.findall(line)):
                        continue
                    if AMOUNT_RE.search(line):
                        continue
                    if re.fullmatch(r"20\d{6}", token):
                        continue
                    findings.append(Finding("long_digits", page_index, _snippet(token)))
                if AMOUNT_RE.search(line):
                    continue
                words = stripped.split()
                if 2 <= len(words) <= 3 and all(re.fullmatch(r"[A-ZÇĞİÖŞÜ]{2,}", w) for w in words):
                    findings.append(Finding("name_heuristic", page_index, _snippet(stripped)))
            for match in AT_TOKEN.finditer(text):
                findings.append(Finding("email_heuristic", page_index, _snippet(match.group(0))))
        full = "\n".join(full_text_parts)
        for item in absent or []:
            if item and item in full:
                findings.append(Finding("expect_absent", -1, _snippet(item)))
    finally:
        doc.close()
    return findings
