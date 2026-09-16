from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "gemini" / "synthetic.json"
MISMATCH = ROOT / "tests" / "fixtures" / "gemini" / "mismatch.json"
SYNTHETIC = ROOT / "tests" / "fixtures" / "synthetic.pdf"


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged["PYTHONIOENCODING"] = "utf-8"
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, str(ROOT / "cli.py"), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=merged,
    )


def test_extract_unmasked_leaks_without_opening_replay(tmp_path: Path) -> None:
    db = tmp_path / "app.db"
    result = _run(
        "extract",
        str(SYNTHETIC),
        "--db",
        str(db),
        env={"GEMINI_REPLAY": str(tmp_path / "missing.json")},
    )
    assert result.returncode == 1
    assert "leak" in result.stderr.lower()


def test_extract_replay_ls_duplicate_and_mismatch(tmp_path: Path) -> None:
    db = tmp_path / "app.db"
    masked = tmp_path / "masked.pdf"
    upgraded = _run("db", "upgrade", "--db", str(db))
    assert upgraded.returncode == 0, upgraded.stderr
    masked_run = _run("mask", str(SYNTHETIC), "-o", str(masked))
    assert masked_run.returncode == 0, masked_run.stderr

    first = _run(
        "extract",
        str(masked),
        "--db",
        str(db),
        env={"GEMINI_REPLAY": str(FIXTURE)},
    )
    assert first.returncode == 0, first.stderr + first.stdout

    listed = _run("ls", "--db", str(db), "--category", "market")
    assert listed.returncode == 0
    assert "market" in listed.stdout.lower()

    second = _run(
        "extract",
        str(masked),
        "--db",
        str(db),
        env={"GEMINI_REPLAY": str(FIXTURE)},
    )
    assert second.returncode == 1
    assert "zaten yüklü" in second.stderr

    db2 = tmp_path / "mismatch.db"
    assert _run("db", "upgrade", "--db", str(db2)).returncode == 0
    mismatch = _run(
        "extract",
        str(masked),
        "--db",
        str(db2),
        env={"GEMINI_REPLAY": str(MISMATCH)},
    )
    assert mismatch.returncode == 3, mismatch.stderr + mismatch.stdout
