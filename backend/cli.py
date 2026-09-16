"""CLI: mask, inspect, verify, render."""

from __future__ import annotations

from getpass import getpass
from pathlib import Path

import pymupdf
import typer

from app.anonymizer.layout import lines
from app.anonymizer.masker import PasswordRequired, ScannedPdf, WrongPassword, mask
from app.anonymizer.profile import (
    MIN_TERM_LEN,
    detect_profile,
    extra_term_pattern,
    load_all_profiles,
    profile_by_bank,
)
from app.anonymizer.sanitize import UnsafePdf
from app.anonymizer.verify import LeakDetected, leak_scan

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _read_pdf(path: Path) -> bytes:
    return path.read_bytes()


def _resolve_profile(name: str | None, first_page_text: str):
    profiles = load_all_profiles()
    warnings: list[str] = []
    if name:
        profile = profile_by_bank(name, profiles)
    else:
        profile, warnings = detect_profile(first_page_text, profiles)
    return profile, warnings


def _password_for(pdf_bytes: bytes, password: str | None) -> str | None:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        if not doc.needs_pass:
            return password
        if password:
            return password
        return getpass("PDF password: ")
    finally:
        doc.close()


def _first_page_text(pdf_bytes: bytes, password: str | None) -> str:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        if doc.needs_pass:
            if not password or doc.authenticate(password) == 0:
                raise WrongPassword()
        if doc.page_count == 0:
            return ""
        return doc[0].get_text("text")
    finally:
        doc.close()


@app.command("mask")
def mask_command(
    input_pdf: Path = typer.Argument(..., metavar="INPUT.pdf"),
    output: Path = typer.Option(..., "-o", help="Masked PDF path"),
    profile_name: str | None = typer.Option(None, "--profile"),
    password: str | None = typer.Option(None, "--password"),
    term: list[str] | None = typer.Option(None, "--term"),
) -> None:
    extra = term or []
    for item in extra:
        if len(item.strip()) < MIN_TERM_LEN:
            raise typer.BadParameter("each --term must be at least 3 characters")
        extra_term_pattern(item)
    pdf_bytes = _read_pdf(input_pdf)
    password = _password_for(pdf_bytes, password)
    try:
        first = _first_page_text(pdf_bytes, password)
        profile, warnings = _resolve_profile(profile_name, first)
        result = mask(pdf_bytes, profile, password=password, extra_terms=extra)
    except PasswordRequired as exc:
        typer.echo("password required", err=True)
        raise typer.Exit(1) from exc
    except WrongPassword as exc:
        typer.echo("wrong password", err=True)
        raise typer.Exit(1) from exc
    except UnsafePdf as exc:
        typer.echo(f"unsafe pdf: {exc}", err=True)
        raise typer.Exit(1) from exc
    except ScannedPdf as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    except LeakDetected as exc:
        typer.echo(f"leak detected ({len(exc.findings)})", err=True)
        raise typer.Exit(2) from exc
    for warning in warnings:
        typer.echo(f"warning: {warning}", err=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result.pdf_bytes)


@app.command()
def inspect(
    input_pdf: Path = typer.Argument(..., metavar="INPUT.pdf"),
    page: int | None = typer.Option(None, "--page"),
    password: str | None = typer.Option(None, "--password"),
) -> None:
    pdf_bytes = _read_pdf(input_pdf)
    password = _password_for(pdf_bytes, password)
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        if doc.needs_pass:
            if not password or doc.authenticate(password) == 0:
                raise typer.Exit(1)
        pages = range(doc.page_count) if page is None else [page]
        for index in pages:
            typer.echo(f"# page {index}")
            for line_i, line in enumerate(lines(doc[index])):
                typer.echo(f"L{line_i} {line.text}")
                for span_text, rect in line.spans:
                    typer.echo(f"  span {rect} {span_text}")
    finally:
        doc.close()


@app.command()
def verify(
    masked_pdf: Path = typer.Argument(..., metavar="MASKED.pdf"),
    profile_name: str | None = typer.Option(None, "--profile"),
    expect_absent: Path | None = typer.Option(None, "--expect-absent"),
    password: str | None = typer.Option(None, "--password"),
) -> None:
    pdf_bytes = _read_pdf(masked_pdf)
    password = _password_for(pdf_bytes, password)
    first = _first_page_text(pdf_bytes, password)
    profile, _ = _resolve_profile(profile_name, first)
    absent: list[str] = []
    if expect_absent:
        absent = [
            line.strip()
            for line in expect_absent.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    findings = leak_scan(pdf_bytes, profile, absent=absent)
    if findings:
        typer.echo(f"{len(findings)} finding(s)", err=True)
        raise typer.Exit(1)


@app.command()
def render(
    masked_pdf: Path = typer.Argument(..., metavar="MASKED.pdf"),
    output_dir: Path = typer.Option(..., "-o"),
    dpi: int = typer.Option(100, "--dpi"),
    password: str | None = typer.Option(None, "--password"),
) -> None:
    pdf_bytes = _read_pdf(masked_pdf)
    password = _password_for(pdf_bytes, password)
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        if doc.needs_pass:
            if not password or doc.authenticate(password) == 0:
                raise typer.Exit(1)
        for index, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)
            pix.save(output_dir / f"page-{index:03d}.png")
    finally:
        doc.close()


