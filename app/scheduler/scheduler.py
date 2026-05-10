import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from pymongo import MongoClient
from app.core.config import settings

logger = logging.getLogger(__name__)

# Module-level scheduler instance
_scheduler: AsyncIOScheduler | None = None
_sync_client: MongoClient | None = None

def get_scheduler() -> AsyncIOScheduler:
    """Return the global APScheduler instance."""
    if _scheduler is None:
        raise RuntimeError("Scheduler not initialized.")
    return _scheduler

async def init_scheduler():
    """Initialize and start the APScheduler with MongoDB job store."""
    global _scheduler, _sync_client
    
    # Configure MongoDB job store (Requires synchronous PyMongo client)
    _sync_client = MongoClient(settings.MONGODB_URI)
    jobstores = {
        'default': MongoDBJobStore(database=settings.MONGODB_DB_NAME, collection='apscheduler_jobs', client=_sync_client)
    }
    
    _scheduler = AsyncIOScheduler(jobstores=jobstores)
    
    # Import jobs here to avoid circular imports
    from app.scheduler.jobs.deadline_reminders import check_and_send_deadline_reminders
    from app.scheduler.jobs.low_stock_alerts import check_low_stock_alerts
    from app.scheduler.jobs.daily_summary import send_daily_summaries
    
    # Add jobs
    # 1. Deadline reminders - every 5 minutes
    _scheduler.add_job(
        check_and_send_deadline_reminders,
        IntervalTrigger(minutes=5),
        id='deadline_reminders_job',
        name='Send deadline reminders for orders',
        replace_existing=True
    )
    
    # 2. Low stock alerts - hourly
    _scheduler.add_job(
        check_low_stock_alerts,
        IntervalTrigger(hours=1),
        id='low_stock_alerts_job',
        name='Check and send hourly low stock alerts',
        replace_existing=True
    )
    
    # 3. Daily summary - every day at 20:00 (UTC, logic inside handles timezones)
    # Actually, if we run it hourly, it can check which businesses should receive it.
    _scheduler.add_job(
        send_daily_summaries,
        IntervalTrigger(hours=1),
        id='daily_summary_job',
        name='Send daily summaries to businesses based on their timezone',
        replace_existing=True
    )
    
    _scheduler.start()
    logger.info("APScheduler initialized and started")

async def shutdown_scheduler():
    """Shutdown the APScheduler gracefully."""
    global _scheduler, _sync_client
    if _scheduler:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down")
    if _sync_client:
        _sync_client.close()
        logger.info("APScheduler MongoDB sync client closed")
