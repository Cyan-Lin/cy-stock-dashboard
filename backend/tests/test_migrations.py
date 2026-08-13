import pytest
from app.db import migrate
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


# --- 切面 5：schema_migrations 已記錄的檔案不會重跑（版本追蹤）---

def test_already_applied_migration_is_not_rerun(tmp_path, monkeypatch, conn):
    fake_migration = tmp_path / "999_side_effect.sql"
    fake_migration.write_text(
        "CREATE TABLE IF NOT EXISTS side_effect_counter (id SERIAL PRIMARY KEY);\n"
        "INSERT INTO side_effect_counter DEFAULT VALUES;\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(migrate, "_MIGRATIONS_DIR", tmp_path)

    try:
        run_migrations()
        run_migrations()

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM side_effect_counter;")
            (count,) = cur.fetchone()
            assert count == 1

            cur.execute(
                "SELECT applied_at FROM schema_migrations WHERE filename = %s;",
                (fake_migration.name,),
            )
            assert cur.fetchone() is not None
    finally:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS side_effect_counter;")
            cur.execute(
                "DELETE FROM schema_migrations WHERE filename = %s;",
                (fake_migration.name,),
            )


# --- 切面 6：migration SQL 與追蹤紀錄寫入為同一筆交易，失敗時一起回滾 ---

def test_migration_rolls_back_if_tracking_insert_fails(tmp_path, monkeypatch, conn):
    fake_migration = tmp_path / "999_atomic.sql"
    fake_migration.write_text(
        "CREATE TABLE IF NOT EXISTS atomic_side_effect (id SERIAL PRIMARY KEY);\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(migrate, "_MIGRATIONS_DIR", tmp_path)

    def failing_record_applied(cur, filename):
        raise RuntimeError("boom")

    monkeypatch.setattr(migrate, "_record_applied", failing_record_applied)

    try:
        with pytest.raises(RuntimeError):
            run_migrations()

        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('atomic_side_effect');")
            (table_oid,) = cur.fetchone()
            assert table_oid is None
    finally:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS atomic_side_effect;")
