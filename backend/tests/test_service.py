from __future__ import annotations

import hashlib
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.anonymizer.masker import MaskResult
from app.db.models import Statement
from app.db.session import make_engine
from app.extractor.client import RecordedClient
from app.extractor.service import DuplicateStatement, ExtractFailed, extract_statement
from tests.conftest import upgrade_db
from tests.fixtures.make_statement import build_pdf

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "gemini"


class FailIfCalled:
    async def extract_chunk(self, pdf_b64: str, chunk_index: int):  # noqa: ANN201
        raise AssertionError("LLM must not be called")


def _mask_result(pdf_bytes: bytes, bank: str = "generic") -> MaskResult:
    return MaskResult(
        pdf_bytes=pdf_bytes,
        bank=bank,
        page_count=3,
        redaction_count=0,
        warnings=[],
        masked_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
    )


def _row(session: Session, mask_result: MaskResult, status: str = "extracting") -> Statement:
    row = Statement(
        user_id=1,
        profile=mask_result.bank,
        uploaded_at=datetime.now(UTC).replace(tzinfo=None),
        page_count=mask_result.page_count,
        redaction_count=0,
        masked_sha256=mask_result.masked_sha256,
        status=status,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@pytest.mark.asyncio
async def test_extract_records_tokens(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    upgrade_db(db)
    engine = make_engine(db)
    pdf_bytes = (Path(__file__).resolve().parent / "fixtures" / "synthetic.pdf").read_bytes()
    mask_result = _mask_result(pdf_bytes)
    client = RecordedClient(FIXTURES / "synthetic.json")
    with Session(engine) as session:
        row = _row(session, mask_result)
        result = await extract_statement(row, mask_result, session, client)
        assert result.status == "done"
        assert result.input_tokens == 1200
        assert result.output_tokens == 400
        assert result.thought_tokens == 80
        assert result.cost_usd_micro > 0
        assert result.transactions


@pytest.mark.asyncio
async def test_chunk_dedupe_and_same_chunk_kept(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    upgrade_db(db)
    engine = make_engine(db)
    doc = build_pdf(pages=16)
    pdf_bytes = doc.tobytes()
    doc.close()
    mask_result = MaskResult(
        pdf_bytes=pdf_bytes,
        bank="generic",
        page_count=16,
        redaction_count=0,
        warnings=[],
        masked_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
    )
    client = RecordedClient(FIXTURES / "chunks.json")
    with Session(engine) as session:
        row = _row(session, mask_result)
        result = await extract_statement(row, mask_result, session, client)
        descriptions = [txn.description for txn in result.transactions]
        assert descriptions.count("Coffee") == 2
        assert "Market A" in descriptions
        assert "Market B" in descriptions
        issues = result.validation_issues_json or ""
        assert "chunk_dup:" in issues


@pytest.mark.asyncio
async def test_duplicate_does_not_call_client(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    upgrade_db(db)
    engine = make_engine(db)
    pdf_bytes = b"%PDF-1.4 duplicate-test"
    mask_result = _mask_result(pdf_bytes)
    with Session(engine) as session:
        first = _row(session, mask_result, status="done")
        with pytest.raises(DuplicateStatement):
            await extract_statement(first, mask_result, session, FailIfCalled())


@pytest.mark.asyncio
async def test_bad_json_extract_failed(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    upgrade_db(db)
    engine = make_engine(db)
    pdf_bytes = (Path(__file__).resolve().parent / "fixtures" / "synthetic.pdf").read_bytes()
    mask_result = _mask_result(pdf_bytes)
    client = RecordedClient(FIXTURES / "bad.json")
    with Session(engine) as session:
        row = _row(session, mask_result)
        with pytest.raises(ExtractFailed):
            await extract_statement(row, mask_result, session, client)
        session.refresh(row)
        assert row.status == "extract_failed"
        assert row.error


@pytest.mark.asyncio
async def test_twenty_five_pages_under_thirty_seconds(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    upgrade_db(db)
    engine = make_engine(db)
    doc = build_pdf(pages=25)
    pdf_bytes = doc.tobytes()
    doc.close()
    mask_result = MaskResult(
        pdf_bytes=pdf_bytes,
        bank="generic",
        page_count=25,
        redaction_count=0,
        warnings=[],
        masked_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
    )
    client = RecordedClient(FIXTURES / "synthetic.json")
    with Session(engine) as session:
        row = _row(session, mask_result)
        start = time.perf_counter()
        await extract_statement(row, mask_result, session, client)
        elapsed = time.perf_counter() - start
        assert elapsed < 30, elapsed
