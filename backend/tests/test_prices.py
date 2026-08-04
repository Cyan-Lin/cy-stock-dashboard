"""
T03 測試：TWSE/yfinance 爬蟲 + /api/prices

切面：
  1. _twse_date_to_iso 民國年轉換正確
  2. fetch_month 解析 TWSE JSON、回傳正確欄位（mock HTTP）
  3. upsert_prices 寫入 DB 並可重複執行（idempotent）
  4. GET /api/prices?symbol=...&interval=daily 回傳 200 + 正確資料
  5. GET /api/prices 查無資料時回傳 404
  6. GET /api/prices from/to 篩選有效
  7. GET /api/prices?interval=weekly 回傳週線彙整（open/high/low/close/volume）
  8. GET /api/prices?interval=weekly 週線包含 ma60 欄位
  9. GET /api/prices?interval=monthly 回傳月線彙整
"""

from datetime import date
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient

from app.crawler.twse import (
    _twse_date_to_iso,
    fetch_month,
    upsert_prices,
)
from app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Fixture：插入跨週/跨月的測試行情資料，測試後清除
# ---------------------------------------------------------------------------

_TEST_SYMBOL = "9999"

# 2024-04-01（週一）~ 2024-04-05（週五）= 第一週
# 2024-04-08（週一）~ 2024-04-10（週三）= 第二週（不完整）
_SAMPLE_ROWS = [
    {"symbol": _TEST_SYMBOL, "date": "2024-04-01", "open": Decimal("100.00"), "high": Decimal("105.00"), "low": Decimal("99.00"),  "close": Decimal("103.00"), "volume": 1_000_000},
    {"symbol": _TEST_SYMBOL, "date": "2024-04-02", "open": Decimal("103.00"), "high": Decimal("107.00"), "low": Decimal("102.00"), "close": Decimal("106.00"), "volume": 1_100_000},
    {"symbol": _TEST_SYMBOL, "date": "2024-04-03", "open": Decimal("106.00"), "high": Decimal("108.00"), "low": Decimal("104.00"), "close": Decimal("105.00"), "volume": 900_000},
    {"symbol": _TEST_SYMBOL, "date": "2024-04-04", "open": Decimal("105.00"), "high": Decimal("109.00"), "low": Decimal("104.50"), "close": Decimal("108.00"), "volume": 1_200_000},
    {"symbol": _TEST_SYMBOL, "date": "2024-04-05", "open": Decimal("108.00"), "high": Decimal("110.00"), "low": Decimal("107.00"), "close": Decimal("109.00"), "volume": 800_000},
    {"symbol": _TEST_SYMBOL, "date": "2024-04-08", "open": Decimal("109.00"), "high": Decimal("112.00"), "low": Decimal("108.00"), "close": Decimal("111.00"), "volume": 1_300_000},
    {"symbol": _TEST_SYMBOL, "date": "2024-04-09", "open": Decimal("111.00"), "high": Decimal("113.00"), "low": Decimal("110.00"), "close": Decimal("112.00"), "volume": 1_400_000},
    {"symbol": _TEST_SYMBOL, "date": "2024-04-10", "open": Decimal("112.00"), "high": Decimal("115.00"), "low": Decimal("111.00"), "close": Decimal("114.00"), "volume": 1_500_000},
]


@pytest.fixture(autouse=True)
def seed_and_cleanup(conn):
    upsert_prices(_SAMPLE_ROWS)
    yield
    with conn.cursor() as cur:
        cur.execute("DELETE FROM daily_prices WHERE symbol = %s", (_TEST_SYMBOL,))


# ---------------------------------------------------------------------------
# 切面 1：民國年轉換
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("twse,expected", [
    ("113/04/01", "2024-04-01"),
    ("89/03/15",  "2000-03-15"),
    ("110/12/31", "2021-12-31"),
])
def test_twse_date_to_iso(twse, expected):
    assert _twse_date_to_iso(twse) == expected


# ---------------------------------------------------------------------------
# 切面 2：fetch_month mock HTTP
# ---------------------------------------------------------------------------

_MOCK_TWSE_BODY = {
    "stat": "OK",
    "data": [
        ["113/04/01", "1,000,000", "100,000,000", "100.00", "105.00", "99.00", "103.50", "+3.50", "5000"],
        ["113/04/02", "1,500,000", "162,000,000", "103.50", "110.00", "102.00", "108.00", "+4.50", "7000"],
    ],
}


