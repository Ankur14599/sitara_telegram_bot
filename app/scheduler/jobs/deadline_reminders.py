import logging
from datetime import datetime, timedelta, timezone
from bson import ObjectId

from app.core.database import get_db
from app.services.notification_service import NotificationService
from app.models.order import OrderStatus

logger = logging.getLogger(__name__)

async def check_and_send_deadline_reminders():
    """Poll for due reminders and send them."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=10)

    # Find reminders that are due but haven't been sent
    cursor = get_db().reminders.find({
        "sent": False,
        "failed": False,
        "scheduled_at": {"$lte": now, "$gte": window_start}
    })
    
    reminders = await cursor.to_list(length=100)
    if not reminders:
        return
        
    logger.info(f"Found {len(reminders)} due reminders to process")
    
    for reminder in reminders:
        business_id = reminder["business_id"]
        order_id = reminder["order_id"]
        
        # Check if order is still active
        try:
            order_doc = await get_db().orders.find_one({"_id": ObjectId(order_id)})
            if not order_doc:
                await get_db().reminders.update_one(
                    {"_id": reminder["_id"]},
                    {"$set": {"failed": True, "error_message": "Order not found"}}
                )
                continue
                
            if order_doc.get("status") in [OrderStatus.COMPLETED.value, OrderStatus.CANCELLED.value]:
                # Skip completed or cancelled orders
                await get_db().reminders.update_one(
                    {"_id": reminder["_id"]},
                    {"$set": {"sent": True, "sent_at": now}}
                )
                continue
                
            order_number = order_doc.get("order_number", "Unknown")
            customer_name = order_doc.get("customer_name", "Customer")
            hours = reminder["hours_before_deadline"]
            
            # Send notification
            text = (
                f"⏰ *Deadline Reminder*\n\n"
                f"Order *{order_number}* for {customer_name} is due in {hours} hours!\n"
            )
            
            success = await NotificationService.send_message(business_id, text)
            
            if success:
                await get_db().reminders.update_one(
                    {"_id": reminder["_id"]},
                    {"$set": {"sent": True, "sent_at": now}}
                )
                # Update order to track reminders sent
                await get_db().orders.update_one(
                    {"_id": ObjectId(order_id)},
                    {"$push": {"reminders_sent": now}}
                )
            else:
                await get_db().reminders.update_one(
                    {"_id": reminder["_id"]},
                    {"$set": {"failed": True, "error_message": "Failed to send message"}}
                )
        except Exception as e:
            logger.error(f"Error processing reminder {reminder['_id']}: {e}")
            await get_db().reminders.update_one(
                {"_id": reminder["_id"]},
                {"$set": {"failed": True, "error_message": str(e)}}
            )
