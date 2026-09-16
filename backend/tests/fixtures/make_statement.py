"""Generate a synthetic bank-statement PDF for CI (no real PII)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pymupdf

EXPECTED = {
    "iban": "TR33 0006 1005 1978 6457 8413 26",
    "card_number": "4242 4242 4242 4242",
    "tckn": "10000000146",
    "name": "Ayse Yilmaz",
    "phone": "0532 111 22 33",
    "email": "ayse@example.com",
    "address": "Ornek Mah. Test Sok. No 1 Ankara",
    "customer_no": "12345678",
}

FONT_SIZE = 10
LEFT = 50
LINE_H = 14


def _write_line(page: pymupdf.Page, y: float, text: str, font: pymupdf.Font) -> None:
    tw = pymupdf.TextWriter(page.rect)
    tw.append((LEFT, y), text, font=font, fontsize=FONT_SIZE)
    tw.write_text(page)


def build_pdf(pages: int = 3) -> pymupdf.Document:
    if pages < 1:
        raise ValueError("pages must be >= 1")
    font = pymupdf.Font("helv")
    doc = pymupdf.open()
    page = doc.new_page()
    y = 50
    _write_line(page, y, "Sentetik Banka Ekstresi", font)
    y += LINE_H * 2
    _write_line(page, y, f"Müşteri No: {EXPECTED['customer_no']}", font)
    y += LINE_H
    _write_line(page, y, f"Sayın {EXPECTED['name']}", font)
    y += LINE_H
    _write_line(page, y, f"Adres: {EXPECTED['address']}", font)
    y += LINE_H
    _write_line(page, y, f"TCKN: {EXPECTED['tckn']}", font)
    y += LINE_H
    _write_line(page, y, f"IBAN: {EXPECTED['iban']}", font)
    y += LINE_H
    _write_line(page, y, f"Kart No: {EXPECTED['card_number']}", font)
    y += LINE_H
    _write_line(page, y, f"Telefon: {EXPECTED['phone']}", font)
    y += LINE_H
    _write_line(page, y, f"E-posta: {EXPECTED['email']}", font)
    y += LINE_H * 2
    _write_line(page, y, "İşlem Tarihi    Açıklama              Tutar", font)
    y += LINE_H

    txn_count = 30 if pages <= 3 else max(30, (pages - 1) * 20)
    txns_per_page = 12
    txn_idx = 0
    while txn_idx < txn_count:
        if y > 780:
            page = doc.new_page()
            y = 50
            _write_line(page, y, "İşlem Tarihi    Açıklama              Tutar", font)
            y += LINE_H
        day = (txn_idx % 28) + 1
        amount = f"{(txn_idx + 1) * 12 + 0.5:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        merchant = f"Market {txn_idx + 1}"
        _write_line(page, y, f"{day:02d}/09/2026    {merchant:<20} {amount}", font)
        y += LINE_H
        txn_idx += 1
        if txn_idx % txns_per_page == 0 and txn_idx < txn_count and page.number + 1 < pages:
            page = doc.new_page()
            y = 50
            _write_line(page, y, "İşlem Tarihi    Açıklama              Tutar", font)
            y += LINE_H

    while doc.page_count < pages:
        extra = doc.new_page()
        _write_line(extra, 50, "İşlem Tarihi    Açıklama              Tutar", font)
        _write_line(extra, 50 + LINE_H, "01/09/2026    Market extra         10,00", font)

    last = doc[-1]
    _write_line(last, 800, "Toplam: 1.234,56", font)
    return doc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", type=Path, default=Path("tests/fixtures/synthetic.pdf"))
    parser.add_argument("--pages", type=int, default=3)
    parser.add_argument("--password", default=None)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    expected_path = args.output.with_name("synthetic_expected.json")
    doc = build_pdf(pages=args.pages)
    if args.password:
        doc.save(
            args.output,
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            user_pw=args.password,
        )
    else:
        doc.save(args.output)
    doc.close()
    expected_path.write_text(json.dumps(EXPECTED, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
