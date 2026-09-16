import json
from pathlib import Path

import pymupdf
import pytest

from app.anonymizer.masker import (
    MaskResult,
    PasswordRequired,
    ScannedPdf,
    WrongPassword,
    mask,
)
from app.anonymizer.profile import load_profile
from tests.fixtures.make_statement import build_pdf

ROOT = Path(__file__).resolve().parent
SYNTHETIC = ROOT / "fixtures" / "synthetic.pdf"
EXPECTED = json.loads((ROOT / "fixtures" / "synthetic_expected.json").read_text(encoding="utf-8"))
GENERIC = load_profile(ROOT.parent / "profiles" / "generic.yaml")
PASSWORD = "12345678901"


def test_synthetic_values_removed_amounts_kept() -> None:
    result = mask(SYNTHETIC.read_bytes(), GENERIC)
    assert isinstance(result, MaskResult)
    assert result.page_count == 3
    text = pymupdf.open(stream=result.pdf_bytes, filetype="pdf").get_page_text(0)
    for key, value in EXPECTED.items():
        if key == "customer_no":
            continue
        assert value not in text
    full = ""
    doc = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
    for page in doc:
        full += page.get_text("text")
    doc.close()
    assert "16/09/2026" in full or "01/09/2026" in full
    assert "," in full


def test_scanned_pdf_rejected() -> None:
    doc = pymupdf.open()
    doc.new_page()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    with pytest.raises(ScannedPdf, match="Taranmış ekstre desteklenmiyor"):
        mask(data, GENERIC)


def _encrypted_bytes(tmp_path: Path) -> bytes:
    path = tmp_path / "enc.pdf"
    doc = build_pdf(pages=3)
    doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw=PASSWORD)
    doc.close()
    return path.read_bytes()


def test_password_required(tmp_path: Path) -> None:
    with pytest.raises(PasswordRequired):
        mask(_encrypted_bytes(tmp_path), GENERIC)


def test_wrong_password(tmp_path: Path) -> None:
    with pytest.raises(WrongPassword):
        mask(_encrypted_bytes(tmp_path), GENERIC, password="00000000000")


def test_password_unlocks_and_output_is_plain(tmp_path: Path) -> None:
    result = mask(_encrypted_bytes(tmp_path), GENERIC, password=PASSWORD)
    opened = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
    assert not opened.needs_pass
    opened.close()
    assert PASSWORD not in result.pdf_bytes.decode("latin-1", errors="ignore")
