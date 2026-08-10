from datetime import date
from typing import Any, Optional

import psycopg2.extras
from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.db.connection import db_conn

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertEventOut(BaseModel):
    symbol: str
    alert_type: str
    date: date
    details: Optional[Any] = None


@router.get("", response_model=list[AlertEventOut])
def get_alerts(symbol: str = Query(..., description="股票代號，例如 TWII")):
    with db_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT symbol, alert_type, date, details
                FROM alert_events
                WHERE symbol = %s
                ORDER BY date DESC
                """,
                (symbol,),
            )
            rows = cur.fetchall()

    return [
        AlertEventOut(
            symbol=r["symbol"],
            alert_type=r["alert_type"],
            date=r["date"],
            details=r["details"],
        )
        for r in rows
    ]
