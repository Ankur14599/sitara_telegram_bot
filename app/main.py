"""
FastAPI application entrypoint with lifespan management.
Handles: DB connection, index creation, bot initialization, scheduler.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import connect_db, close_db, create_indexes
from app.bot.application import build_application
from app.bot.webhook import router as webhook_router
from app.scheduler.scheduler import init_scheduler, shutdown_scheduler

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Startup: DB connect → indexes → bot init → scheduler start
    Shutdown: scheduler stop → bot shutdown → DB close
    """
    # ── Startup ───────────────────────────────────────────────────────
    logger.info("Starting SmallBiz Bot...")

    # 1. Connect to MongoDB
    await connect_db(settings.MONGODB_URI, settings.MONGODB_DB_NAME)

    # 2. Create indexes (idempotent)
    await create_indexes()

    # 3. Build and initialize the Telegram bot application
    bot_app = build_application()
    await bot_app.initialize()
    logger.info("Telegram bot initialized (webhook mode)")

    # 4. Initialize and start the APScheduler
    await init_scheduler()

    logger.info("SmallBiz Bot startup complete ✓")

    yield  # Application runs here

    # ── Shutdown ──────────────────────────────────────────────────────
    logger.info("Shutting down SmallBiz Bot...")

    # Stop scheduler (Phase 3)
    await shutdown_scheduler()

    # Shutdown bot
    await bot_app.shutdown()
    logger.info("Telegram bot shut down")

    # Close DB
    await close_db()

    logger.info("SmallBiz Bot shutdown complete ✓")


# ── FastAPI App ───────────────────────────────────────────────────────

app = FastAPI(
    title="SmallBiz Telegram Bot",
    description="Multi-tenant Telegram bot for small business order & inventory management",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount webhook routes
app.include_router(webhook_router)

# Mount admin routes
from app.admin.router import router as admin_router
app.include_router(admin_router)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "service": "SmallBiz Telegram Bot",
        "version": "0.1.0",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
