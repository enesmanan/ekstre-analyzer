from datetime import date

from app.extractor.schema import Extraction, Txn
from app.extractor.validate import stated_total_from_text, validate


def _txn(day: int, amount: int, direction: str = "debit") -> Txn:
    return Txn(
        txn_date=date(2026, 9, day),
        description="x",
        amount_kurus=amount,
        direction=direction,  # type: ignore[arg-type]
        category="market",
        merchant_norm="X",
        is_installment=False,
        confidence=0.5,
    )


def _extraction(stated: int | None, txns: list[Txn]) -> Extraction:
    return Extraction(
        bank="generic",
        statement_type="account",
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        stated_total_debit_kurus=stated,
        transactions=txns,
    )


def test_total_mismatch_needs_review() -> None:
    report = validate(_extraction(100000, [_txn(1, 101500)]))
    assert report.status == "needs_review"
    assert "total_mismatch" in report.issues


def test_stated_zero_no_divide() -> None:
    report = validate(_extraction(0, [_txn(1, 100)]))
    assert report.status == "done"
    assert "no_stated_total" in report.issues
    assert "total_mismatch" not in report.issues


def test_date_out_of_period() -> None:
    report = validate(_extraction(100, [_txn(1, 100)]))
    late = _txn(1, 100)
    late.txn_date = date(2026, 11, 1)
    report = validate(_extraction(100, [late]))
    assert report.status == "needs_review"
    assert any(item.startswith("date_out_of_period:") for item in report.issues)


def test_credit_excluded_from_debit_total() -> None:
    report = validate(_extraction(1000, [_txn(1, 1000, "debit"), _txn(2, 5000, "credit")]))
    assert "total_mismatch" not in report.issues
    assert report.status == "done"


def test_regex_fallback_from_text() -> None:
    extraction = _extraction(None, [_txn(1, 123456)])
    text = "Ekstre Borcu: 1.234,56"
    assert stated_total_from_text(text) == 123456
    report = validate(extraction, pdf_text=text)
    assert extraction.stated_total_debit_kurus == 123456
    assert "total_mismatch" not in report.issues
