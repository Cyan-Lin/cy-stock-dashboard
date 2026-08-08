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
from decimal import Decimal, ROUND_HALF_UP
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

    calendar_days = (end - start).days + 1
    count = max(1, int(calendar_days * 1.5) + 5)

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

        margin_balance = Decimal(item["V2"])
        short_balance = Decimal(item["V4"])

        ratio = (
            (margin_balance / short_balance).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            if short_balance != 0
            else None
        )

        rows.append(MarginRow(
            symbol=symbol,
            date=dt.isoformat(),
            margin_balance=margin_balance,
            margin_balance_amount=Decimal(item["V3"]),
            short_balance=short_balance,
            short_balance_amount=Decimal(item["V5"]),
            margin_maintenance_ratio=(Decimal(item["V6"]) / 100).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            ),
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
