# SmallBiz Telegram Bot — Implementation Plan

## Context

A multi-tenant Telegram bot platform where each Telegram user maps to an isolated small business. The primary use case is a home baker / micro-business owner who wants to manage orders and inventory through natural conversation — no spreadsheet, no separate app. GROQ LLM parses free-form messages into structured orders. FastAPI serves both the Telegram webhook and an admin panel. APScheduler drives all time-based notifications.

**Inventory is tracked via three paths:**

1. Owner explicitly texts an inventory update ("added 10kg flour", "removed 2 eggs")  
2. Bot auto-deducts from a **recipe/bill-of-materials** when an order is completed — recipes are learned interactively: first time a new item is ordered, bot asks follow-up questions ("What does 1 Chocolate Cake use from your inventory?")  
3. Admin UI — direct quantity/threshold edits without going through the bot

---

## Tech Stack

| Concern | Choice |
| :---- | :---- |
| Backend | FastAPI \+ Uvicorn |
| Database | MongoDB \+ Motor (async) |
| Telegram | python-telegram-bot v21 (webhook mode) |
| NLP | GROQ API — `llama-3.3-70b-versatile` |
| Scheduling | APScheduler 3.x (MongoDB job store) |
| Admin UI | Jinja2 templates \+ minimal CSS | Can also use Streamlit for building UI
| PDF | ReportLab |
| Auth | passlib/bcrypt \+ python-jose JWT |

---

## Project Structure

smallbiz-bot/

├── app/

│   ├── main.py                        \# FastAPI app \+ lifespan

│   ├── core/

│   │   ├── config.py                  \# pydantic-settings BaseSettings

│   │   ├── database.py                \# Motor client \+ index creation

│   │   └── security.py                \# JWT session helpers

│   ├── models/

│   │   ├── business.py                \# Business (tenant anchor)

│   │   ├── order.py                   \# Order \+ OrderStatus enum

│   │   ├── inventory.py               \# InventoryItem

│   │   ├── product\_bom.py             \# ProductBOM — materials consumed per product unit ← new

│   │   ├── customer.py                \# Customer

│   │   ├── payment.py                 \# Payment

│   │   ├── reminder.py                \# Reminder

│   │   └── invoice.py                 \# Invoice

│   ├── services/

│   │   ├── groq\_service.py            \# NLP pipeline (intent \+ extraction)

│   │   ├── order\_service.py           \# Order CRUD \+ business logic

│   │   ├── inventory\_service.py       \# Inventory CRUD \+ threshold checks

│   │   ├── bom\_service.py             \# BOM CRUD \+ auto-deduction on completion ← new

│   │   ├── customer\_service.py        \# Customer CRUD \+ history

│   │   ├── reminder\_service.py        \# Schedule/cancel Reminder docs

│   │   ├── payment\_service.py         \# Payment recording \+ UPI links

│   │   ├── invoice\_service.py         \# PDF generation via ReportLab

│   │   ├── summary\_service.py         \# Aggregation for daily/weekly reports

│   │   └── notification\_service.py    \# Telegram send wrappers

│   ├── bot/

│   │   ├── application.py             \# Build PTB Application

│   │   ├── webhook.py                 \# POST /webhook/{token} route

│   │   ├── handlers/

│   │   │   ├── start.py               \# /start /help

│   │   │   ├── natural\_language.py    \# Free-form message orchestrator ← critical

│   │   │   ├── orders.py              \# /orders /neworder /completeorder

│   │   │   ├── inventory.py           \# /inventory /addstock /removestock /lowstock

│   │   │   ├── bom.py                 \# /bom /setbom — materials-per-product mgmt ← new

│   │   │   ├── customers.py           \# /customers /customer

│   │   │   ├── payments.py            \# /recordpayment /unpaid /revenue

│   │   │   ├── summary.py             \# /summary /weeklysummary

│   │   │   ├── callbacks.py           \# InlineKeyboard callback router

│   │   │   └── error.py               \# Global error handler

│   │   └── keyboards/

│   │       ├── order\_keyboards.py

│   │       └── main\_menu.py

│   ├── admin/

│   │   ├── router.py

│   │   ├── auth.py

│   │   ├── dependencies.py

│   │   ├── routes/

│   │   │   ├── dashboard.py

│   │   │   ├── businesses.py

│   │   │   ├── orders.py

│   │   │   ├── inventory.py

