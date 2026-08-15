from datetime import date, timedelta
from typing import Optional

import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.alerts.evaluator import chip_washout
from app.db.connection import db_conn
from app.interval import Interval

router = APIRouter(prefix="/api/margin", tags=["margin"])

# T06 確認的 rolling window 大小；不可隨 interval 改變（20 個交易日的語意固定）
_CHIP_WASHOUT_WINDOW = 20


class MarginBar(BaseModel):
    symbol: str
    date: date
    margin_balance: Optional[float]
    margin_balance_amount: Optional[float]
    margin_amount_100m: Optional[float]
    short_balance: Optional[float]
    short_balance_amount: Optional[float]
    margin_maintenance_ratio: Optional[float]
    margin_short_ratio: Optional[float]
    chip_washout: Optional[float]


_MARGIN_SQL = """
    SELECT
        date,
        margin_balance,
        margin_balance_amount,
        short_balance,
        short_balance_amount,
        margin_maintenance_ratio,
        margin_short_ratio
    FROM margin_data
    WHERE symbol = %(symbol)s
    ORDER BY date ASC
"""

_CLOSE_SQL = """
    SELECT date, close
    FROM daily_prices
    WHERE symbol = %(symbol)s AND close IS NOT NULL
    ORDER BY date ASC
"""


def _bucket_start(d: date, interval: Interval) -> date:
    if interval == Interval.weekly:
        return d - timedelta(days=d.weekday())
    if interval == Interval.monthly:
        return d.replace(day=1)
    return d


@router.get("", response_model=list[MarginBar])
def get_margin(
    symbol: str = Query(..., description="股票代號，例如 TWII"),
    interval: Interval = Query(Interval.daily, description="daily / weekly / monthly"),
    from_date: Optional[date] = Query(None, alias="from", description="起始日期（含），ISO 格式"),
    to_date: Optional[date] = Query(None, alias="to", description="結束日期（含），ISO 格式"),
    limit: int = Query(500, ge=1, le=20000, description="最多回傳筆數"),
):
    with db_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(_MARGIN_SQL, {"symbol": symbol})
            margin_rows = cur.fetchall()
            cur.execute(_CLOSE_SQL, {"symbol": symbol})
            price_rows = cur.fetchall()

    if not margin_rows:
        raise HTTPException(status_code=404, detail=f"No margin data found for {symbol}")

    # 籌碼洗淨永遠在完整日頻序列上以 window=20 交易日計算（唯一公式來源：
    # app.alerts.evaluator.chip_washout）。週K/月K 只是對算好的日頻結果取樣，
    # 不會在聚合後的資料上重新套窗口——否則 20 期就變成 20 週/月，語意跑掉。
    margin_for_washout = [
        {"date": r["date"].isoformat(), "margin_balance": float(r["margin_balance_amount"])}
        for r in margin_rows
        if r["margin_balance_amount"] is not None
    ]
    ohlcv_for_washout = [
        {"date": r["date"].isoformat(), "close": float(r["close"])}
        for r in price_rows
    ]
    washout_by_date = {
        w["date"]: w["value"]
        for w in chip_washout(margin_for_washout, ohlcv_for_washout, window=_CHIP_WASHOUT_WINDOW)
    }

    daily_bars = []
    for r in margin_rows:
        amount = float(r["margin_balance_amount"]) if r["margin_balance_amount"] is not None else None
        ratio = float(r["margin_maintenance_ratio"]) if r["margin_maintenance_ratio"] is not None else None
        daily_bars.append({
            "date": r["date"],
            "margin_balance": float(r["margin_balance"]) if r["margin_balance"] is not None else None,
            "margin_balance_amount": amount,
            "margin_amount_100m": amount / 100_000 if amount is not None else None,
            "short_balance": float(r["short_balance"]) if r["short_balance"] is not None else None,
            "short_balance_amount": float(r["short_balance_amount"]) if r["short_balance_amount"] is not None else None,
            "margin_maintenance_ratio": ratio * 100 if ratio is not None else None,
            "margin_short_ratio": float(r["margin_short_ratio"]) if r["margin_short_ratio"] is not None else None,
            "chip_washout": washout_by_date.get(r["date"].isoformat()),
        })

    if interval == Interval.daily:
        bars = daily_bars
    else:
        # 同一 bucket 內按升序覆蓋，保留 bucket 最後一個交易日的值
        buckets: dict[date, dict] = {}
        for bar in daily_bars:
            bucket_date = _bucket_start(bar["date"], interval)
            bucket_bar = dict(bar)
            bucket_bar["date"] = bucket_date
            buckets[bucket_date] = bucket_bar
        bars = [buckets[key] for key in sorted(buckets)]

    if from_date:
        bars = [b for b in bars if b["date"] >= from_date]
    if to_date:
        bars = [b for b in bars if b["date"] <= to_date]

    bars.sort(key=lambda b: b["date"], reverse=True)
    bars = bars[:limit]

    if not bars:
        raise HTTPException(status_code=404, detail=f"No margin data found for {symbol}")

    return [MarginBar(symbol=symbol, **b) for b in bars]
