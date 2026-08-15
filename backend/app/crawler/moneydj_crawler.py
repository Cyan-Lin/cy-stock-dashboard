"""
MoneyDJ 爬蟲，負責抓取指數日線資料。

支援標的：
  TWII  → MoneyDJ code EB09999（加權指數，1998 年起）
  TPEx  → MoneyDJ code EB18888（上櫃指數，1998 年起）

用法：
  crawl(symbol="TWII", from_date=date(2000, 1, 1))  # 首次全歷史
  crawl(symbol="TWII")                               # 只抓今天
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, TypedDict

import httpx

from app.db.connection import db_conn


class DailyBar(TypedDict):
    symbol: str
    date: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


def _to_decimal(s: str) -> Decimal:
    return Decimal(str(round(float(s), 2)))

_CODE_MAP = {
    "TWII": "EB09999",
    "TPEx": "EB18888",
}

_BASE_URL = "https://www.moneydj.com/Z/ZB/ZBH/CZKC0.djbcd"
_HEADERS = {"Referer": "https://www.moneydj.com/"}

# MoneyDJ 沒有「結束日期」參數：永遠是從今天往回抓 C 筆交易日，
# to_date 只用來事後篩選，不影響請求成本。回溯深度（today - from_date）
# 才是決定 C 大小、進而決定耗時的因素。超過此深度直接拒絕，避免單次
# 請求過大導致逾時。實測 MoneyDJ 資料最早：EB09999(TWII) 1987/01/06、
# EB18888(TPEx) 1996/01/17，14466 天涵蓋兩者並留一點緩衝。
_MAX_LOOKBACK_DAYS = 15_000


def crawl(
    symbol: str,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> int:
    """
    下載指數日線並 upsert 至 daily_prices。

    from_date 預設今天；to_date 預設今天。
    回傳寫入筆數。
    """
    code = _CODE_MAP.get(symbol)
    if code is None:
        raise ValueError(f"Unsupported symbol: {symbol}. Supported: {list(_CODE_MAP)}")

    today = date.today()
    start = from_date or today
    end = to_date or today

    # calendar days ≥ 交易日數，直接拿來當 C 已經足夠涵蓋 [start, today]
    lookback_days = (today - start).days + 1
    if lookback_days > _MAX_LOOKBACK_DAYS:
        raise ValueError(
            f"from_date too far in the past ({lookback_days} calendar days from today, "
            f"max {_MAX_LOOKBACK_DAYS}); MoneyDJ history is limited, split into smaller requests"
        )
    count = max(1, lookback_days + 5)

    resp = httpx.get(
        _BASE_URL,
        params={"A": code, "B": "D", "C": count, "ver": "5"},
        headers=_HEADERS,
        timeout=90,
    )
    resp.raise_for_status()

    rows = _parse(resp.text, symbol, start, end)
    return _upsert(rows)


def _parse(text: str, symbol: str, start: date, end: date) -> list[DailyBar]:
    """
    解析 MoneyDJ 純文字回應，篩選 [start, end] 範圍內的資料。

    實際回傳格式（一行純文字，空白分隔）：
      <日期列> <group0> <group1> ... <group11>

      - 日期列：YYYY/MM/DD 逗號分隔，共 C 個日期
      - 12 個 group，每組內是「同一欄位所有日期的值」（逗號分隔）
        group0=Open, group1=High, group2=Low, group3=Close, group4=Volume
        group5~11 為其他資料，不使用

    範例（C=3）：
      "2026/08/04,2026/08/05,2026/08/06
       43092.49,43809.83,44487.94       ← group0 Open  (day1, day2, day3)
       43912.77,44980.31,44601.24       ← group1 High
       42895.81,43809.83,44024.32       ← group2 Low
       43360.66,44611.6,44396.7         ← group3 Close
       1086278,1199237,973200           ← group4 Volume
       ..."

    非交易日：API 只回傳日期列，無後續 group（len(parts) < 2）→ 回傳 []。
    """
    text = text.strip()
    if not text:
        return []

    parts = text.split(" ", 1)
    dates_str = parts[0]
    # 日期格式：YYYY/MM/DD
    raw_dates = [d.strip() for d in dates_str.split(",") if d.strip()]

    if len(parts) < 2:
        return []

    # 5 個欄位群組：Open, High, Low, Close, Volume
    field_groups = parts[1].split()
    if len(field_groups) < 5:
        return []

    opens  = field_groups[0].split(",")
    highs  = field_groups[1].split(",")
    lows   = field_groups[2].split(",")
    closes = field_groups[3].split(",")
    vols   = field_groups[4].split(",")

    rows = []
    for i, raw_date in enumerate(raw_dates):
        if i >= len(opens):
            break

        try:
            y, m, d_ = raw_date.split("/")
            dt = date(int(y), int(m), int(d_))
        except (ValueError, AttributeError):
            continue

        if not (start <= dt <= end):
            continue

        try:
            rows.append(DailyBar(
                symbol=symbol,
                date=dt.isoformat(),
                open=_to_decimal(opens[i]),
                high=_to_decimal(highs[i]),
                low=_to_decimal(lows[i]),
                close=_to_decimal(closes[i]),
                volume=int(float(vols[i])),
            ))
        except (ValueError, IndexError):
            continue

    return rows


def _upsert(rows: list[DailyBar]) -> int:
    if not rows:
        return 0

    sql = """
        INSERT INTO daily_prices (symbol, date, open, high, low, close, volume)
        VALUES (%(symbol)s, %(date)s, %(open)s, %(high)s, %(low)s, %(close)s, %(volume)s)
        ON CONFLICT (symbol, date) DO UPDATE SET
            open   = EXCLUDED.open,
            high   = EXCLUDED.high,
            low    = EXCLUDED.low,
            close  = EXCLUDED.close,
            volume = EXCLUDED.volume;
    """
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
        conn.commit()
    return len(rows)