│   │   │   └── logs.py

│   │   └── templates/

│   │       ├── base.html

│   │       ├── login.html

│   │       ├── dashboard.html

│   │       ├── businesses.html

│   │       ├── orders.html

│   │       └── logs.html

│   └── scheduler/

│       ├── scheduler.py               \# APScheduler setup with MongoDB job store

│       └── jobs/

│           ├── deadline\_reminders.py  \# Runs every 5 min ← critical

│           ├── low\_stock\_alerts.py    \# Runs hourly — checks all 3 deduction paths

│           └── daily\_summary.py       \# Cron at 20:00 per business timezone

├── static/css/admin.css

├── scripts/

│   ├── setup\_webhook.py

│   ├── seed\_data.py

│   └── migrate\_db.py

├── tests/

├── requirements.txt

├── .env.example

└── docker-compose.yml

---

## MongoDB Collections

### `businesses` — tenant anchor

telegram\_user\_id (int, UNIQUE INDEX)

business\_name, owner\_name, timezone, currency\_symbol

low\_stock\_threshold (int, default 5\)

reminder\_hours\_before (list\[int\], default \[24, 2\])

daily\_summary\_time (str "HH:MM")

total\_orders\_lifetime (int) ← atomic increment for order numbering

### `orders`

business\_id (int) ← partition key, first field on all indexes

order\_number (str, "ORD-2024-001", UNIQUE per business)

customer\_name, customer\_id (ref → customers)

items: \[{name, quantity, unit\_price, total\_price}\]

deadline (datetime UTC), deadline\_raw (original string)

status: pending | in\_progress | ready | completed | cancelled

subtotal, discount, total\_amount, amount\_paid, payment\_status

reminders\_sent: \[datetime\]

original\_message (raw NL text)

Compound indexes: {business\_id,status}, {business\_id,deadline}, {deadline} for scheduler

### `inventory`

business\_id, name, name\_normalized (lowercase, for matching)

quantity (float), unit, cost\_price, selling\_price

low\_stock\_threshold (float), low\_stock\_alerted (bool, reset on restock)

last\_deduction\_source: "explicit" | "recipe" | "admin"  ← audit trail

Unique index: {business\_id, name\_normalized}

### `product_bom` — bill of materials per product/order-item type (NEW)

Generalized for any business type: bakery uses flour+eggs, tailor uses fabric+thread,

juice shop uses fruits+ice, print shop uses paper+ink. No food-specific assumptions.

business\_id

product\_name\_normalized (str)   ← normalized order item name, e.g. "chocolate cake", "shirt alteration"

materials: \[

  { inventory\_item\_name: str, inventory\_item\_normalized: str, quantity\_per\_unit: float, unit: str }

\]

