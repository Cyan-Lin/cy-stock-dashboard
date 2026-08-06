"""
T03-followup 測試：moneydj_crawler.crawl()

Seam：crawl(symbol, from_date, to_date) → int
Mock 層：httpx.get，回傳 MoneyDJ 純文字格式
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

_SYMBOL = "TWII"
_FROM = date(2024, 4, 1)
_TO = date(2024, 4, 3)

# MoneyDJ 實際格式：日期列（YYYY/MM/DD）後接 12 個 group
# 每個 group = 同一欄位所有日期的值（逗號分隔）
# group0=Open, group1=High, group2=Low, group3=Close, group4=Volume
# 3 筆資料，日期 2024-04-01 ~ 2024-04-03
_MOCK_BODY = (
    "2024/04/01,2024/04/02,2024/04/03 "
    "100.00,103.00,106.00 "   # group0: Open
    "105.00,107.00,108.00 "   # group1: High
    "99.00,102.00,104.00 "    # group2: Low
    "103.00,106.00,105.00 "   # group3: Close
    "1000000,1100000,900000 " # group4: Volume
    "0,0,0 0,0,0 0,0,0 0,0,0 0,0,0 0,0,0 0,0,0"  # group5~11: 不使用
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
        cur.execute("DELETE FROM daily_prices WHERE symbol = %s", (_SYMBOL,))


# ---------------------------------------------------------------------------
# 循環 1：正常爬取 3 筆，回傳 3
# ---------------------------------------------------------------------------

def test_crawl_returns_upserted_count():
    from app.crawler.moneydj_crawler import crawl

    with patch("httpx.get", return_value=_make_response(_MOCK_BODY)):
        count = crawl(_SYMBOL, from_date=_FROM, to_date=_TO)

    assert count == 3


# ---------------------------------------------------------------------------
# 循環 2：欄位對應正確（open/high/low/close/volume）
# ---------------------------------------------------------------------------

def test_crawl_field_mapping(conn):
    from app.crawler.moneydj_crawler import crawl

    with patch("httpx.get", return_value=_make_response(_MOCK_BODY)):
        crawl(_SYMBOL, from_date=_FROM, to_date=_TO)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT open, high, low, close, volume FROM daily_prices "
            "WHERE symbol = %s AND date = %s",
            (_SYMBOL, "2024-04-01"),
        )
        row = cur.fetchone()

    assert row is not None
    open_, high, low, close, volume = row
    assert open_ == Decimal("100.00")
    assert high == Decimal("105.00")
    assert low == Decimal("99.00")
    assert close == Decimal("103.00")
    assert volume == 1_000_000


# ---------------------------------------------------------------------------
# 循環 3：空回應（非交易日）→ 回傳 0，不拋例外
# ---------------------------------------------------------------------------

# MoneyDJ 在非交易日回傳只有日期列，無後續 group
_EMPTY_BODY = "2024/04/06"


def test_crawl_empty_response():
    from app.crawler.moneydj_crawler import crawl

    with patch("httpx.get", return_value=_make_response(_EMPTY_BODY)):
        count = crawl(_SYMBOL, from_date=date(2024, 4, 6), to_date=date(2024, 4, 6))

    assert count == 0


# ---------------------------------------------------------------------------
# 循環 4：不支援的 symbol → ValueError
# ---------------------------------------------------------------------------

def test_crawl_unsupported_symbol():
    from app.crawler.moneydj_crawler import crawl

    with pytest.raises(ValueError, match="Unsupported symbol"):
        crawl("INVALID")
