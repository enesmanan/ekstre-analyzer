from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import STATIC_DIR
from tests.conftest import upgrade_db

GEMINI = Path(__file__).resolve().parent / "fixtures" / "gemini"


@pytest.mark.skipif(not (STATIC_DIR / "index.html").is_file(), reason="frontend not copied to static/")
def test_spa_html_and_api_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import create_app

    monkeypatch.setattr(settings, "gemini_replay", str(GEMINI / "synthetic.json"))
    db = tmp_path / "t.db"
    upgrade_db(db)
    app = create_app(database_path=db, env="prod")
    with TestClient(app) as client:
        html = client.get("/transactions", headers={"Accept": "text/html"})
        assert html.status_code == 200
        assert "text/html" in html.headers["content-type"]
        assert "<div id=\"root\">" in html.text
        categories = client.get("/api/v1/categories")
        assert categories.status_code == 200
        assert isinstance(categories.json(), list)
        assert "content-security-policy" in html.headers
