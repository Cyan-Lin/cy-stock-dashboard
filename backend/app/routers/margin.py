from datetime import date
from typing import Optional

import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.db.connection import db_conn

router = APIRouter(prefix="/api/margin", tags=["margin"])


class MarginBar(BaseModel):
    symbol: str
    date: date
    margin_balance: Optional[float]
    margin_balance_amount: Optional[float]
    short_balance: Optional[float]
    short_balance_amount: Optional[float]
    margin_maintenance_ratio: Optional[float]
    margin_short_ratio: Optional[float]


_SQL = """
    SELECT
        symbol,
        date,
        margin_balance,
        margin_balance_amount,
        short_balance,
        short_balance_amount,
        margin_maintenance_ratio,
        margin_short_ratio
    FROM margin_data
    WHERE symbol = %(symbol)s
      {date_filter}
    ORDER BY date DESC
    LIMIT %(limit)s
"""


def _build_date_filter(params: dict, from_date, to_date) -> str:
    clauses = []
    if from_date:
        clauses.append("AND date >= %(from_date)s")
        params["from_date"] = from_date
    if to_date:
        clauses.append("AND date <= %(to_date)s")
        params["to_date"] = to_date
    return " ".join(clauses)


@router.get("", response_model=list[MarginBar])
def get_margin(
    symbol: str = Query(..., description="股票代號，例如 TWII"),
    from_date: Optional[date] = Query(None, alias="from", description="起始日期（含），ISO 格式"),
    to_date: Optional[date] = Query(None, alias="to", description="結束日期（含），ISO 格式"),
    limit: int = Query(500, ge=1, le=20000, description="最多回傳筆數"),
):
    params: dict = {"symbol": symbol, "limit": limit}
    date_filter = _build_date_filter(params, from_date, to_date)
    sql = _SQL.format(date_filter=date_filter)

    with db_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No margin data found for {symbol}")

    return [
        MarginBar(
            symbol=r["symbol"],
            date=r["date"],
            margin_balance=float(r["margin_balance"]) if r["margin_balance"] is not None else None,
            margin_balance_amount=float(r["margin_balance_amount"]) if r["margin_balance_amount"] is not None else None,
            short_balance=float(r["short_balance"]) if r["short_balance"] is not None else None,
            short_balance_amount=float(r["short_balance_amount"]) if r["short_balance_amount"] is not None else None,
            margin_maintenance_ratio=float(r["margin_maintenance_ratio"]) if r["margin_maintenance_ratio"] is not None else None,
            margin_short_ratio=float(r["margin_short_ratio"]) if r["margin_short_ratio"] is not None else None,
        )
        for r in rows
    ]
