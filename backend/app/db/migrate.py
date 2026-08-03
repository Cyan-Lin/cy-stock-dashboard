import os
from pathlib import Path

from .connection import get_connection

_MIGRATIONS_DIR = Path(__file__).parents[2] / "migrations"


def run_migrations() -> None:
    conn = get_connection()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            for sql_file in sorted(_MIGRATIONS_DIR.glob("*.sql")):
                sql = sql_file.read_text(encoding="utf-8")
                cur.execute(sql)
    finally:
        conn.close()
