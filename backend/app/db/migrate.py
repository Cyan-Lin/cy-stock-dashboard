import os
from pathlib import Path

from .connection import get_connection

_MIGRATIONS_DIR = Path(__file__).parents[2] / "migrations"


def _record_applied(cur, filename: str) -> None:
    cur.execute(
        "INSERT INTO schema_migrations (filename) VALUES (%s);",
        (filename,),
    )


def run_migrations() -> None:
    conn = get_connection()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename   TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute("SELECT filename FROM schema_migrations;")
            applied = {row[0] for row in cur.fetchall()}

        # 每個 migration 檔案的 SQL 與追蹤紀錄寫入需視為同一個原子操作，
        # 否則中途失敗會讓 schema 已變更但 schema_migrations 沒記錄，下次重跑又執行一次。
        conn.autocommit = False
        for sql_file in sorted(_MIGRATIONS_DIR.glob("*.sql")):
            if sql_file.name in applied:
                continue
            sql = sql_file.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql)
                _record_applied(cur, sql_file.name)
            conn.commit()
    finally:
        conn.close()
