"""
T03-followup 測試：moneydj_crawler.crawl()

Seam：crawl(symbol, from_date, to_date) → int
Mock 層：httpx.get，回傳 MoneyDJ 純文字格式
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.crawler import moneydj_crawler

# 用假 symbol 測試，避免污染真的 TWII/TPEx 資料（dev DB 跟測試共用）
_SYMBOL = "TEST_MONEYDJ"
_FROM = date(2024, 4, 1)
_TO = date(2024, 4, 3)


@pytest.fixture(autouse=True)
def _fake_symbol(monkeypatch):
    monkeypatch.setitem(moneydj_crawler._CODE_MAP, _SYMBOL, "TEST_CODE")

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


# ---------------------------------------------------------------------------
# 循環 5：from_date 回溯過深（today - from_date 超過上限）→ ValueError，不呼叫 httpx
# ---------------------------------------------------------------------------

def test_crawl_rejects_lookback_beyond_max():
    from app.crawler.moneydj_crawler import _MAX_LOOKBACK_DAYS, crawl

    too_old = date.today() - timedelta(days=_MAX_LOOKBACK_DAYS + 1)

    with patch("httpx.get") as mock_get:
        with pytest.raises(ValueError, match="too far in the past"):
            crawl(_SYMBOL, from_date=too_old)

    mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# 循環 6：count 依「今天 - from_date」計算，不受 to_date 影響
#         （回填舊區間時，即使 to_date 也很舊，仍要抓到足夠深度才能命中 from_date）
# ---------------------------------------------------------------------------

def test_crawl_count_based_on_lookback_from_today_not_window_width():
    from app.crawler.moneydj_crawler import crawl

    old_from = date.today() - timedelta(days=500)
    old_to = old_from + timedelta(days=3)  # 區間很窄，但離今天很遠

    with patch("httpx.get", return_value=_make_response(_EMPTY_BODY)) as mock_get:
        crawl(_SYMBOL, from_date=old_from, to_date=old_to)

    sent_count = mock_get.call_args.kwargs["params"]["C"]
    assert sent_count >= 500
