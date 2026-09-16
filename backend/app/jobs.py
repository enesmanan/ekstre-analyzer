"""In-memory PDF job store and background statement processing."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pymupdf
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from app.anonymizer.masker import PasswordRequired, ScannedPdf, WrongPassword, mask
from app.anonymizer.profile import load_all_profiles, profile_by_bank
from app.anonymizer.sanitize import UnsafePdf
from app.anonymizer.verify import LeakDetected
from app.config import settings
from app.db.models import Statement
from app.extractor.client import GeminiClient, RecordedClient
from app.extractor.service import DuplicateStatement, ExtractFailed, extract_statement

PREVIEW_TTL = timedelta(minutes=10)
PROCESS_LIMIT = 2


@dataclass
class PdfEntry:
    original: bytes | None
    password: str | None
    profile_name: str | None
    masked: bytes | None = None
    expires_at: datetime | None = None


class JobStore:
    def __init__(self) -> None:
        self.entries: dict[int, PdfEntry] = {}
        self.semaphore = asyncio.Semaphore(PROCESS_LIMIT)


def make_llm_client() -> GeminiClient | RecordedClient:
    if settings.gemini_replay:
        return RecordedClient(Path(settings.gemini_replay))
    return GeminiClient(settings)


def mark_restart(engine: Engine) -> None:
    with Session(engine) as session:
        queued = session.scalars(
            select(Statement).where(Statement.status.in_(("queued", "masking")))
        )
        for row in queued:
            row.status = "mask_failed"
            row.error = "restart"
        extracting = session.scalars(select(Statement).where(Statement.status == "extracting"))
        for row in extracting:
            row.status = "extract_failed"
            row.error = "restart"
        session.commit()


def expire_preview(entry: PdfEntry) -> bool:
    if entry.masked is None or entry.expires_at is None:
        return False
    now = datetime.now(UTC).replace(tzinfo=None)
    if entry.expires_at <= now:
        entry.masked = None
        return True
    return False


def render_preview_png(pdf_bytes: bytes) -> bytes:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        pix = doc[0].get_pixmap(dpi=100)
        return pix.tobytes("png")
    finally:
        doc.close()


def _fail(session: Session, row: Statement, code: str) -> None:
    row.status = "mask_failed"
    row.error = code
    session.commit()


def _fail_id(factory: sessionmaker[Session], statement_id: int, code: str) -> None:
    with factory() as session:
        row = session.get(Statement, statement_id)
        if row is None:
            return
        _fail(session, row, code)


async def process_statement(app: object, statement_id: int) -> None:
    store: JobStore = app.state.jobs  # type: ignore[attr-defined]
    async with store.semaphore:
        factory: sessionmaker[Session] = app.state.session_factory  # type: ignore[attr-defined]
        with factory() as session:
            row = session.get(Statement, statement_id)
            if row is None:
                return
            entry = store.entries.get(statement_id)
            if entry is None or entry.original is None:
                _fail(session, row, "restart")
                return
            row.status = "masking"
            session.commit()
            original = entry.original
            password = entry.password
            profile_name = entry.profile_name
            orig_key = hashlib.sha256(original).hexdigest()
            entry.original = None
            entry.password = None

        profiles = load_all_profiles()
        profile = profile_by_bank(profile_name, profiles) if profile_name else profiles[0]

        def _run_mask() -> object:
            return mask(original, profile, password)

        try:
            mask_result = await run_in_threadpool(_run_mask)
        except LeakDetected:
            _fail_id(factory, statement_id, "leak_detected")
            return
        except UnsafePdf:
            _fail_id(factory, statement_id, "unsafe_pdf")
            return
        except ScannedPdf:
            _fail_id(factory, statement_id, "scanned_pdf")
            return
        except PasswordRequired:
            _fail_id(factory, statement_id, "password_required")
            return
        except WrongPassword:
            _fail_id(factory, statement_id, "wrong_password")
            return
        except Exception:
            _fail_id(factory, statement_id, "mask_failed")
            return

        entry = store.entries.get(statement_id)
        if entry is not None:
            entry.masked = mask_result.pdf_bytes
            entry.expires_at = datetime.now(UTC).replace(tzinfo=None) + PREVIEW_TTL

        with factory() as session:
            try:
                session.execute(
                    update(Statement)
                    .where(Statement.id == statement_id)
                    .values(
                        masked_sha256=orig_key,
                        page_count=mask_result.page_count,
                        redaction_count=mask_result.redaction_count,
                        profile=mask_result.bank,
                        bank=mask_result.bank,
                        mask_warnings_json=json.dumps(mask_result.warnings, ensure_ascii=False),
                    )
                )
                session.commit()
            except IntegrityError:
                session.rollback()
                session.execute(
                    update(Statement)
                    .where(Statement.id == statement_id)
                    .values(status="mask_failed", error="duplicate_statement")
                )
                session.commit()
                return

            row = session.get(Statement, statement_id)
            assert row is not None
            row.status = "extracting"
            session.commit()

            client = make_llm_client()
            try:
                await extract_statement(row, mask_result, session, client)
            except DuplicateStatement:
                row.status = "mask_failed"
                row.error = "duplicate_statement"
                session.commit()
                return
            except ExtractFailed:
                return
            row.masked_sha256 = orig_key
            session.commit()
