"""
T06 測試：Alert Evaluation Service

所有測試純函數，零 DB 連線、零 HTTP 呼叫。

切面：
  1. margin_drop_25 觸發
  2. margin_drop_25 邊界（24.9% 不觸發 / 25.0% 觸發）
  3. margin_drop_50 觸發 + 邊界
  4. ma60_break 觸發（日K 輸入，內部聚合為週K）
  5. ma60_break 資料不足（< 61 週）
  6. maintenance_ratio_below_140 觸發 + 穿越語意
  7. compound 警示
  8. chip_washout 計算
  9. 空陣列 / 單筆邊界
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.alerts.evaluator import chip_washout, evaluate


# ---------------------------------------------------------------------------
# 輔助工廠
# ---------------------------------------------------------------------------

def _margin_row(dt: str, balance: float, ratio: float) -> dict:
    return {
        "date": dt,
        "margin_balance": Decimal(str(balance)),
        "margin_maintenance_ratio": Decimal(str(ratio)),
    }


def _ohlcv_row(dt: str, close: float) -> dict:
    return {"date": dt, "close": close}


def _make_daily_ohlcv(n_weeks: int, close: float = 100.0) -> list[dict]:
    """產生 n_weeks 週的日K（週一到週五，每週收盤都是 close）。"""
    rows = []
    monday = date(2020, 1, 6)  # 2020-01-06 是週一
    for w in range(n_weeks):
        for d in range(5):  # Mon-Fri
            rows.append(_ohlcv_row((monday + timedelta(weeks=w, days=d)).isoformat(), close))
    return rows


def _make_daily_ohlcv_with_break(n_steady_weeks: int, break_close: float) -> list[dict]:
    """
    產生 n_steady_weeks 週收盤 = 100，
    再接 2 週：第 1 週收盤 100（前一根在 MA 上），第 2 週收盤 break_close（當根跌破）。
    """
    rows = _make_daily_ohlcv(n_steady_weeks, close=100.0)
    base = n_steady_weeks
    monday = date(2020, 1, 6)
    # 第 n_steady_weeks+1 週：全週收盤 100
    for d in range(5):
        rows.append(_ohlcv_row(
            (monday + timedelta(weeks=base, days=d)).isoformat(), 100.0
        ))
    # 第 n_steady_weeks+2 週：全週收盤 break_close
    for d in range(5):
        rows.append(_ohlcv_row(
            (monday + timedelta(weeks=base + 1, days=d)).isoformat(), break_close
        ))
    return rows


# ---------------------------------------------------------------------------
# 切面 1：margin_drop_25 觸發
# ---------------------------------------------------------------------------

def test_margin_drop_25_triggers():
    margin = [
        _margin_row("2024-01-01", 10000, 1.8),
        _margin_row("2024-01-02", 7500, 1.8),  # 下跌 25%，觸發
    ]
    events = evaluate([], margin)
    types = [e["alert_type"] for e in events]
    assert "margin_drop_25" in types


def test_margin_drop_25_details_correct():
    margin = [
        _margin_row("2024-01-01", 10000, 1.8),
        _margin_row("2024-01-02", 7500, 1.8),
    ]
    events = evaluate([], margin)
    e = next(e for e in events if e["alert_type"] == "margin_drop_25")
    assert e["date"] == "2024-01-02"
    assert e["details"]["peak"] == pytest.approx(10000)
    assert e["details"]["current"] == pytest.approx(7500)
    assert e["details"]["drop_pct"] == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# 切面 2：margin_drop_25 邊界
# ---------------------------------------------------------------------------

def test_margin_drop_25_below_threshold_no_trigger():
    # 下跌 24.9%，不應觸發
    margin = [
        _margin_row("2024-01-01", 10000, 1.8),
        _margin_row("2024-01-02", 7510, 1.8),  # (10000-7510)/10000 = 24.9%
    ]
    events = evaluate([], margin)
    assert not any(e["alert_type"] == "margin_drop_25" for e in events)


def test_margin_drop_25_exact_threshold_triggers():
    # 恰好 25.0%，應觸發
    margin = [
        _margin_row("2024-01-01", 10000, 1.8),
        _margin_row("2024-01-02", 7500, 1.8),
    ]
    events = evaluate([], margin)
    assert any(e["alert_type"] == "margin_drop_25" for e in events)


def test_margin_drop_25_resets_after_new_peak():
    # 觸發後再創新高，應可再次觸發
    margin = [
        _margin_row("2024-01-01", 10000, 1.8),
        _margin_row("2024-01-02", 7500, 1.8),   # 第一次觸發
        _margin_row("2024-01-03", 11000, 1.8),  # 新高，重置
        _margin_row("2024-01-04", 8250, 1.8),   # 下跌 25%，第二次觸發
    ]
    events = evaluate([], margin)
    drop25 = [e for e in events if e["alert_type"] == "margin_drop_25"]
    assert len(drop25) == 2


def test_margin_drop_25_no_duplicate_trigger():
    # 同一個高點跌破 25% 後繼續下跌，不應重複觸發
    margin = [
        _margin_row("2024-01-01", 10000, 1.8),
        _margin_row("2024-01-02", 7500, 1.8),  # 觸發
        _margin_row("2024-01-03", 7000, 1.8),  # 繼續跌，不重複
    ]
    events = evaluate([], margin)
    drop25 = [e for e in events if e["alert_type"] == "margin_drop_25"]
    assert len(drop25) == 1


# ---------------------------------------------------------------------------
# 切面 3：margin_drop_50 觸發 + 邊界
# ---------------------------------------------------------------------------

def test_margin_drop_50_triggers():
    margin = [
        _margin_row("2024-01-01", 10000, 1.8),
        _margin_row("2024-01-02", 5000, 1.8),  # 下跌 50%，觸發
    ]
    events = evaluate([], margin)
    assert any(e["alert_type"] == "margin_drop_50" for e in events)


def test_margin_drop_50_below_threshold_no_trigger():
    # 下跌 49.9%，不觸發
    margin = [
        _margin_row("2024-01-01", 10000, 1.8),
        _margin_row("2024-01-02", 5010, 1.8),
    ]
    events = evaluate([], margin)
    assert not any(e["alert_type"] == "margin_drop_50" for e in events)


def test_margin_drop_50_independent_from_25():
    # 跌破 50% 時，25% 和 50% 都應觸發
    margin = [
        _margin_row("2024-01-01", 10000, 1.8),
        _margin_row("2024-01-02", 7500, 1.8),  # 25% 觸發
        _margin_row("2024-01-03", 5000, 1.8),  # 50% 觸發
    ]
    events = evaluate([], margin)
    types = [e["alert_type"] for e in events]
    assert "margin_drop_25" in types
    assert "margin_drop_50" in types


def test_margin_drop_50_same_day_as_25():
    # 單步直接跌破 50%，兩個警示應同日觸發
    margin = [
        _margin_row("2024-01-01", 10000, 1.8),
        _margin_row("2024-01-02", 4000, 1.8),  # 60%，同時跌破兩閾值
    ]
    events = evaluate([], margin)
    dates_25 = [e["date"] for e in events if e["alert_type"] == "margin_drop_25"]
    dates_50 = [e["date"] for e in events if e["alert_type"] == "margin_drop_50"]
    assert dates_25 == ["2024-01-02"]
    assert dates_50 == ["2024-01-02"]


# ---------------------------------------------------------------------------
# 切面 4：ma60_break 觸發（日K 輸入，內部聚合週K）
# ---------------------------------------------------------------------------

def test_ma60_break_triggers():
    # 60 週收盤=100，第 61 週前一根=100（在線上），第 62 週收盤=90（跌破）
    ohlcv = _make_daily_ohlcv_with_break(n_steady_weeks=60, break_close=90.0)
    events = evaluate(ohlcv, [])
    assert any(e["alert_type"] == "ma60_break" for e in events)


def test_ma60_break_details():
    ohlcv = _make_daily_ohlcv_with_break(n_steady_weeks=60, break_close=90.0)
    events = evaluate(ohlcv, [])
    e = next(e for e in events if e["alert_type"] == "ma60_break")
    assert e["details"]["close"] == pytest.approx(90.0)
    assert e["details"]["ma60"] == pytest.approx(100.0)


def test_ma60_break_no_trigger_when_above():
    # 全週收盤始終在 MA 之上，不觸發
    ohlcv = _make_daily_ohlcv(n_weeks=62, close=105.0)
    events = evaluate(ohlcv, [])
    assert not any(e["alert_type"] == "ma60_break" for e in events)


# ---------------------------------------------------------------------------
# 切面 5：ma60_break 資料不足（< 61 週）
# ---------------------------------------------------------------------------

def test_ma60_break_insufficient_data_no_trigger():
    # 60 週日K，聚合後恰好 60 根週K，少於所需 61 根，不觸發
    ohlcv = _make_daily_ohlcv(n_weeks=60, close=90.0)
    events = evaluate(ohlcv, [])
    assert not any(e["alert_type"] == "ma60_break" for e in events)


def test_ma60_break_empty_ohlcv_no_crash():
    events = evaluate([], [])
    assert events == []


# ---------------------------------------------------------------------------
# 切面 6：maintenance_ratio_below_140 觸發 + 穿越語意
# ---------------------------------------------------------------------------

def test_maintenance_ratio_triggers():
    margin = [
        _margin_row("2024-01-01", 10000, 1.5),
        _margin_row("2024-01-02", 10000, 1.3),  # 跌破 1.4，觸發
    ]
    events = evaluate([], margin)
    assert any(e["alert_type"] == "maintenance_ratio_below_140" for e in events)


def test_maintenance_ratio_exact_threshold_no_trigger():
    # 恰好 1.4，不觸發
    margin = [
        _margin_row("2024-01-01", 10000, 1.5),
        _margin_row("2024-01-02", 10000, 1.4),
    ]
    events = evaluate([], margin)
    assert not any(e["alert_type"] == "maintenance_ratio_below_140" for e in events)


def test_maintenance_ratio_no_duplicate_while_below():
    # 持續低於閾值，只觸發一次
    margin = [
        _margin_row("2024-01-01", 10000, 1.5),
        _margin_row("2024-01-02", 10000, 1.3),  # 觸發
        _margin_row("2024-01-03", 10000, 1.2),  # 繼續低，不重複
    ]
    events = evaluate([], margin)
    below = [e for e in events if e["alert_type"] == "maintenance_ratio_below_140"]
    assert len(below) == 1


def test_maintenance_ratio_retriggers_after_recovery():
    # 恢復 ≥ 1.4 後再次跌破，應再次觸發
    margin = [
        _margin_row("2024-01-01", 10000, 1.5),
        _margin_row("2024-01-02", 10000, 1.3),  # 第一次觸發
        _margin_row("2024-01-03", 10000, 1.5),  # 恢復
        _margin_row("2024-01-04", 10000, 1.2),  # 第二次觸發
    ]
    events = evaluate([], margin)
    below = [e for e in events if e["alert_type"] == "maintenance_ratio_below_140"]
    assert len(below) == 2


def test_maintenance_ratio_details():
    margin = [
        _margin_row("2024-01-01", 10000, 1.5),
        _margin_row("2024-01-02", 10000, 1.35),
    ]
    events = evaluate([], margin)
    e = next(e for e in events if e["alert_type"] == "maintenance_ratio_below_140")
    assert e["date"] == "2024-01-02"
    assert e["details"]["ratio"] == pytest.approx(1.35)


# ---------------------------------------------------------------------------
# 切面 7：compound 警示
# ---------------------------------------------------------------------------

def test_compound_triggers_when_two_alerts_same_day():
    # margin_drop_25 + maintenance_ratio_below_140 同日觸發
    margin = [
        _margin_row("2024-01-01", 10000, 1.5),
        _margin_row("2024-01-02", 7500, 1.3),
    ]
    events = evaluate([], margin)
    assert any(e["alert_type"] == "compound" for e in events)


def test_compound_details_lists_triggered_types():
    margin = [
        _margin_row("2024-01-01", 10000, 1.5),
        _margin_row("2024-01-02", 7500, 1.3),
    ]
    events = evaluate([], margin)
    c = next(e for e in events if e["alert_type"] == "compound")
    triggered = c["details"]["triggered"]
    assert "margin_drop_25" in triggered
    assert "maintenance_ratio_below_140" in triggered


def test_compound_not_triggered_with_single_alert():
    margin = [
        _margin_row("2024-01-01", 10000, 1.8),
        _margin_row("2024-01-02", 7500, 1.8),  # 只有 margin_drop_25
    ]
    events = evaluate([], margin)
    assert not any(e["alert_type"] == "compound" for e in events)


def test_compound_not_self_referential():
    # compound 本身不應計入 compound 的 triggered 清單
    margin = [
        _margin_row("2024-01-01", 10000, 1.5),
        _margin_row("2024-01-02", 7500, 1.3),
    ]
    events = evaluate([], margin)
    c = next(e for e in events if e["alert_type"] == "compound")
    assert "compound" not in c["details"]["triggered"]


# ---------------------------------------------------------------------------
# 切面 8：chip_washout 計算
# ---------------------------------------------------------------------------

def test_chip_washout_basic():
    # window=2，3 筆資料，最後一筆可計算
    margin = [
        _margin_row("2024-01-01", 10000, 1.8),
        _margin_row("2024-01-02", 9800, 1.8),
        _margin_row("2024-01-03", 9400, 1.8),
    ]
    ohlcv = [
        _ohlcv_row("2024-01-01", 100.0),
        _ohlcv_row("2024-01-02", 98.0),
        _ohlcv_row("2024-01-03", 94.0),
    ]
    results = chip_washout(margin, ohlcv, window=2)
    assert len(results) == 1
    r = results[0]
    assert r["date"] == "2024-01-03"
    # margin_change = (9400-9800)/9800 ≈ -0.040816
    # price_change  = (94-98)/98     ≈ -0.040816
    # value ≈ 1.0
    assert r["value"] == pytest.approx(1.0, rel=1e-4)


def test_chip_washout_skips_when_price_not_falling():
    # 大盤未跌（price_change >= 0），該點略過
    margin = [
        _margin_row("2024-01-01", 10000, 1.8),
        _margin_row("2024-01-02", 9800, 1.8),
        _margin_row("2024-01-03", 9400, 1.8),
    ]
    ohlcv = [
        _ohlcv_row("2024-01-01", 100.0),
        _ohlcv_row("2024-01-02", 102.0),
        _ohlcv_row("2024-01-03", 105.0),
    ]
    results = chip_washout(margin, ohlcv, window=2)
    assert results == []


def test_chip_washout_empty_input():
    assert chip_washout([], [], window=5) == []


# ---------------------------------------------------------------------------
# 切面 9：空陣列 / 單筆資料邊界
# ---------------------------------------------------------------------------

def test_evaluate_empty_inputs():
    assert evaluate([], []) == []


def test_evaluate_single_ohlcv_no_crash():
    ohlcv = [_ohlcv_row("2024-01-01", 100.0)]
    assert evaluate(ohlcv, []) == []


def test_evaluate_single_margin_no_crash():
    margin = [_margin_row("2024-01-01", 10000, 1.8)]
    assert evaluate([], margin) == []


def test_evaluate_single_margin_below_ratio_triggers():
    # 第一筆就低於閾值：初始 above=True，視為「從正常跌破」→ 觸發
    margin = [_margin_row("2024-01-01", 10000, 1.2)]
    events = evaluate([], margin)
    assert any(e["alert_type"] == "maintenance_ratio_below_140" for e in events)
