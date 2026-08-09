from collections import defaultdict
from datetime import date
from decimal import Decimal
from itertools import groupby
from typing import Any, TypedDict


class AlertEvent(TypedDict):
    alert_type: str
    date: str
    details: dict[str, Any]


_MAINTENANCE_RATIO_THRESHOLD = Decimal("1.4")


def evaluate(ohlcv: list[dict], margin: list[dict]) -> list[AlertEvent]:
    """
    掃描完整序列，回傳歷史上所有觸發過的警示事件（依日期升序）。

    ohlcv:  [{"date": "YYYY-MM-DD", "close": float, ...}]  日K，升序
             內部會自動聚合為週K 後計算 ma60_break
    margin: [{"date": "YYYY-MM-DD", "margin_balance": Decimal,
               "margin_maintenance_ratio": Decimal, ...}]  升序
    """
    events: list[AlertEvent] = []

    events.extend(_check_margin_drops(margin))
    events.extend(_check_ma60_break(ohlcv))
    events.extend(_check_maintenance_ratio(margin))
    events.extend(_check_compound(events))

    events.sort(key=lambda e: e["date"])
    return events


def chip_washout(
    margin: list[dict],
    ohlcv: list[dict],
    window: int = 20,
) -> list[dict]:
    """
    籌碼洗淨指標：rolling window 內融資減少速率 ÷ 大盤跌幅。

    回傳 [{"date": str, "value": float}, ...]（有效計算點）
    分母為 0 或正值（大盤未跌）時略過該點。
    value > 1：融資跌幅 > 大盤跌幅（籌碼洗淨充分，偏多訊號）
    value < 1：融資跌幅 < 大盤跌幅（籌碼未洗淨，偏空訊號）
    """
    margin_by_date = {r["date"]: float(r["margin_balance"]) for r in margin}
    ohlcv_by_date = {r["date"]: float(r["close"]) for r in ohlcv}

    dates = sorted(set(margin_by_date) & set(ohlcv_by_date))
    results: list[dict] = []

    for i in range(window, len(dates)):
        end_date = dates[i]
        start_date = dates[i - window]

        mb_start = margin_by_date[start_date]
        mb_end = margin_by_date[end_date]
        px_start = ohlcv_by_date[start_date]
        px_end = ohlcv_by_date[end_date]

        if mb_start == 0 or px_start == 0:
            continue

        margin_change = (mb_end - mb_start) / mb_start
        price_change = (px_end - px_start) / px_start

        if price_change >= 0:
            continue

        value = margin_change / price_change
        results.append({"date": end_date, "value": round(value, 6)})

    return results


# ---------------------------------------------------------------------------
# 內部函數
# ---------------------------------------------------------------------------

def _week_key(row: dict) -> tuple[int, int]:
    iso = date.fromisoformat(row["date"]).isocalendar()
    return (iso.year, iso.week)


def _aggregate_to_weekly(ohlcv: list[dict]) -> list[dict]:
    """日K → 週K（每週最後一個交易日的收盤價為週K收盤）"""
    weekly: list[dict] = []
    for _, week_rows in groupby(ohlcv, key=_week_key):
        rows = list(week_rows)
        weekly.append({"date": rows[-1]["date"], "close": float(rows[-1]["close"])})
    return weekly


def _check_margin_drops(margin: list[dict]) -> list[AlertEvent]:
    events: list[AlertEvent] = []
    if not margin:
        return events

    peak = float(margin[0]["margin_balance"])
    triggered_25 = False
    triggered_50 = False

    for row in margin:
        current = float(row["margin_balance"])

        if current > peak:
            peak = current
            triggered_25 = False
            triggered_50 = False
            continue

        if peak == 0:
            continue

        drop_pct = (peak - current) / peak

        if not triggered_25 and drop_pct >= 0.25:
            triggered_25 = True
            events.append({
                "alert_type": "margin_drop_25",
                "date": row["date"],
                "details": {
                    "peak": peak,
                    "current": current,
                    "drop_pct": round(drop_pct, 6),
                },
            })

        if not triggered_50 and drop_pct >= 0.50:
            triggered_50 = True
            events.append({
                "alert_type": "margin_drop_50",
                "date": row["date"],
                "details": {
                    "peak": peak,
                    "current": current,
                    "drop_pct": round(drop_pct, 6),
                },
            })

    return events


def _check_ma60_break(ohlcv: list[dict]) -> list[AlertEvent]:
    weekly = _aggregate_to_weekly(ohlcv)
    events: list[AlertEvent] = []
    if len(weekly) < 61:
        return events

    closes = [r["close"] for r in weekly]
    dates = [r["date"] for r in weekly]

    for i in range(60, len(closes)):
        ma60 = sum(closes[i - 60:i]) / 60
        prev = closes[i - 1]
        current = closes[i]

        if prev >= ma60 and current < ma60:
            events.append({
                "alert_type": "ma60_break",
                "date": dates[i],
                "details": {
                    "close": round(current, 4),
                    "ma60": round(ma60, 4),
                },
            })

    return events


def _check_maintenance_ratio(margin: list[dict]) -> list[AlertEvent]:
    events: list[AlertEvent] = []
    above = True

    for row in margin:
        ratio = row["margin_maintenance_ratio"]
        if isinstance(ratio, (int, float)):
            ratio = Decimal(str(ratio))

        if above and ratio < _MAINTENANCE_RATIO_THRESHOLD:
            above = False
            events.append({
                "alert_type": "maintenance_ratio_below_140",
                "date": row["date"],
                "details": {"ratio": float(ratio)},
            })
        elif not above and ratio >= _MAINTENANCE_RATIO_THRESHOLD:
            above = True

    return events


def _check_compound(events: list[AlertEvent]) -> list[AlertEvent]:
    by_date: dict[str, list[str]] = defaultdict(list)
    for e in events:
        if e["alert_type"] != "compound":
            by_date[e["date"]].append(e["alert_type"])

    compound_events: list[AlertEvent] = []
    for event_date, types in by_date.items():
        if len(types) >= 2:
            compound_events.append({
                "alert_type": "compound",
                "date": event_date,
                "details": {"triggered": sorted(types)},
            })

    return compound_events
