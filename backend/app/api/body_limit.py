"""JSON 413 envelope for oversized request bodies."""

from __future__ import annotations

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.errors import error_body

MAX_BODY_SIZE = 15 * 1024 * 1024


class _TooLarge(Exception):
    pass


class JsonBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_body_size: int = MAX_BODY_SIZE) -> None:
        self.app = app
        self.max_body_size = max_body_size

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            status_code=413,
            content=error_body("too_large", "PDF 15 MiB sınırını aşıyor"),
        )
        await response(scope, receive, send)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        raw_length = headers.get("content-length")
        if raw_length is not None:
            try:
                if int(raw_length) > self.max_body_size:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                pass
        total = 0

        async def limited_receive() -> Message:
            nonlocal total
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body") or b"")
                if total > self.max_body_size:
                    raise _TooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _TooLarge:
            await self._reject(scope, receive, send)
