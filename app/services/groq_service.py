"""
GROQ NLP pipeline — intent classification + entity extraction + Sitara chat.
Two-step chain with retry, circuit breaker, concurrency and per-user rate limiting.
"""

import asyncio
import json
import logging
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from groq import AsyncGroq

logger = logging.getLogger(__name__)


class GroqService:
    """NLP service wrapping the GROQ API for intent + entity extraction + conversation."""

    # Valid intents — includes conversational ones so Sitara feels human
    INTENTS = [
        "new_order", "update_order", "check_order",
        "add_stock", "remove_stock", "set_recipe",
        "question",
        "greeting",      # hi, hello, hey, good morning, etc.
        "chitchat",      # how are you, what's your name, thanks, etc.
        "unknown",
    ]

    # Sitara's persona system prompt (shared across conversation methods)
    SITARA_PERSONA = (
        "You are Sitara, a warm, witty, and professional virtual assistant for a small business owner. "
        "You speak in a friendly, conversational tone — like a knowledgeable business partner who also happens to be great company. "
        "Your primary job is helping with orders, inventory, customers, and payments, but you can also hold a light conversation. "
        "Keep replies concise (2-4 sentences max) unless the user asks for detail. "
        "Use occasional emojis to feel warm, but don't overdo it. "
        "Never break character. If asked about something outside your scope, gently steer back to business topics."
    )

    def __init__(self):
        self._client = None
        self._model = None
        self._semaphore = None
        self._consecutive_failures = 0
        self._circuit_open = False
        self._initialized = False

        # Per-user GROQ call tracking  { user_id: [timestamp, ...] }
        self._user_call_log: dict[int, list[float]] = defaultdict(list)

    def _ensure_initialized(self):
        """Lazy init — create GROQ client on first use."""
        if not self._initialized:
            from app.core.config import settings
            self._client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            self._model = settings.GROQ_MODEL
            self._semaphore = asyncio.Semaphore(settings.GROQ_RATE_LIMIT)
            self._initialized = True

    # ── Per-user abuse prevention ─────────────────────────────────────

    def check_user_rate_limit(self, user_id: int) -> bool:
        """
        Return True if the user is allowed to make another GROQ call.
        Cleans up stale timestamps before checking.
        """
        from app.core.config import settings
        window = settings.GROQ_USER_WINDOW_SECONDS
        limit = settings.GROQ_USER_CALLS_PER_WINDOW
        now = time.monotonic()

        # Purge timestamps outside the rolling window
        self._user_call_log[user_id] = [
            t for t in self._user_call_log[user_id] if now - t < window
        ]
        return len(self._user_call_log[user_id]) < limit

    def record_user_call(self, user_id: int) -> None:
        """Record a GROQ call for this user."""
        self._user_call_log[user_id].append(time.monotonic())

    def user_calls_remaining(self, user_id: int) -> int:
        """Return remaining GROQ calls the user has in the current window."""
        from app.core.config import settings
        window = settings.GROQ_USER_WINDOW_SECONDS
        limit = settings.GROQ_USER_CALLS_PER_WINDOW
        now = time.monotonic()
        recent = [t for t in self._user_call_log[user_id] if now - t < window]
        return max(0, limit - len(recent))

    # ── Sitara — conversational chat ──────────────────────────────────

    async def chat_with_sitara(
        self,
        user_message: str,
        user_id: int,
        business_context: Optional[dict] = None,
    ) -> str:
        """
        General conversational response as Sitara.
        Handles greetings, chitchat, and open-ended questions.
        Returns a friendly reply string.
        """
        # Build a lightweight context snippet for Sitara
        ctx = ""
        if business_context:
            biz_name = business_context.get("business_name", "your business")
            owner = business_context.get("owner_name", "")
            ctx = (
                f"\nContext: You are assisting {owner}, the owner of '{biz_name}'. "
                "Refer to them by name when it feels natural."
            )

        system_prompt = self.SITARA_PERSONA + ctx

        try:
            return await self._call_groq(system_prompt, user_message, temperature=0.7)
        except Exception as e:
            logger.error(f"Sitara chat failed: {e}")
            return (
                "😊 I'm here to help! You can ask me about orders, inventory, "
                "customers, or payments. What would you like to do?"
            )

    # ── Intent classification ─────────────────────────────────────────

    async def classify_intent(self, message: str) -> str:
        """
        Cheap call — returns one of the valid intents.
        Falls back to 'unknown' on failure.
        """
        system_prompt = (
            "You are an intent classifier for a small business management bot called Sitara.\n"
            "Classify the user's message into EXACTLY ONE of these intents:\n"
            "- greeting: hi, hello, hey, good morning/evening, salam, namaste, etc.\n"
            "- chitchat: how are you, what's your name, thanks, you're great, jokes, banter, etc.\n"
            "- new_order: user wants to create a new order\n"
            "- update_order: user wants to modify an existing order\n"
            "- check_order: user wants to check order status\n"
            "- add_stock: user is adding inventory/stock\n"
            "- remove_stock: user is removing/using inventory\n"
            "- set_recipe: user wants to define materials for a product\n"
            "- question: user is asking a business-related question (orders count, revenue, stock levels)\n"
            "- unknown: message doesn't fit any category\n\n"
            "Respond with ONLY the intent string, nothing else."
        )

        try:
            response = await self._call_groq(system_prompt, message)
            intent = response.strip().lower().replace('"', '').replace("'", "")
            return intent if intent in self.INTENTS else "unknown"
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            return "unknown"

    # ── Order extraction ──────────────────────────────────────────────

    async def extract_order(
        self,
        message: str,
        business_timezone: str = "Asia/Kolkata",
    ) -> Optional[dict]:
        """
        Extract structured order data from free-form text.
        Returns dict with: customer_name, items, deadline, etc.
        """
        current_dt = datetime.now(timezone.utc).isoformat()

        system_prompt = (
            "You are a structured data extractor for a small business.\n"
            f"Current datetime: {current_dt} (business timezone: {business_timezone})\n\n"
            "Respond ONLY with a JSON object — no explanation, no markdown.\n\n"
            "Extract the following fields:\n"
            "- customer_name (string): the customer's name\n"
            "- items (array of objects): each with 'name' (string) and 'quantity' (number, default 1)\n"
            "- deadline (string, ISO 8601 UTC): the delivery/pickup deadline\n"
            "- deadline_confidence (string): 'high', 'medium', or 'low'\n"
            "- special_instructions (string or null): any special notes\n"
            "- is_valid_order (boolean): true if enough info to create an order\n"
            "- reason_if_invalid (string or null): why the order can't be created\n\n"
            "Rules:\n"
            "- Use the nearest upcoming date for relative references (e.g. 'friday' = next friday)\n"
            "- Default quantity to 1 if not specified\n"
            "- Convert deadline to UTC based on the business timezone\n"
        )

        try:
            response = await self._call_groq(system_prompt, message)
            return self._parse_json(response)
        except Exception as e:
            logger.error(f"Order extraction failed: {e}")
            # Retry once with corrective prompt
            try:
                corrective = (
                    f"Your previous response was not valid JSON. "
                    f"Extract order data from: \"{message}\"\n"
                    f"Respond with ONLY a valid JSON object."
                )
                response = await self._call_groq(system_prompt, corrective)
                return self._parse_json(response)
            except Exception as e2:
                logger.error(f"Order extraction retry failed: {e2}")
                return None

    # ── Inventory update extraction ───────────────────────────────────

    async def extract_inventory_update(self, message: str) -> Optional[dict]:
        """
        Extract inventory update from messages like 'added 5kg flour'.
        Returns dict with: item, quantity, unit, direction.
        """
        system_prompt = (
            "You are a structured data extractor for inventory updates.\n"
            "Respond ONLY with a JSON object — no explanation, no markdown.\n\n"
            "Extract:\n"
            "- item (string): the inventory item name\n"
            "- quantity (number): how much\n"
            "- unit (string): the unit (kg, pieces, packs, grams, liters, etc.)\n"
            "- direction (string): 'add' if adding/buying/restocking, 'remove' if using/deducting/consuming\n"
        )

        try:
            response = await self._call_groq(system_prompt, message)
            return self._parse_json(response)
        except Exception as e:
            logger.error(f"Inventory extraction failed: {e}")
            return self._regex_inventory_fallback(message)

    # ── Materials extraction (BOM learning) ───────────────────────────

    async def extract_materials(self, message: str) -> Optional[list]:
        """
        Extract bill of materials from user's description.
        e.g. '200g flour, 2 eggs, 100g butter' -> [{item, qty, unit}, ...]
        """
        system_prompt = (
            "You are a structured data extractor for product materials/ingredients.\n"
            "Respond ONLY with a JSON array — no explanation, no markdown.\n\n"
            "Each element should have:\n"
            "- item (string): the material/ingredient name\n"
            "- quantity (number): how much per unit of product\n"
            "- unit (string): the unit (grams, pieces, ml, meters, etc.)\n"
        )

        try:
            response = await self._call_groq(system_prompt, message)
            parsed = self._parse_json(response)
            if isinstance(parsed, list):
                return parsed
            return None
        except Exception as e:
            logger.error(f"Materials extraction failed: {e}")
            return None

    # ── Internal helpers ──────────────────────────────────────────────

    async def _call_groq(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1,
    ) -> str:
        """Make a rate-limited call to the GROQ API with circuit breaker."""
        self._ensure_initialized()

        if self._circuit_open:
            raise RuntimeError("GROQ circuit breaker is open")

        async with self._semaphore:
            try:
                completion = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=temperature,
                    max_tokens=1024,
                )
                self._consecutive_failures = 0
                return completion.choices[0].message.content
            except Exception as e:
                self._consecutive_failures += 1
                from app.core.config import settings
                if self._consecutive_failures >= settings.GROQ_CIRCUIT_BREAKER_THRESHOLD:
                    self._circuit_open = True
                    logger.critical(
                        f"GROQ circuit breaker OPEN after {self._consecutive_failures} failures"
                    )
                raise

    def _parse_json(self, text: str) -> dict | list | None:
        """Parse JSON from GROQ response, stripping markdown fences if present."""
        # Remove markdown code fences
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON within the text
            json_match = re.search(r'[\[{].*[\]}]', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            raise

    def _regex_inventory_fallback(self, message: str) -> Optional[dict]:
        """
        Fallback regex extractor for inventory updates
        when GROQ is unavailable.
        """
        message_lower = message.lower().strip()

        # Determine direction
        add_keywords = ["added", "add", "bought", "received", "restocked", "got"]
        remove_keywords = ["used", "removed", "consumed", "deducted", "spent", "took"]

        direction = None
        for kw in add_keywords:
            if kw in message_lower:
                direction = "add"
                break
        if not direction:
            for kw in remove_keywords:
                if kw in message_lower:
                    direction = "remove"
                    break

        if not direction:
            return None

        # Try to extract quantity + unit + item
        pattern = r'(\d+\.?\d*)\s*(kg|g|grams|pieces|packs?|liters?|l|ml|dozen|units?)?\s+(.+?)$'
        cleaned = message_lower
        for kw in add_keywords + remove_keywords:
            cleaned = cleaned.replace(kw, "").strip()

        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            return {
                "item": match.group(3).strip(),
                "quantity": float(match.group(1)),
                "unit": match.group(2) or "pieces",
                "direction": direction,
            }

        return None

    def reset_circuit_breaker(self) -> None:
        """Manually reset the circuit breaker."""
        self._circuit_open = False
        self._consecutive_failures = 0
        logger.info("GROQ circuit breaker reset")


# Singleton instance — lazy init, no settings access at import time
groq_service = GroqService()
