"""
T07 測試：Alert Store（DB 寫入與查詢）

所有測試連本機 Docker db（透過 conftest.py 的 conn fixture）。

切面：
  1. save_alert_events 寫入正確欄位
  2. save_alert_events 冪等性（同日同類型不重複寫入）
  3. save_alert_events 空清單不寫入，不報錯
  4. evaluate_and_save 對 TWII 跑完整評估並寫入
  5. evaluate_and_save 無資料時不報錯
"""

import pytest
import psycopg2.extras

from app.alerts.store import evaluate_and_save, save_alert_events


# ---------------------------------------------------------------------------
# 輔助
# ---------------------------------------------------------------------------

def _clean(conn, symbol: str) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM alert_events WHERE symbol = %s", (symbol,))


def _count(conn, symbol: str) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM alert_events WHERE symbol = %s", (symbol,))
        return cur.fetchone()[0]


def _fetch_all(conn, symbol: str) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT symbol, alert_type, date, details FROM alert_events WHERE symbol = %s ORDER BY date",
            (symbol,),
        )
        return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# 切面 1：寫入正確欄位
# ---------------------------------------------------------------------------

def test_save_alert_events_inserts_row(conn):
    _clean(conn, "__test__")
    events = [{"alert_type": "margin_drop_25", "date": "2024-01-02", "details": {"drop_pct": 0.25}}]
    save_alert_events(conn, "__test__", events)
    rows = _fetch_all(conn, "__test__")
    assert len(rows) == 1
    r = rows[0]
    assert r["symbol"] == "__test__"
    assert r["alert_type"] == "margin_drop_25"
    assert str(r["date"]) == "2024-01-02"
    assert r["details"]["drop_pct"] == pytest.approx(0.25)
    _clean(conn, "__test__")


# ---------------------------------------------------------------------------
# 切面 2：冪等性（同日同類型不重複）
# ---------------------------------------------------------------------------

def test_save_alert_events_idempotent(conn):
    _clean(conn, "__test__")
    events = [{"alert_type": "margin_drop_25", "date": "2024-01-02", "details": {}}]
    save_alert_events(conn, "__test__", events)
    save_alert_events(conn, "__test__", events)  # 第二次呼叫
    assert _count(conn, "__test__") == 1
    _clean(conn, "__test__")


def test_save_alert_events_different_types_same_day(conn):
    _clean(conn, "__test__")
    events = [
        {"alert_type": "margin_drop_25", "date": "2024-01-02", "details": {}},
        {"alert_type": "margin_drop_50", "date": "2024-01-02", "details": {}},
    ]
    save_alert_events(conn, "__test__", events)
    assert _count(conn, "__test__") == 2
    _clean(conn, "__test__")


# ---------------------------------------------------------------------------
# 切面 3：空清單
# ---------------------------------------------------------------------------

def test_save_alert_events_empty_list(conn):
    _clean(conn, "__test__")
    save_alert_events(conn, "__test__", [])
    assert _count(conn, "__test__") == 0


# ---------------------------------------------------------------------------
# 切面 4：evaluate_and_save 對 TWII 執行（需 DB 有資料）
# ---------------------------------------------------------------------------

def test_evaluate_and_save_twii_no_crash(conn):
    """有無資料都不應拋出例外；若有資料，alert_events 寫入筆數 >= 0。"""
    _clean(conn, "TWII")
    evaluate_and_save("TWII")  # 不報錯即通過


# ---------------------------------------------------------------------------
# 切面 5：evaluate_and_save 無資料時不報錯
# ---------------------------------------------------------------------------

def test_evaluate_and_save_unknown_symbol_no_crash(conn):
    _clean(conn, "__no_such__")
    evaluate_and_save("__no_such__")
    assert _count(conn, "__no_such__") == 0
    _clean(conn, "__no_such__")
