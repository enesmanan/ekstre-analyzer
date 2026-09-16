"""SQLite engine factory. No engine at import time."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def sqlite_url(path: Path | str) -> str:
    resolved = Path(path).resolve()
    return "sqlite:///" + resolved.as_posix()


def make_engine(path: Path | str) -> Engine:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        sqlite_url(path),
        connect_args={"autocommit": False, "check_same_thread": False, "timeout": 30.0},
    )

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
        dbapi_connection.autocommit = True
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()
        dbapi_connection.autocommit = False

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
