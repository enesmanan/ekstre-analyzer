"""FastAPI application. Engine is opened in lifespan, never at import."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api.errors import register_exception_handlers
from app.config import settings
from app.db.session import make_engine, make_session_factory

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self'; "
    "font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if request.app.state.env == "prod":
            response.headers["Content-Security-Policy"] = CSP
        return response


def create_app(
    *,
    database_path: Path | str | None = None,
    maintenance: bool | None = None,
    env: str | None = None,
) -> FastAPI:
    db_path = Path(database_path) if database_path is not None else Path(settings.database_url)
    maint = settings.maintenance if maintenance is None else maintenance
    app_env = settings.env if env is None else env

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(db_path)
        app.state.engine = engine
        app.state.session_factory = make_session_factory(engine)
        restart = getattr(app.state, "mark_restart", None)
        if callable(restart):
            restart(engine)
        yield
        engine.dispose()

    application = FastAPI(
        title="Ekstre Analyzer",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.state.maintenance = maint
    application.state.env = app_env
    application.state.database_path = db_path
    register_exception_handlers(application)
    application.add_middleware(SecurityHeadersMiddleware)

    @application.get("/api/healthz")
    def healthz(request: Request) -> JSONResponse:
        with request.app.state.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return JSONResponse({"ok": True})

    application.frontend(
        "/",
        directory=STATIC_DIR,
        fallback="index.html",
        check_dir=False,
    )
    return application


app = create_app()
