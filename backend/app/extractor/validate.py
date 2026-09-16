"""Post-LLM checks: stated total, period dates. Dedupe is applied in service.py."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta

from app.extractor.schema import Extraction

STATED_TOTAL_RE = re.compile(
    r"(Toplam Harcama|Dönem Borcu|Toplam Borç|Ekstre Borcu)\s*:?\s*"
    r"(\d{1,3}(?:\.\d{3})*,\d{2})"
)


@dataclass
class ValidationReport:
    status: str
    issues: list[str] = field(default_factory=list)


def parse_tr_amount_kurus(raw: str) -> int:
    whole, _, frac = raw.strip().partition(",")
    whole = whole.replace(".", "")
    frac = (frac + "00")[:2]
    return int(whole) * 100 + int(frac)


def stated_total_from_text(pdf_text: str) -> int | None:
    match = STATED_TOTAL_RE.search(pdf_text)
    if not match:
        return None
    return parse_tr_amount_kurus(match.group(2))


def validate(
    extraction: Extraction,
    pdf_text: str | None = None,
    extra_issues: list[str] | None = None,
) -> ValidationReport:
    issues = list(extra_issues or [])
    status = "done"

    stated = extraction.stated_total_debit_kurus
    if stated is None and pdf_text:
        stated = stated_total_from_text(pdf_text)
        if stated is not None:
            extraction.stated_total_debit_kurus = stated

    debit_total = sum(
        txn.amount_kurus for txn in extraction.transactions if txn.direction == "debit"
    )

    if stated is None or stated == 0:
        issues.append("no_stated_total")
    elif stated > 0:
        delta = abs(debit_total - stated) / stated
        if delta > 0.01:
            status = "needs_review"
            issues.append("total_mismatch")

    lo = extraction.period_start - timedelta(days=5)
    hi = extraction.period_end + timedelta(days=5)
    for index, txn in enumerate(extraction.transactions):
        if txn.txn_date < lo or txn.txn_date > hi:
            status = "needs_review"
            issues.append(f"date_out_of_period:{index}")

    return ValidationReport(status=status, issues=issues)
