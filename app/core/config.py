"""
Application configuration via pydantic-settings.
Reads from .env file and environment variables.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Central configuration for SmallBiz Telegram Bot."""

    # --- Telegram Bot ---
    TELEGRAM_BOT_TOKEN: str
    WEBHOOK_SECRET: str
    WEBHOOK_URL: str  # Base URL, e.g. https://your-domain.com

    # --- MongoDB ---
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "smallbiz_bot"

    # --- GROQ API ---
    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_MAX_RETRIES: int = 1
    GROQ_CIRCUIT_BREAKER_THRESHOLD: int = 3
    GROQ_RATE_LIMIT: int = 5  # concurrent requests semaphore

    # Per-user GROQ abuse prevention
    # Max GROQ API calls a single user can trigger per window
    GROQ_USER_CALLS_PER_WINDOW: int = 20   # e.g. 20 AI calls ...
    GROQ_USER_WINDOW_SECONDS: int = 300    # ... per 5 minutes

    # Bot assistant name
    ASSISTANT_NAME: str = "Sitara"

    # --- Admin Panel ---
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD_HASH: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24

    # --- Server ---
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    LOG_LEVEL: str = "info"

    @property
    def webhook_path(self) -> str:
        """Full webhook path including secret token."""
        return f"/webhook/{self.WEBHOOK_SECRET}"

    @property
    def full_webhook_url(self) -> str:
        """Full webhook URL for Telegram registration."""
        return f"{self.WEBHOOK_URL}{self.webhook_path}"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


# Lazy singleton — avoids crash at import time if .env is missing
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create the Settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# For backward-compatible `from app.core.config import settings` usage,
# we use a module-level property via __getattr__
def __getattr__(name: str):
    if name == "settings":
        return get_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
