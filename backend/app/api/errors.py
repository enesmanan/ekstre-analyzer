"""JSON error envelope for the HTTP API."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        issues: list[Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.issues = issues or []
        super().__init__(message)


def error_body(code: str, message: str, issues: list[Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "issues": issues or []}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.issues),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_body("validation_error", "Geçersiz istek", list(exc.errors())),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        if exc.status_code == 413:
            code = "too_large"
            message = "PDF 15 MiB sınırını aşıyor"
        elif exc.status_code == 404:
            code = "not_found"
            message = "Kayıt bulunamadı"
        else:
            code = "http_error"
            message = str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, message),
        )
