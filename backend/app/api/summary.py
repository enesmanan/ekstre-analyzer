"""Period summary: totals, categories, daily series, top transactions."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.errors import ApiError
from app.db.models import Category, Transaction, User

router = APIRouter()


class CategoryBucket(BaseModel):
    key: str
    label_tr: str
    kurus: int
    count: int


class DailyPoint(BaseModel):
    date: date
    debit_kurus: int


class TopItem(BaseModel):
    id: int
    txn_date: date
    merchant_norm: str
    amount_kurus: int
    effective_category: str


class SummaryOut(BaseModel):
    total_debit_kurus: int
    total_credit_kurus: int
    prev_total_debit_kurus: int
    by_category: list[CategoryBucket]
    daily: list[DailyPoint]
    top: list[TopItem]


def _period_totals(
    db: Session, user_id: int, start: date, end: date
) -> tuple[int, int]:
    debit = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount_kurus), 0)).where(
            Transaction.user_id == user_id,
            Transaction.txn_date >= start,
            Transaction.txn_date <= end,
            Transaction.direction == "debit",
        )
    )
    credit = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount_kurus), 0)).where(
            Transaction.user_id == user_id,
            Transaction.txn_date >= start,
            Transaction.txn_date <= end,
            Transaction.direction == "credit",
        )
    )
    return int(debit or 0), int(credit or 0)


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
) -> SummaryOut:
    if to < from_:
        raise ApiError(422, "validation_error", "to, from tarihinden küçük olamaz")
    total_debit, total_credit = _period_totals(db, user.id, from_, to)
    span = (to - from_).days + 1
    prev_to = from_ - timedelta(days=1)
    prev_from = prev_to - timedelta(days=span - 1)
    prev_debit, _prev_credit = _period_totals(db, user.id, prev_from, prev_to)

    effective = func.coalesce(Transaction.user_override_category, Transaction.category)
    cat_rows = db.execute(
        select(effective, func.sum(Transaction.amount_kurus), func.count())
        .where(
            Transaction.user_id == user.id,
            Transaction.txn_date >= from_,
            Transaction.txn_date <= to,
            Transaction.direction == "debit",
        )
        .group_by(effective)
    ).all()
    labels = {row.key: row.label_tr for row in db.scalars(select(Category)).all()}
    by_category = [
        CategoryBucket(
            key=key,
            label_tr=labels.get(key, key),
            kurus=int(kurus or 0),
            count=int(count),
        )
        for key, kurus, count in cat_rows
        if key is not None
    ]

    daily_map = {
        row[0]: int(row[1] or 0)
        for row in db.execute(
            select(Transaction.txn_date, func.sum(Transaction.amount_kurus)).where(
                Transaction.user_id == user.id,
                Transaction.txn_date >= from_,
                Transaction.txn_date <= to,
                Transaction.direction == "debit",
            ).group_by(Transaction.txn_date)
        ).all()
    }
    daily = []
    cursor = from_
    while cursor <= to:
        daily.append(DailyPoint(date=cursor, debit_kurus=daily_map.get(cursor, 0)))
        cursor += timedelta(days=1)

    top_rows = db.scalars(
        select(Transaction)
        .where(
            Transaction.user_id == user.id,
            Transaction.txn_date >= from_,
            Transaction.txn_date <= to,
        )
        .order_by(Transaction.amount_kurus.desc(), Transaction.id)
        .limit(10)
    ).all()
    top = [
        TopItem(
            id=row.id,
            txn_date=row.txn_date,
            merchant_norm=row.merchant_norm,
            amount_kurus=row.amount_kurus,
            effective_category=row.user_override_category or row.category,
        )
        for row in top_rows
    ]
    return SummaryOut(
        total_debit_kurus=total_debit,
        total_credit_kurus=total_credit,
        prev_total_debit_kurus=prev_debit,
        by_category=by_category,
        daily=daily,
        top=top,
    )
