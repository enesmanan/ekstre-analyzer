from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Statement, Transaction, User
from tests.conftest import upgrade_db

GEMINI = Path(__file__).resolve().parent / "fixtures" / "gemini"
SYNTHETIC = Path(__file__).resolve().parent / "fixtures" / "synthetic.pdf"


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from app.main import create_app

    monkeypatch.setattr(settings, "gemini_replay", str(GEMINI / "synthetic.json"))
    db = tmp_path / "t.db"
    upgrade_db(db)
    return TestClient(create_app(database_path=db))


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _seed_txns(engine) -> tuple[int, int, int, int, int]:
    with Session(engine) as session:
        other = User(
            id=2,
            email="other@local",
            password_hash="x",
            is_active=1,
            is_admin=0,
            created_at=_now(),
        )
        session.add(other)
        mine = Statement(
            user_id=1,
            uploaded_at=_now(),
            page_count=1,
            masked_sha256="seed-mine",
            status="done",
        )
        foreign = Statement(
            user_id=2,
            uploaded_at=_now(),
            page_count=1,
            masked_sha256="seed-other",
            status="done",
        )
        session.add_all([mine, foreign])
        session.flush()
        t1 = Transaction(
            statement_id=mine.id,
            user_id=1,
            txn_date=date(2026, 9, 1),
            description="Market A",
            amount_kurus=1000,
            currency="TRY",
            direction="debit",
            category="market",
            merchant_norm="MARKET A",
            confidence=0.9,
            is_installment=0,
            created_at=_now(),
        )
        t2 = Transaction(
            statement_id=mine.id,
            user_id=1,
            txn_date=date(2026, 9, 2),
            description="Kafe B",
            amount_kurus=2500,
            currency="TRY",
            direction="debit",
            category="restoran_kafe",
            merchant_norm="KAFE B",
            confidence=0.8,
            is_installment=0,
            created_at=_now(),
        )
        t3 = Transaction(
            statement_id=mine.id,
            user_id=1,
            txn_date=date(2026, 9, 3),
            description="Iade",
            amount_kurus=500,
            currency="TRY",
            direction="credit",
            category="diger",
            merchant_norm="IADE",
            confidence=0.7,
            is_installment=0,
            created_at=_now(),
        )
        foreign_txn = Transaction(
            statement_id=foreign.id,
            user_id=2,
            txn_date=date(2026, 9, 1),
            description="Secret",
            amount_kurus=9999,
            currency="TRY",
            direction="debit",
            category="market",
            merchant_norm="SECRET",
            confidence=0.9,
            is_installment=0,
            created_at=_now(),
        )
        session.add_all([t1, t2, t3, foreign_txn])
        session.commit()
        return mine.id, t1.id, foreign.id, foreign_txn.id, t2.id


def test_list_filters_and_pagination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        _seed_txns(client.app.state.engine)
        debit = client.get("/api/v1/transactions", params={"direction": "debit"})
        assert debit.status_code == 200
        body = debit.json()
        assert body["total"] == 2
        assert all(item["direction"] == "debit" for item in body["items"])
        searched = client.get("/api/v1/transactions", params={"q": "Kafe"})
        assert searched.json()["total"] == 1
        paged = client.get("/api/v1/transactions", params={"page": 1, "page_size": 1})
        assert len(paged.json()["items"]) == 1
        assert paged.json()["total"] == 3
        cats = client.get("/api/v1/categories")
        assert cats.status_code == 200
        assert any(item["key"] == "market" for item in cats.json())


def test_patch_override_and_invalid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        _mine_id, txn_id, _fid, _ftid, t2_id = _seed_txns(client.app.state.engine)
        patched = client.patch(f"/api/v1/transactions/{txn_id}", json={"category": "ulasim"})
        assert patched.status_code == 200
        body = patched.json()
        assert body["user_override_category"] == "ulasim"
        assert body["effective_category"] == "ulasim"
        assert body["category"] == "market"
        cleared = client.patch(f"/api/v1/transactions/{txn_id}", json={"category": None})
        assert cleared.json()["effective_category"] == "market"
        assert cleared.json()["user_override_category"] is None
        bad = client.patch(f"/api/v1/transactions/{t2_id}", json={"category": "not-a-category"})
        assert bad.status_code == 422
        assert bad.json()["error"]["code"] == "validation_error"


def test_foreign_records_are_404(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        _mine, _tid, foreign_sid, foreign_tid, _t2 = _seed_txns(client.app.state.engine)
        assert client.get(f"/api/v1/statements/{foreign_sid}").status_code == 404
        assert client.get(f"/api/v1/statements/{foreign_sid}/preview.png").json()["error"]["code"] == "not_found"
        assert client.delete(f"/api/v1/statements/{foreign_sid}").status_code == 404
        patched = client.patch(f"/api/v1/transactions/{foreign_tid}", json={"category": "market"})
        assert patched.status_code == 404
        assert patched.json()["error"]["code"] == "not_found"
        listed = client.get("/api/v1/transactions")
        assert all(item["id"] != foreign_tid for item in listed.json()["items"])
