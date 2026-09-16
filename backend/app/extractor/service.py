"""Extract a masked statement: leak/duplicate are enforced by the CLI before this runs; this still re-checks duplicate."""

from __future__ import annotations

import asyncio
import base64
import json
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime

import pymupdf
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.anonymizer.masker import MaskResult
from app.config import settings
from app.db.models import Statement, Transaction
from app.extractor.chunker import split
from app.extractor.client import LLMClient, Usage
from app.extractor.schema import Extraction, Txn
from app.extractor.validate import ValidationReport, validate


class DuplicateStatement(Exception):
    def __init__(self, statement_id: int):
        self.statement_id = statement_id
        super().__init__(f"bu ekstre zaten yüklü (statement {statement_id})")


class ExtractFailed(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


@dataclass
class ChunkTxn:
    chunk_index: int
    txn: Txn


def normalize_merchant(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    kept: list[str] = []
    for token in ascii_name.upper().split():
        cleaned = token.strip("*")
        if not cleaned or cleaned.isdigit():
            continue
        if len(cleaned) == 1 and cleaned.isalpha():
            continue
        kept.append(cleaned)
    return " ".join(kept)


def cost_usd_micro(usage: Usage, price_in: float, price_out: float) -> int:
    return int(usage.input_tokens * price_in + (usage.output_tokens + usage.thought_tokens) * price_out)


def _txn_key(txn: Txn) -> tuple:
    return (txn.txn_date, txn.amount_kurus, txn.description)


def merge_extractions(parts: list[tuple[int, Extraction]]) -> tuple[Extraction, int]:
    parts = sorted(parts, key=lambda item: item[0])
    header = parts[0][1]
    grouped: list[list[Txn]] = [list(ext.transactions) for _, ext in parts]
    first_keys = {_txn_key(txn) for txn in grouped[0]} if grouped else set()
    dropped = 0
    for index in range(1, len(grouped)):
        kept: list[Txn] = []
        for txn in grouped[index]:
            if _txn_key(txn) in first_keys:
                dropped += 1
                continue
            kept.append(txn)
        grouped[index] = kept
    for index in range(len(grouped) - 1):
        if not grouped[index] or not grouped[index + 1]:
            continue
        if _txn_key(grouped[index][-1]) == _txn_key(grouped[index + 1][0]):
            grouped[index + 1] = grouped[index + 1][1:]
            dropped += 1
    merged: list[Txn] = []
    for group in grouped:
        merged.extend(group)
    header.transactions = merged
    return header, dropped


def _pdf_text(pdf_bytes: bytes) -> str:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        return "".join(page.get_text("text") for page in doc)
    finally:
        doc.close()


def _check_duplicate(db: Session, statement: Statement, mask_result: MaskResult) -> None:
    row = db.execute(
        select(Statement).where(
            Statement.user_id == statement.user_id,
            Statement.masked_sha256 == mask_result.masked_sha256,
            Statement.id != statement.id,
            Statement.status.in_(("done", "needs_review")),
        )
    ).scalar_one_or_none()
    if row is not None:
        raise DuplicateStatement(row.id)
    if statement.status in ("done", "needs_review"):
        raise DuplicateStatement(statement.id)


async def extract_statement(
    statement: Statement,
    mask_result: MaskResult,
    db: Session,
    client: LLMClient,
) -> Statement:
    _check_duplicate(db, statement, mask_result)

    chunks = split(mask_result.pdf_bytes)
    sem = asyncio.Semaphore(3)

    async def _one(index: int, data: bytes) -> tuple[int, Extraction, Usage]:
        async with sem:
            b64 = base64.b64encode(data).decode("ascii")
            extraction, usage = await client.extract_chunk(b64, index)
            return index, extraction, usage

    try:
        gathered = await asyncio.gather(*[_one(i, data) for i, data in enumerate(chunks)])
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        statement.status = "extract_failed"
        statement.error = str(exc)[:500]
        db.commit()
        raise ExtractFailed(statement.error) from exc

    usages = [item[2] for item in gathered]
    merged, dropped = merge_extractions([(item[0], item[1]) for item in gathered])
    for txn in merged.transactions:
        txn.merchant_norm = normalize_merchant(txn.merchant_norm)

    extra = [f"chunk_dup:{dropped}"] if dropped else []
    report: ValidationReport = validate(merged, pdf_text=_pdf_text(mask_result.pdf_bytes), extra_issues=extra)

    total_in = sum(u.input_tokens for u in usages)
    total_out = sum(u.output_tokens for u in usages)
    total_thought = sum(u.thought_tokens for u in usages)
    combined_usage = Usage(total_in, total_out, total_thought)

    statement.bank = merged.bank
    statement.profile = mask_result.bank
    statement.statement_type = merged.statement_type
    statement.period_start = merged.period_start
    statement.period_end = merged.period_end
    statement.page_count = mask_result.page_count
    statement.redaction_count = mask_result.redaction_count
    statement.mask_warnings_json = json.dumps(mask_result.warnings, ensure_ascii=False)
    statement.validation_issues_json = json.dumps(report.issues, ensure_ascii=False)
    statement.masked_sha256 = mask_result.masked_sha256
    statement.model_used = getattr(getattr(client, "_settings", None), "gemini_model", None) or "recorded"
    statement.status = report.status
    statement.error = None
    statement.input_tokens = total_in
    statement.output_tokens = total_out
    statement.thought_tokens = total_thought
    statement.cost_usd_micro = cost_usd_micro(
        combined_usage,
        settings.gemini_price_in_per_m,
        settings.gemini_price_out_per_m,
    )
    statement.stated_total_debit_kurus = merged.stated_total_debit_kurus
    statement.extracted_total_debit_kurus = sum(
        txn.amount_kurus for txn in merged.transactions if txn.direction == "debit"
    )

    statement.transactions.clear()
    now = datetime.now(UTC).replace(tzinfo=None)
    for txn in merged.transactions:
        statement.transactions.append(
            Transaction(
                user_id=statement.user_id,
                txn_date=txn.txn_date,
                description=txn.description,
                amount_kurus=txn.amount_kurus,
                currency="TRY",
                direction=txn.direction,
                category=txn.category,
                merchant_norm=txn.merchant_norm,
                confidence=txn.confidence,
                is_installment=1 if txn.is_installment else 0,
                installment_no=txn.installment_no,
                installment_total=txn.installment_total,
                created_at=now,
            )
        )
    db.commit()
    db.refresh(statement)
    return statement