def test_fetch_month_parses_response(monkeypatch):
    def _mock_get(url, **kwargs):
        resp = httpx.Response(200, json=_MOCK_TWSE_BODY)
        resp.request = httpx.Request("GET", url)
        return resp

    monkeypatch.setattr(httpx, "get", _mock_get)
    rows = fetch_month("9999", 2024, 4)

    assert len(rows) == 2
    assert rows[0]["symbol"] == "9999"
    assert rows[0]["date"] == "2024-04-01"
    assert rows[0]["open"] == Decimal("100.00")
    assert rows[0]["close"] == Decimal("103.50")
    assert rows[0]["volume"] == 1_000_000
    assert rows[1]["high"] == Decimal("110.00")


def test_fetch_month_returns_empty_on_non_ok(monkeypatch):
    def _mock_get(url, **kwargs):
        resp = httpx.Response(200, json={"stat": "查無資料"})
        resp.request = httpx.Request("GET", url)
        return resp

    monkeypatch.setattr(httpx, "get", _mock_get)
    assert fetch_month("0000", 2024, 1) == []


# ---------------------------------------------------------------------------
# 切面 3：upsert_prices idempotent
# ---------------------------------------------------------------------------

def test_upsert_prices_idempotent(conn):
    upsert_prices(_SAMPLE_ROWS)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM daily_prices WHERE symbol = %s", (_TEST_SYMBOL,))
        count = cur.fetchone()[0]
    assert count == len(_SAMPLE_ROWS)


# ---------------------------------------------------------------------------
# 切面 4：GET /api/prices?interval=daily 回傳資料
# ---------------------------------------------------------------------------

def test_get_prices_daily_returns_data():
    resp = client.get("/api/prices", params={"symbol": _TEST_SYMBOL, "interval": "daily"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == len(_SAMPLE_ROWS)
    assert data[0]["date"] > data[-1]["date"]   # ORDER BY date DESC


# ---------------------------------------------------------------------------
# 切面 5：查無資料 → 404
# ---------------------------------------------------------------------------

def test_get_prices_404_for_unknown_symbol():
    resp = client.get("/api/prices", params={"symbol": "XXXXX"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 切面 6：from / to 篩選
# ---------------------------------------------------------------------------

def test_get_prices_from_to_filter():
    resp = client.get(
        "/api/prices",
        params={"symbol": _TEST_SYMBOL, "from": "2024-04-08", "to": "2024-04-09"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    dates = {r["date"] for r in data}
    assert dates == {"2024-04-08", "2024-04-09"}


# ---------------------------------------------------------------------------
# 切面 7：interval=weekly 週線彙整
# ---------------------------------------------------------------------------

def test_get_prices_weekly_aggregation():
    resp = client.get("/api/prices", params={"symbol": _TEST_SYMBOL, "interval": "weekly"})
    assert resp.status_code == 200
    data = resp.json()

    # 8 日資料橫跨 2 週
    assert len(data) == 2

    # 找第一週（ORDER BY date DESC，所以 data[-1] 是較早的）
    week1 = next(r for r in data if r["date"] == "2024-04-01")

    # open 取週一（2024-04-01）開盤
    assert week1["open"] == pytest.approx(100.00)
    # close 取週五（2024-04-05）收盤
    assert week1["close"] == pytest.approx(109.00)
    # high 取週內極值
    assert week1["high"] == pytest.approx(110.00)
    # low 取週內極值
    assert week1["low"] == pytest.approx(99.00)
    # volume 加總
    assert week1["volume"] == 1_000_000 + 1_100_000 + 900_000 + 1_200_000 + 800_000


# ---------------------------------------------------------------------------
# 切面 8：週線包含 ma60
# ---------------------------------------------------------------------------

def test_get_prices_weekly_has_ma60():
    resp = client.get("/api/prices", params={"symbol": _TEST_SYMBOL, "interval": "weekly"})
    assert resp.status_code == 200
    data = resp.json()
    # ma60 欄位存在（資料不足 60 週時為非 None 的部分平均值）
    for bar in data:
        assert "ma60" in bar


# ---------------------------------------------------------------------------
# 切面 9：interval=monthly 月線彙整
# ---------------------------------------------------------------------------

def test_get_prices_monthly_aggregation():
    resp = client.get("/api/prices", params={"symbol": _TEST_SYMBOL, "interval": "monthly"})
    assert resp.status_code == 200
    data = resp.json()

    # 8 日全部在 2024-04，彙整為 1 筆
    assert len(data) == 1
    bar = data[0]
    assert bar["date"] == "2024-04-01"
    assert bar["open"] == pytest.approx(100.00)   # 月內第一日開盤
    assert bar["close"] == pytest.approx(114.00)  # 月內最後日收盤
    assert bar["high"] == pytest.approx(115.00)
    assert bar["low"] == pytest.approx(99.00)
