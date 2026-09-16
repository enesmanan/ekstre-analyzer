from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Transaction
from app.db.session import make_engine
from tests.conftest import upgrade_db


def test_wal_and_foreign_keys(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    upgrade_db(db)
    engine = make_engine(db)
    with engine.connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        assert str(mode).lower() == "wal"
    with Session(engine) as session:
        row = Transaction(
            statement_id=999,
            user_id=1,
            txn_date=__import__("datetime").date(2026, 9, 1),
            description="x",
            amount_kurus=100,
            direction="debit",
            category="market",
            merchant_norm="X",
            confidence=0.5,
            created_at=__import__("datetime").datetime(2026, 9, 1),
        )
        session.add(row)
        try:
            session.commit()
            raise AssertionError("expected IntegrityError")
        except IntegrityError:
            session.rollback()
