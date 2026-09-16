"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.db.models import User


def get_db(request: Request) -> Generator[Session, None, None]:
    factory = request.app.state.session_factory
    session = factory()
    try:
        yield session
    finally:
        session.close()


def get_current_user(db: Session = Depends(get_db)) -> User:
    user = db.get(User, 1)
    if user is None:
        raise ApiError(500, "not_found", "dev user missing")
    return user


def require_not_maintenance(request: Request) -> None:
    if request.app.state.maintenance:
        raise ApiError(503, "maintenance", "Bakım nedeniyle yazma kapalı")
