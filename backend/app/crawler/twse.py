"""
TWSE 月 K 線爬蟲。

呼叫 TWSE 公開 API 取得指定股票、指定月份的每日收盤資料，
並以 INSERT … ON CONFLICT DO UPDATE 寫入 daily_prices。

TWSE 端點：
  https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY
  ?stockNo=<symbol>&date=<YYYYMMDD01>&response=json

欄位順序（Data 陣列每列）：
  0 日期、1 成交股數、2 成交金額、3 開盤價、4 最高價、5 最低價、
  6 收盤價、7 漲跌價差、8 成交筆數
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

import httpx

from app.db.connection import db_conn

_TWSE_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
_TIMEOUT = 15.0


def _to_decimal(raw: str) -> Optional[Decimal]:
    cleaned = raw.replace(",", "").strip()
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _to_int(raw: str) -> Optional[int]:
    cleaned = raw.replace(",", "").strip()
    try:
        return int(cleaned)
    except ValueError:
        return None


def _twse_date_to_iso(twse_date: str) -> str:
    """民國年日期（113/04/01）→ ISO（2024-04-01）"""
    parts = twse_date.split("/")
    year = int(parts[0]) + 1911
    return f"{year}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"


def fetch_month(symbol: str, year: int, month: int) -> list[dict]:
    """向 TWSE 抓單月資料，回傳 list[dict]（OHLCV）。"""
    date_param = f"{year}{month:02d}01"
    resp = httpx.get(
        _TWSE_URL,
        params={"stockNo": symbol, "date": date_param, "response": "json"},
        timeout=_TIMEOUT,
        headers={"User-Agent": "cy-stock-dashboard/1.0"},
    )
    resp.raise_for_status()
    body = resp.json()

    if body.get("stat") != "OK":
        return []

    rows = []
    for record in body.get("data", []):
        rows.append(
            {
                "symbol": symbol,
                "date": _twse_date_to_iso(record[0]),
                "open": _to_decimal(record[3]),
                "high": _to_decimal(record[4]),
                "low": _to_decimal(record[5]),
                "close": _to_decimal(record[6]),
                "volume": _to_int(record[1]),
            }
        )
    return rows


def upsert_prices(rows: list[dict]) -> int:
    """將 OHLCV 列表 upsert 進 daily_prices，回傳影響筆數。"""
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


def crawl_month(symbol: str, year: int, month: int) -> int:
    """高階介面：fetch + upsert，回傳寫入筆數。"""
    rows = fetch_month(symbol, year, month)
    return upsert_prices(rows)
