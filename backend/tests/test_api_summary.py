from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Statement, Transaction
from tests.conftest import upgrade_db

GEMINI = Path(__file__).resolve().parent / "fixtures" / "gemini"


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from app.main import create_app

    monkeypatch.setattr(settings, "gemini_replay", str(GEMINI / "synthetic.json"))
    db = tmp_path / "t.db"
    upgrade_db(db)
    return TestClient(create_app(database_path=db))


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _seed(engine) -> int:
    with Session(engine) as session:
        statement = Statement(
            user_id=1,
            uploaded_at=_now(),
            page_count=1,
            masked_sha256="sum-seed",
            status="done",
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
        )
        session.add(statement)
        session.flush()
        rows = [
            Transaction(
                statement_id=statement.id,
                user_id=1,
                txn_date=date(2026, 9, 1),
                description="Market",
                amount_kurus=1000,
                currency="TRY",
                direction="debit",
                category="market",
                merchant_norm="MARKET",
                confidence=0.9,
                is_installment=0,
                created_at=_now(),
            ),
            Transaction(
                statement_id=statement.id,
                user_id=1,
                txn_date=date(2026, 9, 2),
                description="Kafe",
                amount_kurus=4000,
                currency="TRY",
                direction="debit",
                category="restoran_kafe",
                merchant_norm="KAFE",
                confidence=0.8,
                is_installment=0,
                user_override_category="market",
                created_at=_now(),
            ),
            Transaction(
                statement_id=statement.id,
                user_id=1,
                txn_date=date(2026, 8, 30),
                description="Onceki",
                amount_kurus=700,
                currency="TRY",
                direction="debit",
                category="market",
                merchant_norm="ONCEKI",
                confidence=0.9,
                is_installment=0,
                created_at=_now(),
            ),
            Transaction(
                statement_id=statement.id,
                user_id=1,
                txn_date=date(2026, 9, 5),
                description="Iade",
                amount_kurus=250,
                currency="TRY",
                direction="credit",
                category="diger",
                merchant_norm="IADE",
                confidence=0.7,
                is_installment=0,
                created_at=_now(),
            ),
        ]
        session.add_all(rows)
        session.commit()
        return statement.id


def test_summary_override_prev_daily_top(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        _seed(client.app.state.engine)
        missing = client.get("/api/v1/summary")
        assert missing.status_code == 422
        assert missing.json()["error"]["code"] == "validation_error"
        response = client.get("/api/v1/summary", params={"from": "2026-09-01", "to": "2026-09-03"})
        assert response.status_code == 200
        body = response.json()
        assert body["total_debit_kurus"] == 5000
        assert body["total_credit_kurus"] == 0
        assert isinstance(body["total_debit_kurus"], int)
        buckets = {item["key"]: item for item in body["by_category"]}
        assert buckets["market"]["kurus"] == 5000
        assert buckets["market"]["count"] == 2
        assert "restoran_kafe" not in buckets
        assert body["prev_total_debit_kurus"] == 700
        daily = {item["date"]: item["debit_kurus"] for item in body["daily"]}
        assert daily["2026-09-01"] == 1000
        assert daily["2026-09-02"] == 4000
        assert daily["2026-09-03"] == 0
        assert body["top"][0]["amount_kurus"] == 4000
        assert body["top"][0]["effective_category"] == "market"
