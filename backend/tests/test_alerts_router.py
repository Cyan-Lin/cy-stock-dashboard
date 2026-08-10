"""
T07 測試：GET /api/alerts 路由

切面：
  1. 有警示時回傳正確結構
  2. 指定 symbol 只回傳該 symbol 的資料
  3. 無資料時回傳空清單（不是 404）
  4. 缺少 symbol 參數回傳 422
"""

import json
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SYM = "__alert_test__"


@pytest.fixture(autouse=True)
def seed_and_clean(conn):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM alert_events WHERE symbol = %s", (SYM,))
        cur.execute(
            """
            INSERT INTO alert_events (symbol, alert_type, date, details)
            VALUES (%s, 'margin_drop_25', '2024-06-01', %s)
            """,
            (SYM, json.dumps({"drop_pct": 0.25})),
        )
    yield
    with conn.cursor() as cur:
        cur.execute("DELETE FROM alert_events WHERE symbol = %s", (SYM,))


# ---------------------------------------------------------------------------
# 切面 1：有警示時回傳正確結構
# ---------------------------------------------------------------------------

def test_get_alerts_returns_list(conn):
    resp = client.get(f"/api/alerts?symbol={SYM}")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    item = data[0]
    assert item["symbol"] == SYM
    assert item["alert_type"] == "margin_drop_25"
    assert item["date"] == "2024-06-01"
    assert "details" in item


# ---------------------------------------------------------------------------
# 切面 2：只回傳指定 symbol
# ---------------------------------------------------------------------------

def test_get_alerts_filters_by_symbol(conn):
    resp = client.get("/api/alerts?symbol=__other__")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# 切面 3：無資料時回傳空清單
# ---------------------------------------------------------------------------

def test_get_alerts_empty_when_no_data(conn):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM alert_events WHERE symbol = %s", (SYM,))
    resp = client.get(f"/api/alerts?symbol={SYM}")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# 切面 4：缺少 symbol 參數回傳 422
# ---------------------------------------------------------------------------

def test_get_alerts_missing_symbol_returns_422():
    resp = client.get("/api/alerts")
    assert resp.status_code == 422
