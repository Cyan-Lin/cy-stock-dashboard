"""
T03 測試：POST /api/scrape

切面：
  1. 有效 symbol + 日期範圍 → 200，upserted >= 0
  2. 不支援的 symbol → 422
  3. yfinance 回傳空資料 → 200，upserted = 0
"""

from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_TEST_SYMBOL = "TWII"
_FROM = "2024-04-01"
_TO = "2024-04-05"

# 模擬 yfinance 回傳的 DataFrame（5 個交易日）
def _mock_df():
    idx = pd.to_datetime(["2024-04-01", "2024-04-02", "2024-04-03", "2024-04-04", "2024-04-05"])
    return pd.DataFrame(
        {
            "Open":   [100.0, 103.0, 106.0, 105.0, 108.0],
            "High":   [105.0, 107.0, 108.0, 109.0, 110.0],
            "Low":    [99.0,  102.0, 104.0, 104.5, 107.0],
            "Close":  [103.0, 106.0, 105.0, 108.0, 109.0],
            "Volume": [1_000_000, 1_100_000, 900_000, 1_200_000, 800_000],
        },
        index=idx,
    )


@pytest.fixture(autouse=True)
def cleanup(conn):
    yield
    with conn.cursor() as cur:
        cur.execute("DELETE FROM daily_prices WHERE symbol = %s", (_TEST_SYMBOL,))


# ---------------------------------------------------------------------------
# 切面 1：正常爬取
# ---------------------------------------------------------------------------

def test_scrape_success():
    with patch("app.crawler.yfinance_crawler.yf.download", return_value=_mock_df()):
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
# 切面 3：yfinance 回傳空資料 → upserted = 0
# ---------------------------------------------------------------------------

def test_scrape_empty_data():
    with patch("app.crawler.yfinance_crawler.yf.download", return_value=pd.DataFrame()):
        resp = client.post(
            "/api/scrape",
            json={"symbol": _TEST_SYMBOL, "from_date": _FROM, "to_date": _TO},
        )
    assert resp.status_code == 200
    assert resp.json()["upserted"] == 0
