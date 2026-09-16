from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import upgrade_db


def _client(tmp_path: Path, *, env: str = "dev", maintenance: bool = False) -> TestClient:
    from app.main import create_app

    db = tmp_path / "t.db"
    upgrade_db(db)
    app = create_app(database_path=db, env=env, maintenance=maintenance)
    return TestClient(app)


def test_import_without_static_dir() -> None:
    from app.main import app

    assert app.title == "Ekstre Analyzer"


def test_healthz_ok(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.get("/api/healthz")
        assert response.status_code == 200
        assert response.json() == {"ok": True}


def test_validation_error_envelope(tmp_path: Path) -> None:
    from app.main import create_app

    db = tmp_path / "t.db"
    upgrade_db(db)
    app = create_app(database_path=db)

    @app.get("/__probe")
    def probe(n: int) -> dict[str, int]:
        return {"n": n}

    with TestClient(app) as client:
        response = client.get("/__probe", params={"n": "x"})
        assert response.status_code == 422
        body = response.json()
        assert body["error"]["code"] == "validation_error"
        assert "issues" in body["error"]


def test_csp_only_in_prod(tmp_path: Path) -> None:
    with _client(tmp_path, env="dev") as client:
        dev = client.get("/api/healthz")
        assert "content-security-policy" not in dev.headers
        assert dev.headers["x-content-type-options"] == "nosniff"
    with _client(tmp_path, env="prod") as client:
        prod = client.get("/api/healthz")
        assert "default-src 'self'" in prod.headers["content-security-policy"]
