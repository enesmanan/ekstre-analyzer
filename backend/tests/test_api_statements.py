from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.anonymizer.verify import LeakDetected
from app.config import settings
from tests.conftest import upgrade_db
from tests.fixtures.make_statement import build_pdf

SYNTHETIC = Path(__file__).resolve().parent / "fixtures" / "synthetic.pdf"
GEMINI = Path(__file__).resolve().parent / "fixtures" / "gemini"
HEADERS = {"Content-Type": "application/pdf"}


def _client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    replay: str = "synthetic.json",
    maintenance: bool = False,
) -> TestClient:
    from app.main import create_app

    monkeypatch.setattr(settings, "gemini_replay", str(GEMINI / replay))
    db = tmp_path / "t.db"
    upgrade_db(db)
    app = create_app(database_path=db, maintenance=maintenance)
    return TestClient(app)


def _poll(client: TestClient, statement_id: int, timeout: float = 20.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/api/v1/statements/{statement_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] not in ("queued", "masking", "extracting"):
            return body
        time.sleep(0.05)
    raise AssertionError("statement did not finish")


def _encrypted(password: str = "secret") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    font = pymupdf.Font("helv")
    writer = pymupdf.TextWriter(page.rect)
    writer.append((50, 80), ("lorem ipsum dolor sit amet " * 20), font=font, fontsize=10)
    writer.write_text(page)
    data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw=password)
    doc.close()
    return data


def _form_pdf() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    widget = pymupdf.Widget()
    widget.field_name = "field"
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.rect = pymupdf.Rect(50, 50, 200, 80)
    page.add_widget(widget)
    data = doc.tobytes()
    doc.close()
    return data


def _blank_pdf() -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    data = doc.tobytes()
    doc.close()
    return data


