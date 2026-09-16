"""Transaction list, category override, and category catalog."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_not_maintenance
from app.api.errors import ApiError
from app.db.models import Category, Transaction, User
from app.extractor.schema import CATEGORIES, Category as CategoryKey

router = APIRouter()


class TransactionOut(BaseModel):
    id: int
    statement_id: int
    txn_date: date
    description: str
    amount_kurus: int
    currency: str
    direction: str
    category: str
    user_override_category: str | None
    effective_category: str
    merchant_norm: str
    confidence: float
    is_installment: int
    installment_no: int | None
    installment_total: int | None


class TransactionListOut(BaseModel):
    items: list[TransactionOut]
    total: int


class CategoryOut(BaseModel):
    key: str
    label_tr: str
    sort: int


class PatchTransaction(BaseModel):
    category: CategoryKey | None


def to_out(row: Transaction) -> TransactionOut:
    effective = row.user_override_category or row.category
    return TransactionOut(
        id=row.id,
        statement_id=row.statement_id,
        txn_date=row.txn_date,
        description=row.description,
        amount_kurus=row.amount_kurus,
        currency=row.currency,
        direction=row.direction,
        category=row.category,
        user_override_category=row.user_override_category,
        effective_category=effective,
        merchant_norm=row.merchant_norm,
        confidence=row.confidence,
        is_installment=row.is_installment,
        installment_no=row.installment_no,
        installment_total=row.installment_total,
    )


def _owned_txn(db: Session, user: User, txn_id: int) -> Transaction:
    row = db.execute(
        select(Transaction).where(Transaction.id == txn_id, Transaction.user_id == user.id)
    ).scalar_one_or_none()
    if row is None:
        raise ApiError(404, "not_found", "Kayıt bulunamadı")
    return row


@router.get("/transactions")
def list_transactions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    from_: date | None = Query(None, alias="from"),
    to: date | None = None,
    category: str | None = None,
    direction: str | None = None,
    q: str | None = None,
    statement_id: int | None = None,
    page: int = 1,
    page_size: int = 50,
) -> TransactionListOut:
    if page < 1:
        raise ApiError(422, "validation_error", "page 1 veya daha büyük olmalı")
    if page_size < 1 or page_size > 200:
        raise ApiError(422, "validation_error", "page_size 1-200 arası olmalı")
    effective = func.coalesce(Transaction.user_override_category, Transaction.category)
    query = select(Transaction).where(Transaction.user_id == user.id)
    if from_ is not None:
        query = query.where(Transaction.txn_date >= from_)
    if to is not None:
        query = query.where(Transaction.txn_date <= to)
    if category is not None:
        query = query.where(effective == category)
    if direction is not None:
        query = query.where(Transaction.direction == direction)
    if q:
        query = query.where(Transaction.description.ilike(f"%{q}%"))
    if statement_id is not None:
        query = query.where(Transaction.statement_id == statement_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(Transaction.txn_date, Transaction.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return TransactionListOut(items=[to_out(row) for row in rows], total=int(total))


@router.patch("/transactions/{txn_id}", dependencies=[Depends(require_not_maintenance)])
def patch_transaction(
    txn_id: int,
    body: PatchTransaction,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TransactionOut:
    row = _owned_txn(db, user, txn_id)
    if body.category is not None and body.category not in CATEGORIES:
        raise ApiError(422, "validation_error", "Geçersiz kategori")
    row.user_override_category = body.category
    db.commit()
    db.refresh(row)
    return to_out(row)


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)) -> list[CategoryOut]:
    rows = db.scalars(select(Category).order_by(Category.sort, Category.key)).all()
    return [CategoryOut(key=row.key, label_tr=row.label_tr, sort=row.sort) for row in rows]
