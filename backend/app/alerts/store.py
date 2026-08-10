import json
from decimal import Decimal

import psycopg2.extras

from app.alerts.evaluator import AlertEvent, evaluate
from app.db.connection import db_conn


def save_alert_events(conn, symbol: str, events: list[AlertEvent]) -> None:
    if not events:
        return
    with conn.cursor() as cur:
        for event in events:
            cur.execute(
                """
                INSERT INTO alert_events (symbol, alert_type, date, details)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (symbol, alert_type, date) DO NOTHING
                """,
                (
                    symbol,
                    event["alert_type"],
                    event["date"],
                    json.dumps(event["details"]),
                ),
            )


def evaluate_and_save(symbol: str) -> None:
    with db_conn() as conn:
        conn.autocommit = True
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT date, close FROM daily_prices WHERE symbol = %s ORDER BY date",
                (symbol,),
            )
            ohlcv = [{"date": str(r["date"]), "close": float(r["close"])} for r in cur.fetchall() if r["close"] is not None]

            cur.execute(
                """
                SELECT date, margin_balance, margin_maintenance_ratio
                FROM margin_data
                WHERE symbol = %s ORDER BY date
                """,
                (symbol,),
            )
            margin = [
                {
                    "date": str(r["date"]),
                    "margin_balance": Decimal(str(r["margin_balance"])) if r["margin_balance"] is not None else Decimal("0"),
                    "margin_maintenance_ratio": Decimal(str(r["margin_maintenance_ratio"])) if r["margin_maintenance_ratio"] is not None else Decimal("0"),
                }
                for r in cur.fetchall()
            ]

        events = evaluate(ohlcv, margin)
        save_alert_events(conn, symbol, events)