def test_too_large(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        body = b"%PDF-" + (b"x" * (16 * 1024 * 1024))
        response = client.post("/api/v1/statements", content=body, headers=HEADERS)
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "too_large"


def test_unsafe_magic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        response = client.post("/api/v1/statements", content=b"not-a-pdf", headers=HEADERS)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "unsafe_pdf"


def test_password_required_and_wrong(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = _encrypted()
    with _client(tmp_path, monkeypatch) as client:
        missing = client.post("/api/v1/statements", content=data, headers=HEADERS)
        assert missing.status_code == 400
        assert missing.json()["error"]["code"] == "password_required"
        wrong = client.post(
            "/api/v1/statements",
            content=data,
            headers={**HEADERS, "X-Statement-Password": "nope"},
        )
        assert wrong.status_code == 400
        assert wrong.json()["error"]["code"] == "wrong_password"


def test_too_many_pages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    doc = build_pdf(pages=61)
    data = doc.tobytes()
    doc.close()
    with _client(tmp_path, monkeypatch) as client:
        response = client.post("/api/v1/statements", content=data, headers=HEADERS)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "too_many_pages"


def test_unsafe_form(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        response = client.post("/api/v1/statements", content=_form_pdf(), headers=HEADERS)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "unsafe_pdf"


def test_upload_done_list_preview_delete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf = SYNTHETIC.read_bytes()
    with _client(tmp_path, monkeypatch) as client:
        created = client.post("/api/v1/statements", content=pdf, headers=HEADERS)
        assert created.status_code == 202
        statement_id = created.json()["id"]
        body = _poll(client, statement_id)
        assert body["status"] == "done"
        listed = client.get("/api/v1/statements")
        assert listed.status_code == 200
        assert any(item["id"] == statement_id for item in listed.json())
        preview = client.get(f"/api/v1/statements/{statement_id}/preview.png")
        assert preview.status_code == 200
        assert preview.headers["content-type"] == "image/png"
        assert preview.content[:8] == b"\x89PNG\r\n\x1a\n"
        deleted = client.delete(f"/api/v1/statements/{statement_id}")
        assert deleted.status_code == 204
        missing = client.get(f"/api/v1/statements/{statement_id}")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "not_found"


def test_duplicate_statement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf = SYNTHETIC.read_bytes()
    with _client(tmp_path, monkeypatch) as client:
        first = client.post("/api/v1/statements", content=pdf, headers=HEADERS)
        assert _poll(client, first.json()["id"])["status"] == "done"
        second = client.post("/api/v1/statements", content=pdf, headers=HEADERS)
        assert second.status_code == 202
        body = _poll(client, second.json()["id"])
        assert body["status"] == "mask_failed"
        assert body["error"] == "duplicate_statement"


def test_leak_does_not_build_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[int] = []

    def boom(*_args: object, **_kwargs: object) -> None:
        raise LeakDetected(["tckn"])

    def no_client() -> None:
        called.append(1)
        raise AssertionError("client must not be built")

    monkeypatch.setattr("app.jobs.mask", boom)
    monkeypatch.setattr("app.jobs.make_llm_client", no_client)
    with _client(tmp_path, monkeypatch) as client:
        created = client.post("/api/v1/statements", content=SYNTHETIC.read_bytes(), headers=HEADERS)
        body = _poll(client, created.json()["id"])
        assert body["status"] == "mask_failed"
        assert body["error"] == "leak_detected"
        assert called == []


def test_scanned_pdf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with _client(tmp_path, monkeypatch) as client:
        created = client.post("/api/v1/statements", content=_blank_pdf(), headers=HEADERS)
        assert created.status_code == 202
        body = _poll(client, created.json()["id"])
        assert body["status"] == "mask_failed"
        assert body["error"] == "scanned_pdf"


def test_preview_queued_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.statements.BackgroundTasks.add_task",
        lambda self, *args, **kwargs: None,
    )
    with _client(tmp_path, monkeypatch) as client:
        created = client.post("/api/v1/statements", content=SYNTHETIC.read_bytes(), headers=HEADERS)
        statement_id = created.json()["id"]
        preview = client.get(f"/api/v1/statements/{statement_id}/preview.png")
        assert preview.status_code == 404
        assert preview.json()["error"]["code"] == "not_found"


def test_preview_expired_injected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf = SYNTHETIC.read_bytes()
    with _client(tmp_path, monkeypatch) as client:
        created = client.post("/api/v1/statements", content=pdf, headers=HEADERS)
        statement_id = created.json()["id"]
        _poll(client, statement_id)
        entry = client.app.state.jobs.entries[statement_id]
        entry.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
        preview = client.get(f"/api/v1/statements/{statement_id}/preview.png")
        assert preview.status_code == 404
        assert preview.json()["error"]["code"] == "preview_expired"


def test_maintenance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with _client(tmp_path, monkeypatch, maintenance=True) as client:
        posted = client.post("/api/v1/statements", content=SYNTHETIC.read_bytes(), headers=HEADERS)
        assert posted.status_code == 503
        assert posted.json()["error"]["code"] == "maintenance"
        deleted = client.delete("/api/v1/statements/1")
        assert deleted.status_code == 503
        patched = client.patch("/api/v1/transactions/1", json={"category": "market"})
        assert patched.status_code == 503
        health = client.get("/api/healthz")
        assert health.status_code == 200
        listed = client.get("/api/v1/statements")
        assert listed.status_code == 200


def test_busy_fifth_queued(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.statements.BackgroundTasks.add_task",
        lambda self, *args, **kwargs: None,
    )
    pdf = SYNTHETIC.read_bytes()
    with _client(tmp_path, monkeypatch) as client:
        for _ in range(4):
            created = client.post("/api/v1/statements", content=pdf, headers=HEADERS)
            assert created.status_code == 202
        fifth = client.post("/api/v1/statements", content=pdf, headers=HEADERS)
        assert fifth.status_code == 503
        assert fifth.json()["error"]["code"] == "busy"


def test_extract_failed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with _client(tmp_path, monkeypatch, replay="bad.json") as client:
        created = client.post("/api/v1/statements", content=SYNTHETIC.read_bytes(), headers=HEADERS)
        body = _poll(client, created.json()["id"])
        assert body["status"] == "extract_failed"
        assert body["error"]


def test_restart_marks_queued(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy.orm import Session

    from app.db.models import Statement
    from app.db.session import make_engine
    from app.main import create_app

    monkeypatch.setattr(settings, "gemini_replay", str(GEMINI / "synthetic.json"))
    db = tmp_path / "t.db"
    upgrade_db(db)
    engine = make_engine(db)
    with Session(engine) as session:
        row = Statement(
            user_id=1,
            uploaded_at=datetime.now(UTC).replace(tzinfo=None),
            page_count=0,
            masked_sha256="pending:restart-test",
            status="queued",
        )
        session.add(row)
        session.commit()
        statement_id = row.id
    app = create_app(database_path=db)
    with TestClient(app) as client:
        body = client.get(f"/api/v1/statements/{statement_id}")
        assert body.status_code == 200
        payload = body.json()
        assert payload["status"] == "mask_failed"
        assert payload["error"] == "restart"
