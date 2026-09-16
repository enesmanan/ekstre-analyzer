"""Statement upload, status, preview, and delete."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pymupdf
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.anonymizer.profile import detect_profile, load_all_profiles, profile_by_bank
from app.anonymizer.sanitize import UnsafePdf, check
from app.api.deps import get_current_user, get_db, require_not_maintenance
from app.api.errors import ApiError
from app.db.models import Statement, User
from app.api.body_limit import MAX_BODY_SIZE
from app.jobs import PdfEntry, expire_preview, process_statement, render_preview_png

router = APIRouter()
MAX_PAGES = 60
BUSY_QUEUED = 4


class StatementOut(BaseModel):
    id: int
    status: str
    error: str | None
    issues: list[Any]
    mask_warnings: list[Any]
    page_count: int
    bank: str | None
    profile: str | None
    statement_type: str | None
    period_start: str | None
    period_end: str | None
    redaction_count: int
    uploaded_at: datetime
    input_tokens: int
    output_tokens: int
    thought_tokens: int
    cost_usd_micro: int


def _parse_json_list(raw: str | None) -> list[Any]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def to_out(row: Statement) -> StatementOut:
    return StatementOut(
        id=row.id,
        status=row.status,
        error=row.error,
        issues=_parse_json_list(row.validation_issues_json),
        mask_warnings=_parse_json_list(row.mask_warnings_json),
        page_count=row.page_count,
        bank=row.bank,
        profile=row.profile,
        statement_type=row.statement_type,
        period_start=row.period_start.isoformat() if row.period_start else None,
        period_end=row.period_end.isoformat() if row.period_end else None,
        redaction_count=row.redaction_count,
        uploaded_at=row.uploaded_at,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        thought_tokens=row.thought_tokens,
        cost_usd_micro=row.cost_usd_micro,
    )


def _inspect(
    pdf_bytes: bytes, password: str | None, profile_header: str | None
) -> str:
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ApiError(400, "unsafe_pdf", "PDF değil")
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        if not doc.is_pdf:
            raise ApiError(400, "unsafe_pdf", "PDF değil")
        if doc.needs_pass:
            if not password:
                raise ApiError(400, "password_required", "PDF şifreli")
            if doc.authenticate(password) == 0:
                raise ApiError(400, "wrong_password", "PDF şifresi yanlış")
        if doc.page_count > MAX_PAGES:
            raise ApiError(400, "too_many_pages", "En fazla 60 sayfa")
        try:
            check(doc)
        except UnsafePdf as exc:
            raise ApiError(400, "unsafe_pdf", "Güvenli olmayan PDF") from exc
        first = doc[0].get_text("text") if doc.page_count else ""
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(400, "unsafe_pdf", "PDF değil") from exc
    finally:
        doc.close()
    profiles = load_all_profiles()
    if profile_header:
        try:
            profile = profile_by_bank(profile_header, profiles)
        except KeyError as exc:
            raise ApiError(400, "validation_error", "Bilinmeyen profil") from exc
    else:
        profile, _warnings = detect_profile(first, profiles)
    return profile.bank


def _owned(db: Session, user: User, statement_id: int) -> Statement:
    row = db.execute(
        select(Statement).where(Statement.id == statement_id, Statement.user_id == user.id)
    ).scalar_one_or_none()
    if row is None:
        raise ApiError(404, "not_found", "Kayıt bulunamadı")
    return row


@router.post("/statements", status_code=202, dependencies=[Depends(require_not_maintenance)])
async def upload_statement(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, int]:
    queued = db.scalar(
        select(func.count())
        .select_from(Statement)
        .where(Statement.user_id == user.id, Statement.status == "queued")
    )
    if queued is not None and int(queued) >= BUSY_QUEUED:
        raise ApiError(503, "busy", "Çok fazla bekleyen iş")

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_BODY_SIZE:
                raise ApiError(413, "too_large", "PDF 15 MiB sınırını aşıyor")
        except ValueError:
            pass
    pdf_bytes = await request.body()
    if len(pdf_bytes) > MAX_BODY_SIZE:
        raise ApiError(413, "too_large", "PDF 15 MiB sınırını aşıyor")
    password = request.headers.get("X-Statement-Password") or None
    profile_header = request.headers.get("X-Statement-Profile") or None
    bank = await run_in_threadpool(_inspect, pdf_bytes, password, profile_header)

    async with request.app.state.write_lock:
        queued = db.scalar(
            select(func.count())
            .select_from(Statement)
            .where(Statement.user_id == user.id, Statement.status == "queued")
        )
        if queued is not None and int(queued) >= BUSY_QUEUED:
            raise ApiError(503, "busy", "Çok fazla bekleyen iş")
        row = Statement(
            user_id=user.id,
            profile=bank,
            uploaded_at=datetime.now(UTC).replace(tzinfo=None),
            page_count=0,
            masked_sha256=f"pending:{uuid4()}",
            status="queued",
        )
        db.add(row)
        db.commit()
        db.refresh(row)

    request.app.state.jobs.entries[row.id] = PdfEntry(
        original=pdf_bytes,
        password=password,
        profile_name=bank,
    )
    background_tasks.add_task(process_statement, request.app, row.id)
    return {"id": row.id}


@router.get("/statements")
def list_statements(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[StatementOut]:
    rows = db.scalars(
        select(Statement)
        .where(Statement.user_id == user.id)
        .order_by(Statement.uploaded_at.desc())
    ).all()
    return [to_out(row) for row in rows]


@router.get("/statements/{statement_id}")
def get_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StatementOut:
    return to_out(_owned(db, user, statement_id))


@router.get("/statements/{statement_id}/preview.png")
def preview_statement(
    statement_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    _owned(db, user, statement_id)
    entry = request.app.state.jobs.entries.get(statement_id)
    if entry is None:
        raise ApiError(404, "not_found", "Önizleme yok")
    if expire_preview(entry):
        raise ApiError(404, "preview_expired", "Önizleme süresi doldu")
    if entry.masked is None:
        raise ApiError(404, "not_found", "Önizleme yok")
    png = render_preview_png(entry.masked)
    return Response(content=png, media_type="image/png")


@router.delete(
    "/statements/{statement_id}",
    status_code=204,
    dependencies=[Depends(require_not_maintenance)],
)
def delete_statement(
    statement_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    row = _owned(db, user, statement_id)
    db.delete(row)
    db.commit()
    request.app.state.jobs.entries.pop(statement_id, None)
    return Response(status_code=204)
