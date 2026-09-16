from pathlib import Path

from app.anonymizer.masker import mask
from app.anonymizer.profile import load_profile
from app.anonymizer.verify import leak_scan

ROOT = Path(__file__).resolve().parent
SYNTHETIC = ROOT / "fixtures" / "synthetic.pdf"
GENERIC = load_profile(ROOT.parent / "profiles" / "generic.yaml")


def test_unmasked_has_findings_masked_has_none() -> None:
    raw = SYNTHETIC.read_bytes()
    unmasked = leak_scan(raw, GENERIC)
    assert len(unmasked) >= 6
    result = mask(raw, GENERIC)
    assert leak_scan(result.pdf_bytes, GENERIC) == []
