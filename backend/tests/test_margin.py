"""
T04 測試：TWSE 融資券爬蟲 + /api/margin
T10 測試：/api/margin interval 參數、億元/百分比換算、籌碼洗淨欄位

切面：
  1. _parse() 欄位對應正確（V1~V7 → MarginRow）
  2. _parse() 日期範圍篩選：超出範圍的筆數不回傳
  3. _upsert() idempotent（重複執行不產生重複資料）
  4. _upsert() margin_short_ratio 計算正確（margin_balance ÷ short_balance）
  5. GET /api/margin?symbol=TWII 回傳 200 + 正確欄位
  6. GET /api/margin 查無資料 → 404
  7. GET /api/margin from/to 篩選有效
  8. GET /api/margin margin_amount_100m 由 margin_balance_amount 換算（÷100000）
  9. GET /api/margin margin_maintenance_ratio 回傳百分比（非小數比率）
  10. GET /api/margin chip_washout：window 內無值為 null
  11. GET /api/margin chip_washout：日頻正確值（reuse evaluator.chip_washout）
  12. GET /api/margin?interval=weekly 取該週最後交易日的值（含 chip_washout）
  13. GET /api/margin?interval=monthly 取該月最後交易日的值（含 chip_washout）
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.crawler import pscnet_crawler
from app.crawler.pscnet_crawler import _parse, _upsert
from app.crawler.twse import upsert_prices
from app.main import app

client = TestClient(app)

_TEST_SYMBOL = "TEST_MARGIN"


@pytest.fixture(autouse=True)
def _fake_symbol(monkeypatch):
    monkeypatch.setitem(
        pscnet_crawler._SYMBOL_MAP, _TEST_SYMBOL, ("TEST_CODE", "https://example.invalid/test")
    )

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


def _make_margin_response(result: list[dict]):
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json = MagicMock(return_value={"ResultSet": {"Result": result}})
    return mock


# ---------------------------------------------------------------------------
# 切面 8：crawl() from_date 回溯過深（today - from_date 超過上限）→ ValueError，不呼叫 httpx
# ---------------------------------------------------------------------------

def test_crawl_rejects_lookback_beyond_max():
    from app.crawler.pscnet_crawler import _MAX_LOOKBACK_DAYS, crawl

    too_old = date.today() - timedelta(days=_MAX_LOOKBACK_DAYS + 1)

    with patch("httpx.get") as mock_get:
        with pytest.raises(ValueError, match="too far in the past"):
            crawl(_TEST_SYMBOL, from_date=too_old)

    mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# 切面 9：crawl() count 依「今天 - from_date」計算，不受 to_date 影響
# ---------------------------------------------------------------------------

def test_crawl_count_based_on_lookback_from_today_not_window_width():
    from app.crawler.pscnet_crawler import crawl

    old_from = date.today() - timedelta(days=500)
    old_to = old_from + timedelta(days=3)  # 區間很窄，但離今天很遠

    with patch("httpx.get", return_value=_make_margin_response([])) as mock_get:
        crawl(_TEST_SYMBOL, from_date=old_from, to_date=old_to)

    sent_count = mock_get.call_args.kwargs["params"]["c"]
    assert sent_count >= 500


# ---------------------------------------------------------------------------
# T10：/api/margin interval 參數、億元/百分比換算、籌碼洗淨欄位
#
# 25 天日頻資料（2024-04-01 起，剛好從週一開始）：
#   margin_balance_amount(t) = 100000 - 1000*t 千元  → margin_amount_100m(t) = 1 - 0.01*t 億元
#   close(t)                 = 100 - 0.5*t
#   margin_maintenance_ratio 固定 1.5000（小數比率）→ API 應回傳 150.0（百分比）
#
# chip_washout 只在 i >= window(20) 時有值：
#   t=20（2024-04-21，週三所在的那個 week bucket 最後交易日）：
#     margin_change = (80000-100000)/100000 = -0.2；price_change = (90-100)/100 = -0.1 → value = 2.0
#   t=24（2024-04-25，月 bucket 最後交易日）：
#     margin_change = (76000-96000)/96000 = -5/24；price_change = (88-98)/98 = -5/49 → value = 49/24 ≈ 2.041667
# ---------------------------------------------------------------------------

_CW_SYMBOL = "TEST_MARGIN_CW"


def _chip_washout_rows():
    margin_rows = []
    price_rows = []
    for t in range(25):
        d = (date(2024, 4, 1) + timedelta(days=t)).isoformat()
        margin_rows.append({
            "symbol": _CW_SYMBOL,
            "date": d,
            "margin_balance": Decimal("9000000"),
            "margin_balance_amount": Decimal(100000 - 1000 * t),
            "short_balance": Decimal("200000"),
            "short_balance_amount": Decimal("12000"),
            "margin_maintenance_ratio": Decimal("1.5000"),
            "margin_short_ratio": Decimal("45.0000"),
        })
        price_rows.append({
            "symbol": _CW_SYMBOL,
            "date": d,
            "open": Decimal("100.00"),
            "high": Decimal("100.00"),
            "low": Decimal("100.00"),
            "close": Decimal("100.0") - Decimal("0.5") * t,
            "volume": 1_000_000,
        })
    return margin_rows, price_rows


@pytest.fixture
def chip_washout_data(conn):
    margin_rows, price_rows = _chip_washout_rows()
    _upsert(margin_rows)
    upsert_prices(price_rows)
    yield
    with conn.cursor() as cur:
        cur.execute("DELETE FROM margin_data WHERE symbol = %s", (_CW_SYMBOL,))
        cur.execute("DELETE FROM daily_prices WHERE symbol = %s", (_CW_SYMBOL,))


def test_get_margin_amount_100m_conversion(chip_washout_data):
    resp = client.get("/api/margin", params={"symbol": _CW_SYMBOL, "limit": 25})
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["date"] == "2024-04-01")
    assert row["margin_amount_100m"] == pytest.approx(1.0)  # 100000 千元 / 100000


def test_get_margin_maintenance_ratio_is_percentage(chip_washout_data):
    resp = client.get("/api/margin", params={"symbol": _CW_SYMBOL, "limit": 25})
    data = resp.json()
    assert data[0]["margin_maintenance_ratio"] == pytest.approx(150.0)


def test_get_margin_chip_washout_null_before_window_fills(chip_washout_data):
    resp = client.get("/api/margin", params={"symbol": _CW_SYMBOL, "limit": 25})
    row = next(r for r in resp.json() if r["date"] == "2024-04-10")  # t=9 < window(20)
    assert row["chip_washout"] is None


def test_get_margin_chip_washout_daily_value(chip_washout_data):
    resp = client.get("/api/margin", params={"symbol": _CW_SYMBOL, "limit": 25})
    row = next(r for r in resp.json() if r["date"] == "2024-04-21")  # t=20
    assert row["chip_washout"] == pytest.approx(2.0, abs=0.0001)


def test_get_margin_weekly_uses_last_trading_day(chip_washout_data):
    resp = client.get("/api/margin", params={"symbol": _CW_SYMBOL, "interval": "weekly", "limit": 10})
    assert resp.status_code == 200
    data = resp.json()
    week = next(r for r in data if r["date"] == "2024-04-15")  # 週一開始，最後交易日是 2024-04-21 (t=20)
    assert week["chip_washout"] == pytest.approx(2.0, abs=0.0001)
    assert week["margin_amount_100m"] == pytest.approx(0.8)  # t=20 → 1 - 0.01*20


def test_get_margin_monthly_uses_last_trading_day(chip_washout_data):
    resp = client.get("/api/margin", params={"symbol": _CW_SYMBOL, "interval": "monthly", "limit": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    month = data[0]
    assert month["date"] == "2024-04-01"
    assert month["chip_washout"] == pytest.approx(49 / 24, abs=0.0001)  # 最後交易日 2024-04-25 (t=24)
    assert month["margin_amount_100m"] == pytest.approx(0.76)  # t=24 → 1 - 0.01*24
