"""
pscnet 爬蟲，負責抓取融資券日線資料。

支援標的：
  TWII  → afterHours-market0002-1（上市）
  TPEx  → afterHours-market0002-2（上櫃）

欄位對應：
  V1 = 日期（YYYY/MM/DD）
  V2 = 融資餘額（張）
  V3 = 融資金額（千元）
  V4 = 融券餘額（張）
  V5 = 融券金額（千元）
  V6 = 融資維持率（百分比，存入時除以 100）

用法：
  crawl(symbol="TWII", from_date=date(2008, 1, 1))  # 首次全歷史
  crawl(symbol="TWII")                               # 只抓今天
"""

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional, TypedDict

import httpx

from app.db.connection import db_conn


class MarginRow(TypedDict):
    symbol: str
    date: str
    margin_balance: Decimal
    margin_balance_amount: Decimal
    short_balance: Decimal
    short_balance_amount: Decimal
    margin_maintenance_ratio: Decimal
    margin_short_ratio: Optional[Decimal]


# (pscnet_code, url)
_SYMBOL_MAP: dict[str, tuple[str, str]] = {
    "TWII": (
        "afterHours-market0002-1",
        "https://pscnetsecrwd.moneydj.com/b2brwdCommon/jsondata/32/06/4a/twstockdata.xdjjson",
    ),
    "TPEx": (
        "afterHours-market0002-2",
        "https://pscnetsecrwd.moneydj.com/b2brwdCommon/jsondata/3a/b1/8d/twstockdata.xdjjson",
    ),
}

_HEADERS = {"Referer": "https://www.pscnet.com.tw/"}

# pscnet 同樣沒有「結束日期」參數：永遠是從今天往回抓 c 筆交易日，
# to_date 只用來事後篩選 upsert 範圍，不影響請求成本。回溯深度
# （today - from_date）才是決定 c 大小、進而決定耗時的因素。實測資料
# 最早：TWII 1999/05/19、TPEx 1999/04/01，9998 天涵蓋兩者並留緩衝。
_MAX_LOOKBACK_DAYS = 10_500


def crawl(
    symbol: str,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
) -> int:
    """
    下載融資券日線並 upsert 至 margin_data。

    from_date 預設今天；to_date 預設今天。
    回傳寫入筆數。
    """
    entry = _SYMBOL_MAP.get(symbol)
    if entry is None:
        raise ValueError(f"Unsupported symbol: {symbol}. Supported: {list(_SYMBOL_MAP)}")
    pscnet_code, url = entry

    today = date.today()
    start = from_date or today
    end = to_date or today

    # calendar days ≥ 交易日數，直接拿來當 c 已經足夠涵蓋 [start, today]
    lookback_days = (today - start).days + 1
    if lookback_days > _MAX_LOOKBACK_DAYS:
        raise ValueError(
            f"from_date too far in the past ({lookback_days} calendar days from today, "
            f"max {_MAX_LOOKBACK_DAYS}); pscnet history is limited, split into smaller requests"
        )
    count = max(1, lookback_days + 5)

    resp = httpx.get(
        url,
        params={"x": pscnet_code, "b": "d", "c": count, "revision": "2018_07_31_1"},
        headers=_HEADERS,
        timeout=30,
    )
    resp.raise_for_status()

    result = resp.json()["ResultSet"]["Result"]
    rows = _parse(result, symbol, start, end)
    return _upsert(rows)


def _parse(
    result: list[dict],
    symbol: str,
    start: date,
    end: date,
) -> list[MarginRow]:
    rows: list[MarginRow] = []
    for item in result:
        try:
            y, m, d_ = item["V1"].split("/")
            dt = date(int(y), int(m), int(d_))
        except (ValueError, KeyError):
            continue

        if not (start <= dt <= end):
            continue

        # 早期資料（如 2003 年附近）V6 等欄位常是空字串，Decimal("") 會拋
        # InvalidOperation；缺這些欄位的日期就跳過，不讓整批因單筆壞資料失敗。
        try:
            margin_balance = Decimal(item["V2"])
            short_balance = Decimal(item["V4"])
            margin_balance_amount = Decimal(item["V3"])
            short_balance_amount = Decimal(item["V5"])
            margin_maintenance_ratio = (Decimal(item["V6"]) / 100).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
        except (InvalidOperation, KeyError):
            continue

        ratio = (
            (margin_balance / short_balance).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            if short_balance != 0
            else None
        )

        rows.append(MarginRow(
            symbol=symbol,
            date=dt.isoformat(),
            margin_balance=margin_balance,
            margin_balance_amount=margin_balance_amount,
            short_balance=short_balance,
            short_balance_amount=short_balance_amount,
            margin_maintenance_ratio=margin_maintenance_ratio,
            margin_short_ratio=ratio,
        ))

    return rows


def _upsert(rows: list[MarginRow]) -> int:
    if not rows:
        return 0

    sql = """
        INSERT INTO margin_data (
            symbol, date,
            margin_balance, margin_balance_amount,
            short_balance, short_balance_amount,
            margin_maintenance_ratio, margin_short_ratio
        )
        VALUES (
            %(symbol)s, %(date)s,
            %(margin_balance)s, %(margin_balance_amount)s,
            %(short_balance)s, %(short_balance_amount)s,
            %(margin_maintenance_ratio)s, %(margin_short_ratio)s
        )
        ON CONFLICT (symbol, date) DO UPDATE SET
            margin_balance            = EXCLUDED.margin_balance,
            margin_balance_amount     = EXCLUDED.margin_balance_amount,
            short_balance             = EXCLUDED.short_balance,
            short_balance_amount      = EXCLUDED.short_balance_amount,
            margin_maintenance_ratio  = EXCLUDED.margin_maintenance_ratio,
            margin_short_ratio        = EXCLUDED.margin_short_ratio;
    """
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
        conn.commit()
    return len(rows)
