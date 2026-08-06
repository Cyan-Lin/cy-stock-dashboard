"""
T03 測試：POST /api/scrape

切面：
  1. 有效 symbol + 日期範圍 → 200，upserted >= 0
  2. 不支援的 symbol → 422
  3. MoneyDJ 回傳空資料 → 200，upserted = 0
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_TEST_SYMBOL = "TWII"
_FROM = "2024-04-01"
_TO = "2024-04-05"

# MoneyDJ 實際格式：5 個交易日
_MOCK_BODY = (
    "2024/04/01,2024/04/02,2024/04/03,2024/04/04,2024/04/05 "
    "100.00,103.00,106.00,105.00,108.00 "   # group0: Open
    "105.00,107.00,108.00,109.00,110.00 "   # group1: High
    "99.00,102.00,104.00,104.50,107.00 "    # group2: Low
    "103.00,106.00,105.00,108.00,109.00 "   # group3: Close
    "1000000,1100000,900000,1200000,800000 " # group4: Volume
    "0,0,0,0,0 0,0,0,0,0 0,0,0,0,0 0,0,0,0,0 0,0,0,0,0 0,0,0,0,0 0,0,0,0,0"
)


def _make_response(body: str, status_code: int = 200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.text = body
    mock.raise_for_status = MagicMock()
    return mock


@pytest.fixture(autouse=True)
def cleanup(conn):
    yield
    with conn.cursor() as cur:
        cur.execute("DELETE FROM daily_prices WHERE symbol = %s", (_TEST_SYMBOL,))


# ---------------------------------------------------------------------------
# 切面 1：正常爬取
# ---------------------------------------------------------------------------

def test_scrape_success():
    with patch("httpx.get", return_value=_make_response(_MOCK_BODY)):
        resp = client.post(
            "/api/scrape",
            json={"symbol": _TEST_SYMBOL, "from_date": _FROM, "to_date": _TO},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == _TEST_SYMBOL
    assert body["upserted"] == 5


# ---------------------------------------------------------------------------
# 切面 2：不支援的 symbol → 422
# ---------------------------------------------------------------------------

def test_scrape_invalid_symbol():
    resp = client.post("/api/scrape", json={"symbol": "INVALID"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 切面 3：MoneyDJ 回傳空資料 → upserted = 0
# ---------------------------------------------------------------------------

def test_scrape_empty_data():
    with patch("httpx.get", return_value=_make_response("2024/04/06")):
        resp = client.post(
            "/api/scrape",
            json={"symbol": _TEST_SYMBOL, "from_date": "2024-04-06", "to_date": "2024-04-06"},
        )
    assert resp.status_code == 200
    assert resp.json()["upserted"] == 0
