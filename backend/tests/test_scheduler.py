"""
T05 測試：APScheduler 每日排程

切面：
  1. cron trigger 時區為 Asia/Taipei
  2. cron trigger day_of_week 為 mon-fri（週六不觸發）
  3. cron trigger hour 為 22
  4. run_daily_crawl 呼叫全部四個爬蟲任務（TWII prices、TPEx prices、TWII margin、TPEx margin）
  5. 爬蟲回傳筆數 > 0 → log 包含 "records upserted"
  6. 爬蟲回傳 0 → log 包含 "skipped"
  7. 爬蟲拋出例外 → log 包含 "ERROR"，其餘爬蟲仍繼續執行
  8. POST /api/scrape/daily → 200，run_daily_crawl 被呼叫
"""

import logging
from datetime import datetime
from unittest.mock import MagicMock, call, patch

import pytest
import pytz
from fastapi.testclient import TestClient

from app.main import app
from app.scheduler import (
    CRON_DAY_OF_WEEK,
    CRON_HOUR,
    CRON_TIMEZONE,
    run_daily_crawl,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# 切面 1-3：cron trigger 設定正確性
# ---------------------------------------------------------------------------

def _make_trigger():
    from apscheduler.triggers.cron import CronTrigger
    return CronTrigger(day_of_week=CRON_DAY_OF_WEEK, hour=CRON_HOUR, timezone=CRON_TIMEZONE)


def test_trigger_timezone():
    trigger = _make_trigger()
    assert str(trigger.timezone) == "Asia/Taipei"


def test_trigger_day_of_week_excludes_weekend():
    trigger = _make_trigger()
    tz = pytz.timezone("Asia/Taipei")
    # 已知週六 2024-04-06 22:00
    saturday = tz.localize(datetime(2024, 4, 6, 22, 0, 0))
    next_fire = trigger.get_next_fire_time(None, saturday)
    # 下一次觸發必須是週一（weekday == 0）
    assert next_fire.weekday() == 0


def test_trigger_hour():
    trigger = _make_trigger()
    tz = pytz.timezone("Asia/Taipei")
    # 週一 21:59，下一次應為當天 22:00
    monday_before = tz.localize(datetime(2024, 4, 1, 21, 59, 0))
    next_fire = trigger.get_next_fire_time(None, monday_before)
    assert next_fire.hour == 22


# ---------------------------------------------------------------------------
# 切面 4：run_daily_crawl 呼叫四個任務
# ---------------------------------------------------------------------------

def test_run_daily_crawl_calls_all_four_tasks():
    mock_prices = MagicMock(return_value=10)
    mock_margin = MagicMock(return_value=10)
    with (
        patch("app.scheduler.crawl_prices", mock_prices),
        patch("app.scheduler.crawl_margin", mock_margin),
    ):
        run_daily_crawl()

    # prices 以 TWII、TPEx 各呼叫一次
    assert call("TWII") in mock_prices.call_args_list
    assert call("TPEx") in mock_prices.call_args_list
    # margin 以 TWII、TPEx 各呼叫一次
    assert call("TWII") in mock_margin.call_args_list
    assert call("TPEx") in mock_margin.call_args_list


# ---------------------------------------------------------------------------
# 切面 5：回傳筆數 > 0 → log "records upserted"
# ---------------------------------------------------------------------------

def test_run_daily_crawl_logs_upserted_count(caplog):
    with caplog.at_level(logging.INFO, logger="app.scheduler"):
        with (
            patch("app.scheduler.crawl_prices", return_value=15),
            patch("app.scheduler.crawl_margin", return_value=8),
        ):
            run_daily_crawl()

    assert any("records upserted" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# 切面 6：回傳 0 → log "skipped"
# ---------------------------------------------------------------------------

def test_run_daily_crawl_logs_skipped_when_zero(caplog):
    with caplog.at_level(logging.INFO, logger="app.scheduler"):
        with (
            patch("app.scheduler.crawl_prices", return_value=0),
            patch("app.scheduler.crawl_margin", return_value=0),
        ):
            run_daily_crawl()

    assert any("skipped" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# 切面 7：例外 → log "ERROR"，其他爬蟲仍繼續
# ---------------------------------------------------------------------------

def test_run_daily_crawl_isolates_errors(caplog):
    def boom(symbol):
        raise RuntimeError("網路錯誤")

    mock_margin = MagicMock(return_value=5)
    with caplog.at_level(logging.ERROR, logger="app.scheduler"):
        with (
            patch("app.scheduler.crawl_prices", side_effect=boom),
            patch("app.scheduler.crawl_margin", mock_margin),
        ):
            run_daily_crawl()  # 不應拋出例外

    assert any("ERROR" in r.message for r in caplog.records)
    # margin 仍被呼叫（共 2 次）
    assert mock_margin.call_count == 2


# ---------------------------------------------------------------------------
# 切面 8：POST /api/scrape/daily → 202
# ---------------------------------------------------------------------------

def test_post_scrape_daily_returns_200():
    with patch("app.routers.scrape.run_daily_crawl") as mock_crawl:
        resp = client.post("/api/scrape/daily")
    assert resp.status_code == 200
    mock_crawl.assert_called_once()
