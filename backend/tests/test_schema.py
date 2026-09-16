from datetime import date

import pytest
from pydantic import ValidationError

from app.extractor.schema import CATEGORIES, Extraction, Txn, gemini_json_schema


def test_json_schema_produced() -> None:
    schema = Extraction.model_json_schema()
    assert "properties" in schema
    cleaned = gemini_json_schema(Extraction)
    assert "title" not in cleaned


def test_bad_category_rejected() -> None:
    with pytest.raises(ValidationError):
        Txn(
            txn_date=date(2026, 9, 1),
            description="x",
            amount_kurus=100,
            direction="debit",
            category="not_a_category",  # type: ignore[arg-type]
            merchant_norm="X",
            is_installment=False,
            confidence=0.5,
        )


def test_invalid_date_rejected() -> None:
    with pytest.raises(ValidationError):
        Extraction.model_validate(
            {
                "bank": "generic",
                "statement_type": "account",
                "period_start": "2026-13-40",
                "period_end": "2026-09-30",
                "stated_total_debit_kurus": None,
                "transactions": [],
            }
        )


def test_eighteen_categories() -> None:
    assert len(CATEGORIES) == 18