db_app = typer.Typer(help="Database commands")
app.add_typer(db_app, name="db")


def _run_upgrade(db_path: Path) -> None:
    import argparse

    from alembic import command
    from alembic.config import Config

    ini = Path(__file__).resolve().parent / "app" / "db" / "alembic.ini"
    cfg = Config(str(ini))
    cfg.cmd_opts = argparse.Namespace(x=[f"db={db_path.resolve()}"])
    command.upgrade(cfg, "head")


@db_app.command("upgrade")
def db_upgrade(db: Path = typer.Option(..., "--db")) -> None:
    db.parent.mkdir(parents=True, exist_ok=True)
    _run_upgrade(db)


def _mask_result_from_bytes(pdf_bytes: bytes, bank: str):
    import hashlib

    from app.anonymizer.masker import MaskResult

    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        page_count = doc.page_count
    finally:
        doc.close()
    return MaskResult(
        pdf_bytes=pdf_bytes,
        bank=bank,
        page_count=page_count,
        redaction_count=0,
        warnings=[],
        masked_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
    )


def _format_tl(kurus: int) -> str:
    sign = "-" if kurus < 0 else ""
    kurus = abs(kurus)
    whole, frac = divmod(kurus, 100)
    whole_s = f"{whole:,}".replace(",", ".")
    return f"{sign}{whole_s},{frac:02d}"


@app.command("extract")
def extract_command(
    masked_pdf: Path = typer.Argument(..., metavar="MASKED.pdf"),
    db: Path = typer.Option(..., "--db"),
    profile_name: str | None = typer.Option(None, "--profile"),
    record: Path | None = typer.Option(None, "--record"),
) -> None:
    import asyncio
    import json
    from datetime import UTC, datetime

    from sqlalchemy import select

    from app.config import settings
    from app.db.models import Statement
    from app.db.session import make_engine, make_session_factory
    from app.extractor.client import GeminiClient, RecordedClient
    from app.extractor.service import DuplicateStatement, ExtractFailed, extract_statement

    pdf_bytes = _read_pdf(masked_pdf)
    first = _first_page_text(pdf_bytes, None)
    profile, _warnings = _resolve_profile(profile_name, first)
    findings = leak_scan(pdf_bytes, profile)
    if findings:
        typer.echo(f"leak detected ({len(findings)})", err=True)
        raise typer.Exit(1)

    mask_result = _mask_result_from_bytes(pdf_bytes, profile.bank)
    engine = make_engine(db)
    factory = make_session_factory(engine)
    now = datetime.now(UTC).replace(tzinfo=None)
    with factory() as session:
        existing = session.execute(
            select(Statement).where(
                Statement.user_id == 1,
                Statement.masked_sha256 == mask_result.masked_sha256,
            )
        ).scalar_one_or_none()
        if existing is not None and existing.status in ("done", "needs_review"):
            typer.echo(f"bu ekstre zaten yüklü (statement {existing.id})", err=True)
            raise typer.Exit(1)
        if existing is None:
            row = Statement(
                user_id=1,
                profile=profile.bank,
                uploaded_at=now,
                page_count=mask_result.page_count,
                redaction_count=0,
                masked_sha256=mask_result.masked_sha256,
                status="extracting",
            )
            session.add(row)
            session.commit()
            session.refresh(row)
        else:
            row = existing
            row.status = "extracting"
            session.commit()

        if settings.gemini_replay:
            client: GeminiClient | RecordedClient = RecordedClient(Path(settings.gemini_replay))
        else:
            client = GeminiClient(settings)

        try:
            asyncio.run(extract_statement(row, mask_result, session, client))
        except DuplicateStatement as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1) from exc
        except ExtractFailed:
            raise typer.Exit(1)

        if record:
            record.parent.mkdir(parents=True, exist_ok=True)
            recordings = getattr(client, "recordings", [])
            if len(recordings) == 1:
                record.write_text(json.dumps(recordings[0], ensure_ascii=False, indent=2), encoding="utf-8")
            else:
                record.write_text(
                    json.dumps({"chunks": recordings}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

        session.refresh(row)
        if row.status == "needs_review":
            raise typer.Exit(3)


@app.command("ls")
def ls_command(
    db: Path = typer.Option(..., "--db"),
    from_: str | None = typer.Option(None, "--from"),
    to: str | None = typer.Option(None, "--to"),
    category: str | None = typer.Option(None, "--category"),
    statement: int | None = typer.Option(None, "--statement"),
) -> None:
    from datetime import date

    from sqlalchemy import select

    from app.db.models import Transaction
    from app.db.session import make_engine, make_session_factory

    engine = make_engine(db)
    factory = make_session_factory(engine)
    with factory() as session:
        query = select(Transaction).order_by(Transaction.txn_date, Transaction.id)
        if from_:
            query = query.where(Transaction.txn_date >= date.fromisoformat(from_))
        if to:
            query = query.where(Transaction.txn_date <= date.fromisoformat(to))
        if category:
            query = query.where(Transaction.category == category)
        if statement is not None:
            query = query.where(Transaction.statement_id == statement)
        rows = session.execute(query).scalars().all()
    for row in rows:
        typer.echo(
            f"{row.txn_date.isoformat()}  {row.description}  {_format_tl(row.amount_kurus)}  "
            f"{row.category}  {row.confidence:.2f}"
        )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
