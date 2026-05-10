import logging
from datetime import datetime, timezone
import pytz

from app.core.database import get_db
from app.services.summary_service import SummaryService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

async def send_daily_summaries():
    """Send daily summaries to businesses at their local 20:00."""
    now_utc = datetime.now(timezone.utc)
    
    # We poll hourly. We want to find businesses where it is currently between 20:00 and 20:59 local time.
    # To do this correctly, we can fetch all businesses and check their local time.
    # Alternatively, we just do it via timezone calc.
    
    cursor = get_db().businesses.find({})
    businesses = await cursor.to_list(length=None)
    
    for biz in businesses:
        biz_tz = biz.get("timezone", "UTC")
        summary_time_str = biz.get("daily_summary_time", "20:00")
        
        try:
            tz = pytz.timezone(biz_tz)
        except pytz.UnknownTimeZoneError:
            tz = pytz.UTC
            
        local_time = now_utc.astimezone(tz)
        
        # Parse target hour and minute
        try:
            target_h, target_m = map(int, summary_time_str.split(":"))
        except ValueError:
            target_h, target_m = 20, 0
            
        # We run this job every hour. We check if the current local hour matches the target hour.
        # Since the job runs exactly on the hour (e.g. 14:00 UTC), local time could be 19:30 or 20:00.
        # Let's say if it's within target_h hour, and we haven't sent it today.
        
        # To avoid duplicate sends, we could track `last_summary_sent_date` on the business doc.
        if local_time.hour == target_h:
            last_sent = biz.get("last_summary_sent_date")
            today_str = local_time.strftime("%Y-%m-%d")
            
            if last_sent != today_str:
                business_id = biz["telegram_user_id"]
                try:
                    summary_svc = SummaryService(business_id)
                    text = await summary_svc.get_daily_summary()
                    
                    success = await NotificationService.send_message(business_id, text)
                    if success:
                        await get_db().businesses.update_one(
                            {"_id": biz["_id"]},
                            {"$set": {"last_summary_sent_date": today_str}}
                        )
                except Exception as e:
                    logger.error(f"Failed to send daily summary to {business_id}: {e}")
