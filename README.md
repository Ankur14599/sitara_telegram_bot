# 🌟 SmallBiz Bot — Sitara

> **Your AI-powered small business assistant on Telegram.**  
> Manage orders, inventory, customers, payments, and reports — all through natural conversation.

---

## 📖 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Environment Variables](#environment-variables)
  - [Running with Podman (Recommended)](#running-with-podman-recommended)
  - [Running Locally (No Container)](#running-locally-no-container)
- [Ngrok Setup (Webhook Tunneling)](#ngrok-setup-webhook-tunneling)
- [Bot Commands](#bot-commands)
- [Natural Language Examples](#natural-language-examples)
- [Admin Dashboard](#admin-dashboard)
- [Rate Limiting & Abuse Prevention](#rate-limiting--abuse-prevention)
- [Automated Scheduler Jobs](#automated-scheduler-jobs)
- [API Endpoints](#api-endpoints)
- [Configuration Reference](#configuration-reference)

---

## Overview

**SmallBiz Bot** is a multi-tenant Telegram bot built for small business owners. Instead of juggling spreadsheets, WhatsApp messages, and paper notes, owners can simply chat with **Sitara** — the bot's AI assistant — in plain language to manage their entire business workflow.

Sitara understands natural language powered by **GROQ's LLaMA 3.3 70B** model, so you can say things like:

- *"Order for Priya for 2 cakes by Friday 8pm"*
- *"Added 10kg flour"*
- *"How many orders do I have today?"*
- *"Hey Sitara, how's it going?"*

...and Sitara handles the rest.

### 📱 Talk to Sitara Now!
- **Link:** [https://t.me/Ai_sitara_bot](https://t.me/Ai_sitara_bot)
- **Handle:** `@Ai_sitara_bot`

*(Scan the QR code to start chatting!)*  
<img src="qr_code.png" alt="Sitara Bot QR Code" width="200" />

---

## Features

### 🤖 AI Assistant — Sitara
- Warm, conversational personality — not a rigid command bot
- Handles greetings, chitchat, and casual conversation naturally
- Understands free-form business instructions
- Powered by **GROQ LLaMA 3.3 70B** for intent classification and entity extraction
- Gracefully handles unknown messages instead of returning errors

### 📦 Order Management
- Create orders through natural conversation
- Guided `/neworder` wizard for step-by-step creation
- View, filter, and paginate active orders
- Mark orders as complete or cancelled
- Inline action buttons on every order card
- Quick reorder suggestions for returning customers

### 📊 Inventory Tracking
- Add and remove stock via natural language or commands
- Auto-deduction of materials on order completion (via BOM)
- Low-stock alerts with configurable thresholds
- Per-item pricing and unit management

### 🧾 Bill of Materials (BOM)
- Define material recipes per product (e.g. *"1 chocolate cake needs 200g flour, 2 eggs"*)
- Automatic stock deduction when orders are completed
- Deduction preview shown at order creation time
- BOM learning prompts for unknown products

### 👥 Customer Management
- Auto-creates customer profiles from order mentions
- Full order history per customer
- Top customers by revenue
- Outstanding balance tracking per customer

### 💰 Payments
- Record full or partial payments
- UPI payment link generation
- Outstanding/unpaid order summaries
- Revenue reports — daily, weekly, monthly

### 📋 Reports & Invoices
- Daily and weekly business summaries
- PDF invoice generation per order (via ReportLab)
- Broadcast messages to all registered businesses (admin only)

### ⚙️ Admin Dashboard
- Web-based admin panel (JWT-authenticated)
- Dashboard with key metrics
- Manage businesses, orders, inventory, and BOMs
- System logs viewer
- Built with FastAPI + Jinja2 templates

### ⏰ Automated Scheduler
- **Deadline reminders** — notifies owners 24h and 2h before order deadlines
- **Low-stock alerts** — daily check and Telegram notification
- **Daily business summary** — auto-sent at configurable time (default 8 PM)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Telegram User                        │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS (webhook)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    ngrok Tunnel                             │
│              (forwards to localhost:8000)                   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                FastAPI Application (Uvicorn)                │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Webhook      │  │ Admin Panel  │  │  Health Check    │  │
│  │ /webhook/*** │  │ /admin/***   │  │  /health         │  │
│  └──────┬───────┘  └──────────────┘  └──────────────────┘  │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           python-telegram-bot (PTB)                  │   │
│  │                                                      │   │
│  │  Rate Limit Middleware → Handler Router              │   │
│  │                                                      │   │
│  │  /start  /help  /orders  /inventory  /bom  ...       │   │
│  │                          ↓                           │   │
│  │              Natural Language Handler                │   │
│  └────────────────────┬─────────────────────────────────┘   │
│                       │                                     │
│         ┌─────────────▼──────────────┐                     │
│         │       GROQ Service         │                     │
│         │  • classify_intent()       │                     │
│         │  • extract_order()         │                     │
│         │  • chat_with_sitara()      │                     │
│         │  • Per-user rate limiting  │                     │
│         └─────────────┬──────────────┘                     │
│                       │                                     │
│    ┌──────────────────▼────────────────────┐               │
│    │           Service Layer               │               │
│    │  OrderService  │  InventoryService    │               │
│    │  CustomerSvc   │  BOMService          │               │
│    │  PaymentSvc    │  ReminderService     │               │
│    └──────────────────┬────────────────────┘               │
│                       │                                     │
└───────────────────────┼─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    MongoDB (Motor async)                    │
│   businesses │ orders │ inventory │ customers │ payments    │
└─────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
SmallBiz Telegram Bot/
├── app/
│   ├── main.py                     # FastAPI entrypoint + lifespan
│   ├── core/
│   │   ├── config.py               # Pydantic settings (reads .env)
│   │   └── database.py             # MongoDB async connection + indexes
│   ├── bot/
│   │   ├── application.py          # PTB Application builder + handler registry
│   │   ├── middleware.py           # Global rate-limit middleware (30 msg/min)
│   │   ├── webhook.py              # Webhook route (/webhook/<secret>)
│   │   ├── handlers/
│   │   │   ├── start.py            # /start, /help
│   │   │   ├── natural_language.py # NL orchestrator — Sitara's brain
│   │   │   ├── orders.py           # Order commands + conversation wizard
│   │   │   ├── inventory.py        # Inventory commands
│   │   │   ├── bom.py              # BOM commands + conversation wizard
│   │   │   ├── payments.py         # Payment commands
│   │   │   ├── summary.py          # Summary commands
│   │   │   ├── admin.py            # Broadcast handler
│   │   │   ├── callbacks.py        # Inline keyboard callback router
│   │   │   └── error.py            # Global error handler
│   │   └── keyboards/
│   │       └── order_keyboards.py  # Inline keyboard builders
│   ├── services/
│   │   ├── groq_service.py         # GROQ LLM — intent + extraction + Sitara chat
│   │   ├── order_service.py        # Order CRUD + business logic
│   │   ├── inventory_service.py    # Stock management + low-stock checks
│   │   ├── customer_service.py     # Customer profiles + stats
│   │   ├── bom_service.py          # Bill of Materials + auto-deduction
│   │   ├── payment_service.py      # Payment recording + UPI links
│   │   ├── invoice_service.py      # PDF invoice generation
│   │   ├── reminder_service.py     # Deadline reminder scheduling
│   │   ├── notification_service.py # Telegram push notifications
│   │   └── summary_service.py      # Business summary generation
│   ├── models/
│   │   ├── business.py             # Business (tenant) model
│   │   ├── order.py                # Order model
│   │   ├── inventory.py            # Inventory item model
│   │   ├── customer.py             # Customer model
│   │   ├── payment.py              # Payment model
│   │   ├── product_bom.py          # BOM model
│   │   ├── reminder.py             # Reminder model
│   │   └── invoice.py              # Invoice model
│   ├── scheduler/
│   │   ├── scheduler.py            # APScheduler setup (MongoDB jobstore)
│   │   └── jobs/
│   │       ├── deadline_reminders.py
│   │       ├── low_stock_alerts.py
│   │       └── daily_summary.py
│   └── admin/
│       ├── router.py               # Admin panel router
│       ├── auth.py                 # JWT authentication
│       ├── dependencies.py         # Auth dependencies
│       ├── routes/                 # Admin route handlers
│       └── templates/              # Jinja2 HTML templates
├── static/                         # Static files for admin UI
├── tests/                          # Test suite
├── scripts/                        # Utility scripts
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env                            # Local secrets (never commit!)
└── .env.example                    # Template for environment setup
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.11 |
| **Web Framework** | FastAPI + Uvicorn |
| **Telegram SDK** | python-telegram-bot 21.5 (webhook mode) |
| **AI / NLP** | GROQ API — LLaMA 3.3 70B Versatile |
| **Database** | MongoDB 7.0 (async via Motor) |
| **Scheduler** | APScheduler 3.10 (MongoDB jobstore) |
| **PDF Generation** | ReportLab |
| **Admin UI** | Jinja2 templates |
| **Auth** | JWT (python-jose) + bcrypt |
| **Container Runtime** | Podman + podman-compose |
| **Tunnel (dev)** | ngrok |

---

## Getting Started

### Prerequisites

- [Podman](https://podman.io/getting-started/installation) + [podman-compose](https://github.com/containers/podman-compose)
- [ngrok](https://ngrok.com/download) account (free tier works)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A [GROQ API key](https://console.groq.com)

---

### Environment Variables

Copy the example and fill in your values:

```bash
cp .env.example .env
```

```env
# === Telegram Bot ===
TELEGRAM_BOT_TOKEN=<your_bot_token_from_botfather>
WEBHOOK_SECRET=<any_random_hex_string>
WEBHOOK_URL=https://<your-ngrok-domain>

# === MongoDB ===
MONGODB_URI=mongodb://smallbiz-mongodb:27017   # use this for Podman
MONGODB_DB_NAME=smallbiz_bot

# === GROQ API ===
GROQ_API_KEY=<your_groq_api_key>
GROQ_MODEL=llama-3.3-70b-versatile

# === Rate Limiting (optional tuning) ===
GROQ_USER_CALLS_PER_WINDOW=20   # AI calls per user per window
GROQ_USER_WINDOW_SECONDS=300    # Window size in seconds (5 min default)

# === Admin Panel ===
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=<bcrypt_hash_of_your_password>
JWT_SECRET_KEY=<random_64_char_hex>

# === Server ===
HOST=0.0.0.0
PORT=8000
DEBUG=false
LOG_LEVEL=info
```

> **Generate `ADMIN_PASSWORD_HASH`:**
> ```python
> from passlib.hash import bcrypt
> print(bcrypt.hash("your_password"))
> ```

> **Generate `JWT_SECRET_KEY`:**
> ```python
> import secrets
> print(secrets.token_hex(32))
> ```

---

### Running with Podman (Recommended)

**Step 1 — Start ngrok** (keep this terminal open):
```powershell
ngrok http 8000 --url=<your-static-ngrok-domain>
```

**Step 2 — Build and start all services:**
```powershell
cd "d:\SmallBiz Telegram Bot"
podman compose up --build
```

**Step 3 — Verify the bot is running:**
```
GET https://<your-ngrok-url>/health
→ {"status": "healthy", "service": "SmallBiz Telegram Bot", "version": "0.1.0"}
```

**Step 4 — Open Telegram, find your bot, and say hi to Sitara!**

---

**To stop:**
```powershell
podman compose down
```

**To restart after code changes** (no rebuild needed for `app/` changes — it's volume-mounted):
```powershell
podman compose down; podman compose up
```

**To force a full image rebuild** (needed after `requirements.txt` changes):
```powershell
podman compose down; podman compose up --build
```

---

### Running Locally (No Container)

```powershell
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run (make sure MongoDB is running separately)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Ngrok Setup (Webhook Tunneling)

Telegram requires a **public HTTPS URL** to send webhook events. ngrok creates a secure tunnel from the internet to your local machine.

### First-time Setup

1. Sign up at [ngrok.com](https://ngrok.com) (free)
2. Install ngrok and authenticate:
   ```powershell
   ngrok config add-authtoken <your_authtoken>
   ```
3. Claim your **free static domain** at [dashboard.ngrok.com → Domains](https://dashboard.ngrok.com/domains)
4. Start ngrok pointing to your static domain:
   ```powershell
   ngrok http 8000 --url=your-domain.ngrok-free.app
   ```
5. Set `WEBHOOK_URL=https://your-domain.ngrok-free.app` in your `.env`

### Every Time You Start Your Laptop

You **must restart ngrok** each session. Your **URL stays the same** if you use your static domain with `--url`:

```powershell
# Terminal 1 — keep open
ngrok http 8000 --url=your-domain.ngrok-free.app

# Terminal 2
podman compose up
```

> ℹ️ Without `--url`, ngrok generates a new random URL each time, requiring a `.env` update and container restart.

---

## Bot Commands

### 📦 Orders
| Command | Description |
|---|---|
| `/neworder` | Guided order creation wizard |
| `/orders` | View all active orders (paginated) |
| `/order <number>` | View specific order (e.g. `/order ORD-2024-0001`) |
| `/completeorder` | Mark an order as complete |
| `/cancelorder` | Cancel an order |
| `/invoice <number>` | Generate PDF invoice |

### 📊 Inventory
| Command | Description |
|---|---|
| `/inventory` | View all stock with quantities |
| `/addstock` | Add items to inventory |
| `/removestock` | Manually deduct items |
| `/lowstock` | Items at or below threshold |
| `/setprice` | Set selling price for an item |
| `/setthreshold` | Set low-stock alert threshold |

### 🧾 Bill of Materials
| Command | Description |
|---|---|
| `/bom <product>` | View materials for a product |
| `/setbom <product>` | Define materials for a product |
| `/boms` | List all products with defined BOMs |

### 👥 Customers
| Command | Description |
|---|---|
| `/customers` | View all customers |
| `/customer <name>` | Customer profile + history |
| `/topcustomers` | Top 5 customers by revenue |

### 💰 Payments
| Command | Description |
|---|---|
| `/recordpayment` | Record payment for an order |
| `/unpaid` | Orders with outstanding balance |
| `/revenue` | Revenue summary (today/week/month) |

### 📋 Reports
| Command | Description |
|---|---|
| `/summary` | Today's business summary |
| `/weeklysummary` | This week's summary |

### ⚙️ Settings
| Command | Description |
|---|---|
| `/settings` | View/edit business settings |
| `/settimezone` | Set your timezone |
| `/setreminders` | Configure reminder times |

---

## Natural Language Examples

You don't need commands — just talk to Sitara naturally:

```
"Order for Priya for 2 chocolate cakes by Friday 8pm"
→ Creates Order #ORD-XXXX-0001 for Priya, deadline set, reminders scheduled

"Added 10kg flour"
→ Inventory updated: flour +10kg

"Used 3 eggs"
→ Inventory deducted: eggs -3 pieces

"How many orders do I have today?"
→ Sitara gives you a live summary

"Mark order 0045 as done"
→ Order status updated → materials auto-deducted via BOM

"Hey Sitara, good morning!"
→ "Good morning, [Name]! Ready to tackle the day at [Business]? ..."

"What's your name?"
→ "I'm Sitara, your SmallBiz assistant! ..."
```

---

## Admin Dashboard

Access the web-based admin panel at:

```
http://localhost:8000/admin
```

**Login:** Use the `ADMIN_USERNAME` and your admin password from `.env`

### Dashboard Sections
| Section | What you can do |
|---|---|
| **Dashboard** | Key metrics overview |
| **Businesses** | View/manage all registered tenants |
| **Orders** | Browse, filter, and manage all orders |
| **Inventory** | View and edit stock across tenants |
| **BOMs** | Manage product material definitions |
| **Logs** | System activity logs |
| **System** | Service health and configuration info |

---

## Rate Limiting & Abuse Prevention

The bot has **three independent layers** of protection to prevent API key abuse:

| Layer | Limit | Scope | Purpose |
|---|---|---|---|
| **Global bot middleware** | 30 messages / 60 sec | Per user, all messages | Prevents bot flooding |
| **GROQ user rate limit** | 20 AI calls / 5 min | Per user, AI messages only | Protects GROQ API key |
| **GROQ concurrency semaphore** | 5 simultaneous calls | All users combined | Prevents API overload |
| **GROQ circuit breaker** | Opens after 3 consecutive failures | Global | Stops cascading failures |

### Tuning the GROQ User Limit

Add these to your `.env` to adjust:

```env
GROQ_USER_CALLS_PER_WINDOW=20    # default: 20 AI calls per user
GROQ_USER_WINDOW_SECONDS=300     # default: 300 seconds (5 minutes)
```

When a user hits the GROQ limit, Sitara sends a friendly message:
> *"⏳ Sitara needs a breather! You've reached the AI request limit (20 calls per 5 minutes)..."*

---

## Automated Scheduler Jobs

APScheduler runs these jobs automatically in the background:

| Job | Schedule | What it does |
|---|---|---|
| **Deadline Reminders** | Per-order | Sends Telegram alerts 24h and 2h before order deadlines |
| **Low Stock Alerts** | Daily | Checks all inventory; notifies owners of items below threshold |
| **Daily Summary** | 8:00 PM (configurable) | Sends an automated business summary to each owner |

The scheduler uses **MongoDB as its jobstore**, so jobs survive container restarts.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service health check |
| `POST` | `/webhook/<secret>` | Telegram webhook receiver |
| `GET` | `/admin` | Admin dashboard login |
| `GET/POST` | `/admin/*` | Admin panel routes |
| `GET` | `/docs` | FastAPI auto-generated API docs |

---

## Configuration Reference

Full list of supported `.env` variables:

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | **Required.** From @BotFather |
| `WEBHOOK_SECRET` | — | **Required.** Random string for webhook path security |
| `WEBHOOK_URL` | — | **Required.** Your public HTTPS base URL (ngrok URL) |
| `MONGODB_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `MONGODB_DB_NAME` | `smallbiz_bot` | MongoDB database name |
| `GROQ_API_KEY` | — | **Required.** From console.groq.com |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | GROQ model to use |
| `GROQ_RATE_LIMIT` | `5` | Max concurrent GROQ requests |
| `GROQ_CIRCUIT_BREAKER_THRESHOLD` | `3` | Failures before circuit opens |
| `GROQ_USER_CALLS_PER_WINDOW` | `20` | Max AI calls per user per window |
| `GROQ_USER_WINDOW_SECONDS` | `300` | Rolling window for user AI limit |
| `ASSISTANT_NAME` | `Sitara` | Display name of the AI assistant |
| `ADMIN_USERNAME` | `admin` | Admin panel username |
| `ADMIN_PASSWORD_HASH` | — | **Required.** bcrypt hash of admin password |
| `JWT_SECRET_KEY` | — | **Required.** Secret for JWT signing |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `JWT_EXPIRY_HOURS` | `24` | JWT token expiry |
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL` | `info` | Logging level (`debug`/`info`/`warning`/`error`) |

---

> Built with ❤️ for small business owners who deserve better tools.
