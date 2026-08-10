import concurrent.futures
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.alerts.store import evaluate_and_save
from app.crawler.moneydj_crawler import crawl as crawl_prices
from app.crawler.pscnet_crawler import crawl as crawl_margin

logger = logging.getLogger(__name__)

CRON_TIMEZONE = "Asia/Taipei"
CRON_DAY_OF_WEEK = "mon-fri"
CRON_HOUR = 22

_scheduler: BackgroundScheduler | None = None


def _run_one(symbol: str, label: str, crawl_fn) -> None:
    try:
        count = crawl_fn(symbol)
        if count == 0:
            logger.info("[scheduler] %s %s: skipped (no data)", symbol, label)
        else:
            logger.info("[scheduler] %s %s: %d records upserted", symbol, label, count)
    except Exception as exc:
        logger.error("[scheduler] %s %s: ERROR – %s", symbol, label, exc)


def run_daily_crawl() -> None:
    # 在函式內建立，確保 patch 時能正確替換名稱
    tasks = [
        ("TWII", "prices", crawl_prices),
        ("TPEx", "prices", crawl_prices),
        ("TWII", "margin", crawl_margin),
        ("TPEx", "margin", crawl_margin),
    ]
    logger.info("[scheduler] daily crawl starting")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(_run_one, symbol, label, fn)
            for symbol, label, fn in tasks
        ]
        concurrent.futures.wait(futures)
    logger.info("[scheduler] daily crawl complete")

    for symbol in ("TWII", "TPEx"):
        try:
            evaluate_and_save(symbol)
            logger.info("[scheduler] %s alert evaluation complete", symbol)
        except Exception as exc:
            logger.error("[scheduler] %s alert evaluation ERROR – %s", symbol, exc)


def start_scheduler() -> None:
    global _scheduler
    _scheduler = BackgroundScheduler()
    trigger = CronTrigger(
        day_of_week=CRON_DAY_OF_WEEK,
        hour=CRON_HOUR,
        minute=0,
        timezone=CRON_TIMEZONE,
    )
    _scheduler.add_job(run_daily_crawl, trigger)
    _scheduler.start()
    logger.info("[scheduler] started — cron %s %02d:00 %s", CRON_DAY_OF_WEEK, CRON_HOUR, CRON_TIMEZONE)


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[scheduler] shut down")
