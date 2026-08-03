import pytest
from app.db.migrate import run_migrations


EXPECTED_TABLES = {
    "daily_prices",
    "margin_data",
    "alert_events",
    "national_fund_entries",
    "etf_margin_ratio",
}


def _get_tables(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public';"
        )
        return {row[0] for row in cur.fetchall()}


# --- 切面 1：執行後 5 張資料表存在 ---

def test_all_tables_created_after_migration(conn):
    run_migrations()
    assert EXPECTED_TABLES <= _get_tables(conn)


# --- 切面 2：可重複執行不報錯（idempotent）---

def test_run_migrations_is_idempotent(conn):
    run_migrations()
    run_migrations()  # 第二次不應拋出任何例外


# --- 切面 3：national_fund_entries 恰好 9 筆，最早 entry_date = 2000-03-15 ---

def test_national_fund_entries_seed(conn):
    run_migrations()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*), MIN(entry_date) FROM national_fund_entries;")
        count, earliest = cur.fetchone()
    assert count == 9
    assert str(earliest) == "2000-03-15"


# --- 切面 4：etf_margin_ratio TWII=0.6、TPEx=0.6 ---

def test_etf_margin_ratio_seed(conn):
    run_migrations()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT symbol, ratio FROM etf_margin_ratio ORDER BY symbol;"
        )
        rows = {row[0]: float(row[1]) for row in cur.fetchall()}
    assert rows == {"TPEx": 0.6, "TWII": 0.6}
