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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
