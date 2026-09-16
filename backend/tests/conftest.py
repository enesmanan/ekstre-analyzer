from __future__ import annotations

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config


def upgrade_db(path: Path) -> None:
    ini = Path(__file__).resolve().parents[1] / "app" / "db" / "alembic.ini"
    cfg = Config(str(ini))
    cfg.cmd_opts = argparse.Namespace(x=[f"db={path.resolve()}"])
    command.upgrade(cfg, "head")
