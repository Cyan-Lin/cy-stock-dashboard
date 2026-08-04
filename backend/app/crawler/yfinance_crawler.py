"""
yfinance 爬蟲，負責抓取指數日線資料。

支援標的：
  TWII  → Yahoo Finance ticker ^TWII（加權指數）
  TPEx  → Yahoo Finance ticker ^TWO （櫃買指數）

用法：
  crawl(symbol="TWII", from_date=date(2000, 1, 1))         # 首次全歷史
  crawl(symbol="TWII")                                      # 只抓今天
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

import pandas as pd
import yfinance as yf

from app.db.connection import db_conn

# 系統代號 → Yahoo Finance ticker
_TICKER_MAP = {
    "TWII": "^TWII",
    "TPEx": "^TWOII",
}


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
    ticker = _TICKER_MAP.get(symbol)
    if ticker is None:
        raise ValueError(f"Unsupported symbol: {symbol}. Supported: {list(_TICKER_MAP)}")

    today = date.today()
    start = from_date or today
    # yfinance end 是 exclusive，需加一天
    end = (to_date or today) + timedelta(days=1)

    df = yf.download(
        ticker,
        start=start.isoformat(),
        end=end.isoformat(),
        auto_adjust=True,
        progress=False,
    )

    if df.empty:
        return 0

    # yfinance 單一 ticker 時回傳 MultiIndex columns，需 droplevel
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)

    def _to_dec(v) -> Decimal | None:
        f = float(v)
        return None if f != f else Decimal(str(round(f, 2)))  # f != f 是 NaN 判斷

    rows = []
    for dt, row in df.iterrows():
        rows.append(
            {
                "symbol": symbol,
                "date": dt.date().isoformat(),
                "open": _to_dec(row["Open"]),
                "high": _to_dec(row["High"]),
                "low": _to_dec(row["Low"]),
                "close": _to_dec(row["Close"]),
                "volume": int(row["Volume"]) if row["Volume"] == row["Volume"] else None,
            }
        )

    return _upsert(rows)


def _upsert(rows: list[dict]) -> int:
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
