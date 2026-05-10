from typing import List, Optional, Tuple
from datetime import datetime, timezone
import urllib.parse
from pymongo import ReturnDocument

from app.core.database import get_db
from app.models.payment import Payment, PaymentMethod
from app.models.order import Order, PaymentStatus


class PaymentService:
    def __init__(self, business_id: int):
        self.business_id = business_id

    async def record_payment(self, order_id: str, amount: float, method: PaymentMethod = PaymentMethod.CASH, notes: Optional[str] = None) -> Tuple[bool, str]:
        """Record a payment for an order and update order status."""
        from bson import ObjectId

        # 1. Fetch order
        try:
            order_doc = await get_db().orders.find_one({
                "_id": ObjectId(order_id),
                "business_id": self.business_id
            })
        except Exception:
            return False, "Invalid order ID."

        if not order_doc:
            return False, "Order not found."

        order = Order(**order_doc)
        order_number = order.order_number

        # 2. Insert Payment record
        payment = Payment(
            business_id=self.business_id,
            order_id=order_id,
            order_number=order_number,
            amount=amount,
            method=method,
            notes=notes,
            recorded_at=datetime.now(timezone.utc)
        )
        await get_db().payments.insert_one(payment.model_dump())

        # 3. Update Order amount_paid and payment_status
        new_amount_paid = order.amount_paid + amount
        
        if new_amount_paid >= order.total_amount:
            new_payment_status = PaymentStatus.PAID
        elif new_amount_paid > 0:
            new_payment_status = PaymentStatus.PARTIAL
        else:
            new_payment_status = PaymentStatus.UNPAID

        await get_db().orders.update_one(
            {"_id": ObjectId(order_id), "business_id": self.business_id},
            {
                "$set": {
                    "amount_paid": new_amount_paid,
                    "payment_status": new_payment_status.value,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )

        # 4. Log activity
        await get_db().activity_logs.insert_one({
            "business_id": self.business_id,
            "action": "record_payment",
            "entity_type": "order",
            "entity_id": order_id,
            "details": {
                "order_number": order_number,
                "amount": amount,
                "method": method.value,
                "new_payment_status": new_payment_status.value
            },
            "created_at": datetime.now(timezone.utc)
        })

        return True, f"Recorded {amount} payment for {order_number}. Status: {new_payment_status.value}."

    async def get_payments_for_order(self, order_id: str) -> List[Payment]:
        """Get all payments for a specific order."""
        cursor = get_db().payments.find({
            "business_id": self.business_id,
            "order_id": order_id
        }).sort("recorded_at", 1)
        
        docs = await cursor.to_list(length=None)
        return [Payment(**doc) for doc in docs]

    async def get_unpaid_orders(self) -> List[Order]:
        """Get all orders that are unpaid or partially paid."""
        cursor = get_db().orders.find({
            "business_id": self.business_id,
            "payment_status": {"$in": [PaymentStatus.UNPAID.value, PaymentStatus.PARTIAL.value]},
            "status": {"$ne": "cancelled"}
        }).sort("deadline", 1)
        
        docs = await cursor.to_list(length=None)
        return [Order(**doc) for doc in docs]

    def generate_upi_link(self, amount: float, payee_vpa: str, order_number: str) -> str:
        """Generate a UPI deep link."""
        params = {
            "pa": payee_vpa,
            "pn": "Business",
            "am": str(amount),
            "tn": order_number,
            "cu": "INR"
        }
        query_string = urllib.parse.urlencode(params)
        return f"upi://pay?{query_string}"

    async def get_revenue_summary(self, start_date: datetime, end_date: datetime) -> dict:
        """Get revenue summary (total collected vs total outstanding) in a date range."""
        pipeline = [
            {
                "$match": {
                    "business_id": self.business_id,
                    "recorded_at": {"$gte": start_date, "$lte": end_date}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_collected": {"$sum": "$amount"}
                }
            }
        ]
        
        result = await get_db().payments.aggregate(pipeline).to_list(length=1)
        total_collected = result[0]["total_collected"] if result else 0.0

        return {
            "total_collected": total_collected
        }
