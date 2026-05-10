"""
MongoDB async client via Motor.
Provides collection accessors and index creation.
"""

import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import IndexModel, ASCENDING, DESCENDING
from pymongo.errors import CollectionInvalid

logger = logging.getLogger(__name__)

# Module-level references — initialized at startup
_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_db(mongodb_uri: str, db_name: str) -> None:
    """Create the Motor client and store references."""
    global _client, _db
    _client = AsyncIOMotorClient(mongodb_uri)
    _db = _client[db_name]

    # Verify connectivity
    await _client.admin.command("ping")
    logger.info(f"Connected to MongoDB: {db_name}")


async def close_db() -> None:
    """Gracefully close the Motor client."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        logger.info("MongoDB connection closed")


def get_db() -> AsyncIOMotorDatabase:
    """Return the active database handle. Raises if not connected."""
    if _db is None:
        raise RuntimeError("Database not initialized. Call connect_db() first.")
    return _db

class DatabaseProxy:
    def __getattr__(self, name):
        return get_db()[name]

db = DatabaseProxy()


# ── Collection accessors ──────────────────────────────────────────────

def businesses_col():
    return get_db()["businesses"]

def orders_col():
    return get_db()["orders"]

def inventory_col():
    return get_db()["inventory"]

def product_bom_col():
    return get_db()["product_bom"]

def customers_col():
    return get_db()["customers"]

def payments_col():
    return get_db()["payments"]

def reminders_col():
    return get_db()["reminders"]

def activity_logs_col():
    return get_db()["activity_logs"]


# ── Index creation ────────────────────────────────────────────────────

async def create_indexes() -> None:
    """Create all required indexes. Safe to call multiple times (idempotent)."""
    db = get_db()
    logger.info("Creating MongoDB indexes...")

    # businesses
    await db["businesses"].create_indexes([
        IndexModel([("telegram_user_id", ASCENDING)], unique=True),
    ])

    # orders
    await db["orders"].create_indexes([
        IndexModel([("business_id", ASCENDING), ("order_number", ASCENDING)], unique=True),
        IndexModel([("business_id", ASCENDING), ("status", ASCENDING)]),
        IndexModel([("business_id", ASCENDING), ("deadline", ASCENDING)]),
        IndexModel([("deadline", ASCENDING)]),
    ])

    # inventory
    await db["inventory"].create_indexes([
        IndexModel([("business_id", ASCENDING), ("name_normalized", ASCENDING)], unique=True),
    ])

    # product_bom
    await db["product_bom"].create_indexes([
        IndexModel([("business_id", ASCENDING), ("product_name_normalized", ASCENDING)], unique=True),
    ])

    # customers
    await db["customers"].create_indexes([
        IndexModel([("business_id", ASCENDING), ("name_normalized", ASCENDING)], unique=True),
    ])

    # payments
    await db["payments"].create_indexes([
        IndexModel([("business_id", ASCENDING), ("order_id", ASCENDING)]),
    ])

    # reminders — primary scheduler index
    await db["reminders"].create_indexes([
        IndexModel([("sent", ASCENDING), ("scheduled_at", ASCENDING)]),
        IndexModel([("business_id", ASCENDING), ("order_id", ASCENDING)]),
    ])

    # activity_logs — TTL index (90 days)
    await db["activity_logs"].create_indexes([
        IndexModel([("business_id", ASCENDING), ("created_at", DESCENDING)]),
        IndexModel([("created_at", ASCENDING)], expireAfterSeconds=90 * 24 * 3600),
    ])

    logger.info("All MongoDB indexes created successfully")
