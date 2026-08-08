"""
T04 測試：TWSE 融資券爬蟲 + /api/margin

切面：
  1. _parse() 欄位對應正確（V1~V7 → MarginRow）
  2. _parse() 日期範圍篩選：超出範圍的筆數不回傳
  3. _upsert() idempotent（重複執行不產生重複資料）
  4. _upsert() margin_short_ratio 計算正確（margin_balance ÷ short_balance）
  5. GET /api/margin?symbol=TWII 回傳 200 + 正確欄位
  6. GET /api/margin 查無資料 → 404
  7. GET /api/margin from/to 篩選有效
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.crawler.pscnet_crawler import _parse, _upsert
from app.main import app

client = TestClient(app)

_TEST_SYMBOL = "TEST_MARGIN"

_MOCK_RESULT = [
    {"V1": "2024/04/03", "V2": "9000000", "V3": "54000000", "V4": "200000", "V5": "12000", "V6": "180.00", "V7": "43000.0"},
    {"V1": "2024/04/02", "V2": "8800000", "V3": "52000000", "V4": "190000", "V5": "11000", "V6": "175.50", "V7": "42500.0"},
    {"V1": "2024/04/01", "V2": "8600000", "V3": "50000000", "V4": "180000", "V5": "10000", "V6": "170.00", "V7": "42000.0"},
]


@pytest.fixture(autouse=True)
def cleanup(conn):
    yield
    with conn.cursor() as cur:
        cur.execute("DELETE FROM margin_data WHERE symbol = %s", (_TEST_SYMBOL,))


# ---------------------------------------------------------------------------
# 切面 1：_parse() 欄位對應
# ---------------------------------------------------------------------------

def test_parse_field_mapping():
    rows = _parse(_MOCK_RESULT, _TEST_SYMBOL, date(2024, 4, 1), date(2024, 4, 3))

    assert len(rows) == 3
    r = rows[0]  # 最新一筆 (2024-04-03)
    assert r["symbol"] == _TEST_SYMBOL
    assert r["date"] == "2024-04-03"
    assert r["margin_balance"] == Decimal("9000000")
    assert r["margin_balance_amount"] == Decimal("54000000")
    assert r["short_balance"] == Decimal("200000")
    assert r["short_balance_amount"] == Decimal("12000")
    assert r["margin_maintenance_ratio"] == Decimal("1.8000")   # 180.00 / 100


# ---------------------------------------------------------------------------
# 切面 2：_parse() 日期範圍篩選
# ---------------------------------------------------------------------------

def test_parse_date_range_filter():
    rows = _parse(_MOCK_RESULT, _TEST_SYMBOL, date(2024, 4, 2), date(2024, 4, 2))
    assert len(rows) == 1
    assert rows[0]["date"] == "2024-04-02"


# ---------------------------------------------------------------------------
# 切面 3：_upsert() idempotent
# ---------------------------------------------------------------------------

def test_upsert_idempotent(conn):
    rows = _parse(_MOCK_RESULT, _TEST_SYMBOL, date(2024, 4, 1), date(2024, 4, 3))
    _upsert(rows)
    _upsert(rows)  # 第二次 upsert

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM margin_data WHERE symbol = %s", (_TEST_SYMBOL,))
        count = cur.fetchone()[0]
    assert count == 3


# ---------------------------------------------------------------------------
# 切面 4：margin_short_ratio 計算正確
# ---------------------------------------------------------------------------

def test_upsert_margin_short_ratio(conn):
    rows = _parse(_MOCK_RESULT, _TEST_SYMBOL, date(2024, 4, 3), date(2024, 4, 3))
    _upsert(rows)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT margin_short_ratio FROM margin_data WHERE symbol = %s AND date = '2024-04-03'",
            (_TEST_SYMBOL,),
        )
        ratio = cur.fetchone()[0]
    # 9000000 / 200000 = 45.0000
    assert float(ratio) == pytest.approx(45.0, abs=0.0001)


# ---------------------------------------------------------------------------
# 切面 5：GET /api/margin 回傳 200 + 正確欄位
# ---------------------------------------------------------------------------

def test_get_margin_returns_data(conn):
    rows = _parse(_MOCK_RESULT, _TEST_SYMBOL, date(2024, 4, 1), date(2024, 4, 3))
    _upsert(rows)

    resp = client.get("/api/margin", params={"symbol": _TEST_SYMBOL})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3

    r = data[0]  # ORDER BY date DESC → 最新在前
    assert r["date"] == "2024-04-03"
    assert "margin_balance" in r
    assert "margin_balance_amount" in r
    assert "short_balance" in r
    assert "short_balance_amount" in r
    assert "margin_maintenance_ratio" in r
    assert "margin_short_ratio" in r


# ---------------------------------------------------------------------------
# 切面 6：查無資料 → 404
# ---------------------------------------------------------------------------

def test_get_margin_404_for_unknown_symbol():
    resp = client.get("/api/margin", params={"symbol": "XXXXX"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 切面 7：from / to 篩選
# ---------------------------------------------------------------------------

def test_get_margin_from_to_filter(conn):
    rows = _parse(_MOCK_RESULT, _TEST_SYMBOL, date(2024, 4, 1), date(2024, 4, 3))
    _upsert(rows)

    resp = client.get(
        "/api/margin",
        params={"symbol": _TEST_SYMBOL, "from": "2024-04-02", "to": "2024-04-02"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["date"] == "2024-04-02"