confirmed: bool                 ← False \= still in learning mode (bot asked, owner hasn't confirmed yet)

created\_at, updated\_at

Examples:

  Bakery  → product="chocolate cake",  materials=\[{flour,200g},{butter,100g},{eggs,2},{cocoa,50g}\]

  Tailor  → product="shirt alteration",materials=\[{thread,5m},{buttons,4 pieces}\]

  Florist → product="bouquet",         materials=\[{roses,12 pieces},{wrapping paper,1 sheet}\]

Unique index: {business\_id, product\_name\_normalized}

### `customers`

business\_id, name, name\_normalized

total\_orders (int), total\_spent (float), last\_order\_date

phone, telegram\_username, notes

### `payments`

business\_id, order\_id, amount, method (cash/upi/card), recorded\_at

### `reminders`

business\_id, order\_id

scheduled\_at (datetime UTC), hours\_before\_deadline

sent (bool), sent\_at, failed, error\_message

Primary scheduler index: {sent, scheduled\_at}

### `activity_logs`

business\_id, action, entity\_type, entity\_id, details (dict)

TTL index: expire after 90 days

---

## Multi-Tenant Isolation Strategy

- `telegram_user_id` is the partition key stored as `business_id` on every document.  
- All service classes are instantiated with a bound `business_id`; DB queries always include it as the first filter field to hit compound indexes.  
- Callback data format: `order:complete:ORD-2024-047` — handlers ALWAYS re-query with `{order_number, business_id}` to prevent cross-tenant access.  
- Admin panel is the only layer that queries without `business_id`, protected by JWT session.

---

## GROQ NLP Pipeline (groq\_service.py)

### Two-step chain

1. **Intent classification** — cheap call, returns one of: `new_order | update_order | check_order | add_stock | remove_stock | set_recipe | question | unknown`  
2. **Entity extraction** — specialized prompt based on intent, always requests JSON output.

### Order extraction prompt (condensed)

System: You are a structured data extractor for a small business.

        Current datetime: {current\_datetime} (business timezone: {timezone})

        Respond ONLY with a JSON object — no explanation, no markdown.

        Extract: customer\_name, items\[{name, quantity}\], deadline (ISO 8601),

                 deadline\_confidence (high/medium/low), special\_instructions,

                 is\_valid\_order (bool), reason\_if\_invalid.

        Rules: nearest upcoming date if relative; default quantity=1 if omitted.

User: "order for priya for 2 cakes for friday 8 pm"

→ {"customer\_name":"Priya","items":\[{"name":"cake","quantity":2}\],

   "deadline":"2024-01-19T20:00:00","deadline\_confidence":"high",

   "special\_instructions":null,"is\_valid\_order":true}

### Reliability

- Retry once on JSON parse failure with corrective prompt.  
- Fallback to regex extractor if GROQ unavailable (circuit breaker after 3 failures).  
- `asyncio.Semaphore` rate limiter to stay within GROQ free-tier limits.

---

## Bot Commands

/start              Register business, show welcome

/help               Full command reference

\# Orders

/neworder           Guided wizard (ConversationHandler)

/orders             Paginated active orders

/order \<num\>        View specific order

/completeorder      Mark complete (inline keyboard)

/cancelorder        Cancel with confirmation

\# Inventory

/inventory          Full stock view with quantities \+ thresholds

/addstock           Add items ("added 10kg flour")

/removestock        Manually deduct items

/lowstock           Items at or below threshold (instant alert)

/setprice           Set unit selling price

/setthreshold       Set low-stock alert threshold for an item

\# Bill of Materials (works for any business type)

/bom \<product\>      View what materials 1 unit of a product uses

/setbom \<product\>   Define/update materials for a product (guided wizard)

/boms               List all products that have a defined BOM

\# Customers

/customers          All customers

/customer \<name\>    Profile \+ order history

/topcustomers       Top 5 by revenue

\# Payments

/recordpayment      Record payment for order

/unpaid             Orders with outstanding balance

/revenue            Revenue summary (today/week/month)

\# Reporting

/summary            Today's summary

/weeklysummary      This week's summary

/invoice \<num\>      Generate \+ send PDF invoice

\# Settings

/settings           View/edit business settings

/settimezone        Set timezone

/setreminders       Configure reminder hours

\# Admin only

/broadcast          Message all customers with Telegram handles

### Natural Language Message Flow — Order Creation

User: "order for priya for 2 cakes for friday 8 pm"

  → classify\_intent()  → "new\_order"

  → extract\_order()    → {customer:"Priya", items:\[{name:"cake",qty:2}\], deadline:...}

  → find\_or\_create\_customer("Priya")

  → create\_order()     → ORD-2024-047

  → schedule\_reminders() → Reminder docs at (deadline-24h) and (deadline-2h)

  → bom\_service.check\_bom("cake")

      ┌─ BOM exists & confirmed=True → preview expected deduction in confirmation

      └─ BOM missing or unconfirmed  → bot appends:

           "I don't know what materials 1 Cake uses yet.

            What inventory does 1 Cake consume? (e.g. '200g flour, 2 eggs, 100g butter')

            \[Set Materials\] \[Skip for now\]"

  → reply: "Order \#ORD-2024-047 created for Priya — 2 Cakes by Friday 8pm

            On completion, inventory will auto-deduct: 400g flour, 4 eggs, 200g butter

            \[View\] \[Edit\] \[Cancel\]"

### Natural Language Message Flow — Explicit Inventory Update

User: "added 5kg flour" / "used 3 eggs" / "bought 2 packs butter"

  → classify\_intent()  → "add\_stock" / "remove\_stock"

  → extract\_inventory\_update() → {item:"flour", quantity:5, unit:"kg", direction:"add"}

  → inventory\_service.add\_stock() / deduct\_stock()

  → reply: "Flour updated: 3kg → 8kg"

  → if quantity now below threshold: immediate low-stock warning appended

### Natural Language Message Flow — BOM Learning (ConversationHandler)

Bot: "What inventory does making 1 Chocolate Cake consume?"

User: "200g flour, 2 eggs, 100g butter, 50g cocoa powder"

  → groq\_service.extract\_materials()

      → \[{item:"flour",qty:200,unit:"grams"}, {item:"eggs",qty:2,unit:"pieces"}, ...\]

  → bot shows parsed list:

      "Got it\! 1 Chocolate Cake uses:

       • 200g Flour   • 2 Eggs   • 100g Butter   • 50g Cocoa Powder

       \[Confirm\] \[Edit\] \[Skip\]"

  → on Confirm: BOM saved with confirmed=True

  → future orders for "chocolate cake" auto-deduct on completion

  → if any of those inventory items don't exist yet:

      "I noticed 'Cocoa Powder' isn't in your inventory yet.

       How much do you have? \[Add to Inventory\] \[Skip\]"

### Callback Data Format

order:complete:ORD-2024-047

order:cancel:ORD-2024-047

order:view:ORD-2024-047

inventory:restock:{item\_id}

payment:record:{order\_id}

page:orders:2

---

## Reminder Scheduler Design

**One polling job, not per-order jobs** — avoids thousands of scheduled jobs.

\# runs every 5 minutes

async def check\_and\_send\_deadline\_reminders():

    now \= datetime.utcnow()

    window\_start \= now \- timedelta(minutes=10)  \# catch near-misses

    reminders \= await db.reminders.find({

        "sent": False,

        "failed": False,

        "scheduled\_at": {"$lte": now, "$gte": window\_start}

    }).to\_list(100)

    for reminder in reminders:

        \# skip completed/cancelled orders

        \# send Telegram message

        \# mark sent=True or failed=True

**Lifecycle:**

- Order created → `schedule_reminders()` inserts Reminder docs  
- Deadline changed → delete unsent reminders, re-schedule  
- Order completed/cancelled → delete all unsent reminders

**Other scheduled jobs:**

- `low_stock_alerts` — hourly, queries `{quantity: {$lte: low_stock_threshold}}`  
- `daily_summary` — cron 20:00, per-business timezone handled inside job

---

## Admin Panel Routes

GET/POST /admin/login

GET      /admin/                 Dashboard (stats cards, recent activity)

GET      /admin/businesses       All businesses paginated

GET      /admin/businesses/{id}  Business detail \+ orders \+ inventory

POST     /admin/businesses/{id}/toggle  Activate/deactivate

GET      /admin/orders           All orders (cross-business, filterable)

GET      /admin/orders/{id}      Order detail

POST     /admin/orders/{id}/status  Update status

GET      /admin/inventory        Cross-business inventory view (inline edits, CSV import)

GET      /admin/boms             All product BOMs — view/edit materials per product

POST     /admin/boms/{id}        Update BOM materials, confirm/unconfirm BOM

GET      /admin/logs             Activity logs (business filter \+ date range)

GET      /admin/system           Webhook status, scheduler status, DB stats

POST     /admin/system/webhook   Re-register webhook

Dashboard cards: total businesses, orders today, revenue today, orders due next 24h (across all businesses), system health.

---

## Three-Path Inventory Tracking System

### Path 1 — Explicit Text from Owner

Owner simply tells the bot about stock changes. NLP extracts item, quantity, direction.

"added 10kg flour"       → add\_stock("flour", 10, "kg")

"used 3 eggs"            → deduct\_stock("eggs", 3, "pieces")

"bought 2 packs butter"  → add\_stock("butter", 2, "packs")

"I'm out of cocoa"       → set\_stock("cocoa", 0\) \+ immediate low-stock alert

Handled in: `groq_service.extract_inventory_update()` \+ `inventory_service`

### Path 2 — Auto-Deduction from Orders via BOM

When an order item has a confirmed BOM, completing the order auto-deducts materials.

Order ORD-2024-047 completed (2 Chocolate Cakes)

  → bom\_service.get\_bom("chocolate cake") → confirmed BOM found

  → for each material: deduct quantity \* order\_item.quantity

       flour: \-400g, eggs: \-4, butter: \-200g, cocoa: \-100g

  → if any inventory now \< threshold: fire low-stock alert immediately

  → log deduction source as "bom\_auto" in inventory item

If BOM not confirmed: bot prompts owner to confirm or manually specify deduction.

BOM learning triggers the **first** time each new product appears in an order. The bot asks once; once confirmed it never asks again for that product.

### Path 3 — Admin UI

Admin panel has a full inventory management page:

- Table view: all items, quantity, unit, threshold, last deduction source \+ date  
- Inline edit: click quantity/threshold cell to edit in place, Save button  
- Add new item form: name, unit, opening quantity, threshold  
- Bulk CSV import: owner can upload a spreadsheet of initial stock  
- Audit log: shows every add/deduct with source (explicit / bom\_auto / admin)

Admin BOM management:

- List all products with BOM status (confirmed / learning / none)  
- Edit BOM materials for any product inline  
- Preview: "If order of 5 units placed, will consume: X, Y, Z"

### Low-Stock Alert Logic

Three triggers, all send Telegram notification \+ log to activity\_logs:

1. **Real-time**: immediately after any deduction that crosses the threshold  
2. **Hourly job**: `low_stock_alerts.py` scans inventory for items below threshold that haven't been alerted in the last 6 hours (to avoid spam)  
3. **Daily summary**: always includes low-stock section even if alerts were sent

Alert message format:

⚠ Low Stock Alert

• Flour: 300g remaining (threshold: 500g)

• Butter: 1 pack remaining (threshold: 3 packs)

\[Restock Flour\] \[Restock Butter\] \[View All Inventory\]

---

## Suggested Additional Features (implement after core)

1. **PDF Invoice Generation** (`/invoice ORD-2024-047`) ReportLab generates invoice PDF in memory, bot sends as document file. Includes: business header, line items table, totals, payment status.  
     
2. **UPI Payment Links** Generate `upi://pay?pa=...&am=500&tn=ORD-2024-047` deep link as clickable button. Track partial payments; auto-update `payment_status` from unpaid → partial → paid.  
     
3. **Customer Loyalty Tracking** After 10 orders, proactively suggest a discount: "Priya has ordered 10 times\!" `/customer Priya` shows: lifetime spend, favorite item, average order value.  
     
4. **BOM-based Auto-Deduction** On order complete, `bom_service` looks up materials per product unit, multiplies by quantity ordered, deducts from inventory. Prompts for confirmation if BOM is missing. Works for any business type — not food-specific.  
     
5. **Quick Reorder Suggestion** When customer name appears in a new message, bot checks history and offers: "Last time Priya ordered 2 Chocolate Cakes (₹700). Same again? \[Yes\] \[Modify\]"  
     
6. **Broadcast to Customers** (`/broadcast <message>`) Send message to all customers who have a `telegram_username` on file. Rate limited to 1 message/second. Track delivery count.  
     
7. **Daily/Weekly Summary Auto-Push** Automated evening report with: active orders, today's revenue, tomorrow's deadlines, low stock alerts. Time configurable per business timezone.

---

## Implementation Phases

### Phase 1 — Foundation (Days 1–5)

1. Scaffold folder structure, `requirements.txt`, `.env.example`  
2. `core/config.py` — BaseSettings reading all env vars  
3. `core/database.py` — Motor client, collection accessors, `create_indexes()`  
4. All Pydantic v2 models in `models/`  
5. `main.py` — FastAPI lifespan: indexes \+ scheduler start/stop  
6. `services/groq_service.py` — intent classification \+ order extraction  
7. Bot bootstrap: `bot/application.py`, `bot/webhook.py`, `/start`, `/help`, error handler  
8. `scripts/setup_webhook.py` — register webhook with Telegram

### Phase 2 — Core Order \+ Inventory (Days 6–10)

9. `services/order_service.py` — full CRUD, order number generation (atomic `$inc`)  
10. `services/customer_service.py` — `find_or_create()` with name normalization  
11. `services/reminder_service.py` — schedule/cancel Reminder documents  
12. `bot/handlers/natural_language.py` — orchestrate intent → extraction → create → confirm  
13. `bot/handlers/orders.py` — `/orders` paginated, `/completeorder`, `/cancelorder`, callbacks  
14. `services/inventory_service.py` — CRUD \+ fuzzy name matching, three-path deduction  
15. `bot/handlers/inventory.py` — all inventory commands (Path 1: explicit text updates)  
16. `services/bom_service.py` — BOM CRUD, material deduction, `check_bom()` helper  
17. `bot/handlers/bom.py` — `/bom /setbom /boms` \+ BOM learning ConversationHandler (Path 2\)  
18. Wire BOM auto-deduction into `order_service.complete_order()`

### Phase 3 — Payments \+ Scheduler (Days 11–14)

16. `services/payment_service.py` \+ `bot/handlers/payments.py`  
17. `scheduler/scheduler.py` — APScheduler with MongoDB job store  
18. `scheduler/jobs/deadline_reminders.py` — 5-min polling job  
19. `scheduler/jobs/low_stock_alerts.py` — hourly job  
20. `services/summary_service.py` \+ `scheduler/jobs/daily_summary.py`  
21. `services/notification_service.py` — Telegram send wrappers

### Phase 4 — Admin Panel (Days 15–20)

22. `admin/auth.py` — bcrypt password \+ JWT session cookie  
23. `admin/dependencies.py` — `get_current_admin()` FastAPI dependency  
24. `admin/routes/dashboard.py` \+ `templates/dashboard.html`  
25. Business, orders, logs routes \+ templates  
26. `admin/routes/inventory.py` — inline-edit quantities, thresholds, add new item, CSV import (Path 3\)  
27. `admin/routes/boms.py` — view/edit/confirm BOMs per product per business  
28. `admin/routes/system.py` — webhook status, scheduler status  
29. `static/css/admin.css`

### Phase 5 — Advanced Features \+ Polish (Days 21–25)

28. `services/invoice_service.py` — ReportLab PDF \+ `/invoice` command  
29. UPI payment link generation in `payment_service.py`  
30. Quick reorder suggestion in `natural_language.py`  
31. Smart inventory deduction on order completion  
32. `/broadcast` handler with rate limiting  
33. Integration tests in `tests/`  
34. Rate limiting middleware (30 req/min per user)  
35. `Dockerfile` \+ `docker-compose.yml`

---

## Critical Implementation Notes

### Webhook mode (not polling)

\# bot/webhook.py

@router.post("/webhook/{token}")

async def telegram\_webhook(token: str, request: Request):

    if token \!= settings.WEBHOOK\_SECRET:

        raise HTTPException(403)

    update \= Update.de\_json(await request.json(), application.bot)

    await application.process\_update(update)

    return {"ok": True}

\# application.initialize() at startup, do NOT call application.start()

### Order number generation (atomic, no race condition)

result \= await db.businesses.find\_one\_and\_update(

    {"telegram\_user\_id": business\_id},

    {"$inc": {"total\_orders\_lifetime": 1}},

    return\_document=True

)

return f"ORD-{datetime.utcnow().year}-{result\['total\_orders\_lifetime'\]:04d}"

### DateTime handling

- All datetimes stored as UTC in MongoDB.  
- `business.timezone` injected into GROQ prompt for relative date resolution only.  
- Display formatting localizes to business timezone.

---

## Verification Checklist

**Orders \+ NLP**

- [ ] "order for priya for 2 cakes for friday 8 pm" → structured confirmation \+ BOM prompt if missing  
- [ ] Reminder fires 24h and 2h before deadline  
- [ ] `/completeorder` → order marked complete, reminder cancelled

**Inventory — Path 1 (explicit text)**

- [ ] "added 10kg flour" → flour quantity increases  
- [ ] "used 3 eggs" → egg quantity decreases  
- [ ] Immediate low-stock alert when quantity crosses threshold

**Inventory — Path 2 (BOM auto-deduction)**

- [ ] First order of unknown product → bot asks for materials, shows parsed list, owner confirms  
- [ ] Second order of same product → no BOM prompt; on completion auto-deducts materials  
- [ ] `/bom <product>` → shows confirmed materials with quantities per unit  
- [ ] BOM deduction multiplies correctly by ordered quantity

**Inventory — Path 3 (Admin UI)**

- [ ] Admin `/admin/inventory` loads; inline edit of quantity/threshold saves to DB  
- [ ] Admin `/admin/boms` shows all products; edit materials; confirm/unconfirm  
- [ ] CSV import adds new inventory items in bulk

**Multi-tenancy**

- [ ] Two different Telegram users cannot see each other's orders, inventory, or BOMs

**Payments \+ Reporting**

- [ ] `/unpaid` shows orders with outstanding balance  
- [ ] `/invoice ORD-XXXX` sends PDF via Telegram  
- [ ] Daily summary includes low-stock section and tomorrow's orders

**Admin**

- [ ] `/admin/` requires login; dashboard shows cross-business stats  
- [ ] System page shows webhook \+ scheduler status

