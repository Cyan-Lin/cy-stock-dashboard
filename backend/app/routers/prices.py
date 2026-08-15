from datetime import date
from typing import Optional

import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db.connection import db_conn
from app.interval import Interval

router = APIRouter(prefix="/api/prices", tags=["prices"])


class PriceBar(BaseModel):
    symbol: str
    date: date
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    volume: Optional[int]
    ma60: Optional[float] = None


# --- SQL helpers ---

_DAILY_SQL = """
    SELECT
        symbol,
        date,
        open,
        high,
        low,
        close,
        volume,
        NULL::numeric AS ma60
    FROM daily_prices
    WHERE symbol = %(symbol)s
      {date_filter}
    ORDER BY date DESC
    LIMIT %(limit)s
"""

# 週線：open 取週內最早交易日的開盤、close 取週內最晚交易日的收盤
# FIRST_VALUE / LAST_VALUE + FILTER 確保假日/停市日不影響語意
_WEEKLY_SQL = """
    WITH weekly AS (
        SELECT
            symbol,
            date_trunc('week', date)::date          AS date,
            (ARRAY_AGG(open  ORDER BY date ASC ))[1] AS open,
            MAX(high)                                AS high,
            MIN(low)                                 AS low,
            (ARRAY_AGG(close ORDER BY date DESC))[1] AS close,
            SUM(volume)                              AS volume
        FROM daily_prices
        WHERE symbol = %(symbol)s
          {date_filter}
        GROUP BY symbol, date_trunc('week', date)
    )
    SELECT
        symbol,
        date,
        open,
        high,
        low,
        close,
        volume,
        AVG(close) OVER (
            ORDER BY date
            ROWS BETWEEN 59 PRECEDING AND CURRENT ROW
        ) AS ma60
    FROM weekly
    ORDER BY date DESC
    LIMIT %(limit)s
"""

_MONTHLY_SQL = """
    WITH monthly AS (
        SELECT
            symbol,
            date_trunc('month', date)::date          AS date,
            (ARRAY_AGG(open  ORDER BY date ASC ))[1] AS open,
            MAX(high)                                AS high,
            MIN(low)                                 AS low,
            (ARRAY_AGG(close ORDER BY date DESC))[1] AS close,
            SUM(volume)                              AS volume
        FROM daily_prices
        WHERE symbol = %(symbol)s
          {date_filter}
        GROUP BY symbol, date_trunc('month', date)
    )
    SELECT
        symbol,
        date,
        open,
        high,
        low,
        close,
        volume,
        AVG(close) OVER (
            ORDER BY date
            ROWS BETWEEN 59 PRECEDING AND CURRENT ROW
        ) AS ma60
    FROM monthly
    ORDER BY date DESC
    LIMIT %(limit)s
"""

_SQL_MAP = {
    Interval.daily: _DAILY_SQL,
    Interval.weekly: _WEEKLY_SQL,
    Interval.monthly: _MONTHLY_SQL,
}


def _build_date_filter(params: dict, from_date, to_date) -> str:
    clauses = []
    if from_date:
        clauses.append("AND date >= %(from_date)s")
        params["from_date"] = from_date
    if to_date:
        clauses.append("AND date <= %(to_date)s")
        params["to_date"] = to_date
    return " ".join(clauses)


@router.get("", response_model=list[PriceBar])
def get_prices(
    symbol: str = Query(..., description="股票代號，例如 TWII"),
    interval: Interval = Query(Interval.daily, description="daily / weekly / monthly"),
    from_date: Optional[date] = Query(None, alias="from", description="起始日期（含），ISO 格式"),
    to_date: Optional[date] = Query(None, alias="to", description="結束日期（含），ISO 格式"),
    limit: int = Query(500, ge=1, le=20000, description="最多回傳筆數"),
):
    params: dict = {"symbol": symbol, "limit": limit}
    date_filter = _build_date_filter(params, from_date, to_date)
    sql = _SQL_MAP[interval].format(date_filter=date_filter)

    with db_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No price data found for {symbol}")

    return [
        PriceBar(
            symbol=r["symbol"],
            date=r["date"],
            open=float(r["open"]) if r["open"] is not None else None,
            high=float(r["high"]) if r["high"] is not None else None,
            low=float(r["low"]) if r["low"] is not None else None,
            close=float(r["close"]) if r["close"] is not None else None,
            volume=r["volume"],
            ma60=float(r["ma60"]) if r["ma60"] is not None else None,
        )
        for r in rows
    ]
