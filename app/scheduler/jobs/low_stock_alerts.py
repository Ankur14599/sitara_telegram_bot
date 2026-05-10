import logging
from datetime import datetime, timezone
from typing import Dict, List

from app.core.database import get_db
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

async def check_low_stock_alerts():
    """Hourly job to check for items below low stock threshold."""
    # Find all items where quantity <= low_stock_threshold and not yet alerted
    # Actually, we can just use the mongo query
    cursor = get_db().inventory.find({
        "$expr": {"$lte": ["$quantity", "$low_stock_threshold"]},
        "low_stock_alerted": {"$ne": True}
    })
    
    items = await cursor.to_list(length=None)
    if not items:
        return
        
    logger.info(f"Found {len(items)} items below low stock threshold")
    
    # Group by business_id
    alerts_by_business: Dict[int, List[dict]] = {}
    for item in items:
        b_id = item["business_id"]
        if b_id not in alerts_by_business:
            alerts_by_business[b_id] = []
        alerts_by_business[b_id].append(item)
        
    # Send notifications per business
    now = datetime.now(timezone.utc)
    
    for business_id, biz_items in alerts_by_business.items():
        lines = ["⚠️ *Low Stock Alert*\n"]
        for item in biz_items:
            lines.append(f"• {item['name']}: {item['quantity']} {item['unit']} remaining (threshold: {item['low_stock_threshold']})")
            
        text = "\n".join(lines)
        
        success = await NotificationService.send_message(business_id, text)
        
        if success:
            # Mark as alerted
            item_ids = [item["_id"] for item in biz_items]
            await get_db().inventory.update_many(
                {"_id": {"$in": item_ids}},
                {"$set": {"low_stock_alerted": True, "updated_at": now}}
            )
        else:
            logger.error(f"Failed to send low stock alert to business {business_id}")
