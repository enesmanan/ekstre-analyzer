import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "cli.py"), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_verify_unmasked_exits_one() -> None:
    result = _run("verify", "tests/fixtures/synthetic.pdf")
    assert result.returncode == 1


def test_mask_then_verify_exits_zero(tmp_path: Path) -> None:
    out = tmp_path / "masked.pdf"
    masked = _run("mask", "tests/fixtures/synthetic.pdf", "-o", str(out))
    assert masked.returncode == 0
    verified = _run("verify", str(out))
    assert verified.returncode == 0


def test_term_too_short_rejected(tmp_path: Path) -> None:
    out = tmp_path / "masked.pdf"
    result = _run("mask", "tests/fixtures/synthetic.pdf", "-o", str(out), "--term", "ab")
    assert result.returncode != 0
