from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.anonymizer.masker import mask as real_mask
from app.config import settings
from tests.conftest import upgrade_db
from tests.fixtures.make_statement import build_pdf

GEMINI = Path(__file__).resolve().parent / "fixtures" / "gemini"
SYNTHETIC = Path(__file__).resolve().parent / "fixtures" / "synthetic.pdf"
HEADERS = {"Content-Type": "application/pdf"}


def test_healthz_during_two_uploads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import create_app

    monkeypatch.setattr(settings, "gemini_replay", str(GEMINI / "synthetic.json"))

    def slow_mask(*args: object, **kwargs: object):
        time.sleep(0.2)
        return real_mask(*args, **kwargs)

    monkeypatch.setattr("app.jobs.mask", slow_mask)
    db = tmp_path / "t.db"
    upgrade_db(db)
    app = create_app(database_path=db)
    extra = build_pdf(pages=3)
    extra_bytes = extra.tobytes()
    extra.close()
    times_ms: list[float] = []
    stop = threading.Event()
    with TestClient(app) as client:

        def ping() -> None:
            while not stop.wait(0.03):
                started = time.perf_counter()
                response = client.get("/api/healthz")
                times_ms.append((time.perf_counter() - started) * 1000)
                assert response.status_code == 200

        worker = threading.Thread(target=ping)
        worker.start()
        try:
            first = client.post("/api/v1/statements", content=SYNTHETIC.read_bytes(), headers=HEADERS)
            second = client.post("/api/v1/statements", content=extra_bytes, headers=HEADERS)
            assert first.status_code == 202
            assert second.status_code == 202
        finally:
            stop.set()
            worker.join()
    assert times_ms
    assert max(times_ms) < 200, max(times_ms)
