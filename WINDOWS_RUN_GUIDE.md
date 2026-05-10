# Windows Local Setup Guide (Podman Containers)

This guide runs the local MongoDB database, FastAPI Telegram bot, and Streamlit admin dashboard with raw Podman commands on Windows PowerShell.

## Local URLs

- FastAPI backend: `http://localhost:8000`
- Health check: `http://localhost:8000/health`
- Streamlit admin dashboard: `http://localhost:8501`
- MongoDB from Windows host: `mongodb://localhost:27017`
- MongoDB from Podman containers: `mongodb://smallbiz-mongodb:27017`

## Required `.env` Values

For local Podman containers, make sure `.env` contains:

```env
MONGODB_URI=mongodb://smallbiz-mongodb:27017
MONGODB_DB_NAME=smallbiz_bot
HOST=0.0.0.0
PORT=8000
DEBUG=true
LOG_LEVEL=debug
```

The dashboard also needs:

```env
ADMIN_USERNAME=your-admin-username
ADMIN_PASSWORD_HASH=your-bcrypt-password-hash
```

To generate an admin hash:

```powershell
podman run --rm -it `
  -v "D:\SmallBiz Telegram Bot:/app" `
  smallbiz-bot `
  python scripts/generate_admin_hash.py
```

## First-Time Setup

Run from PowerShell:

```powershell
cd "D:\SmallBiz Telegram Bot"
```

Create the shared container network:

```powershell
podman network create smallbiz-network
```

Start MongoDB:

```powershell
podman run -d `
  --name smallbiz-mongodb `
  --network smallbiz-network `
  -p 27017:27017 `
  -v smallbiz-mongodb-data:/data/db `
  mongo:7.0
```

Build the app image:

```powershell
podman build -t smallbiz-bot .
```

Start the FastAPI bot service:

```powershell
podman run -d `
  --name smallbiz-bot `
  --network smallbiz-network `
  -p 8000:8000 `
  --env-file .env `
  -e APP_MODE=bot `
  -v "D:\SmallBiz Telegram Bot:/app" `
  smallbiz-bot
```

Start the Streamlit dashboard:

```powershell
podman run -d `
  --name smallbiz-dashboard `
  --network smallbiz-network `
  -p 8501:8501 `
  --env-file .env `
  -e APP_MODE=streamlit `
  -e PORT=8501 `
  -v "D:\SmallBiz Telegram Bot:/app" `
  smallbiz-bot
```

Check logs:

```powershell
podman logs -f smallbiz-bot
```

```powershell
podman logs -f smallbiz-dashboard
```

## Telegram Webhook For Local Testing

Start ngrok in a second PowerShell window:

```powershell
ngrok http 8000 --url=yoga-deem-anyone.ngrok-free.dev
```

In `.env`, set:

```env
WEBHOOK_URL=https://yoga-deem-anyone.ngrok-free.dev
```

Then register the webhook:

```powershell
$TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
$APP_URL = "https://yoga-deem-anyone.ngrok-free.dev"
$SECRET = "YOUR_WEBHOOK_SECRET"
Invoke-RestMethod "https://api.telegram.org/bot$TOKEN/setWebhook?url=$APP_URL/webhook/$SECRET"
Invoke-RestMethod "https://api.telegram.org/bot$TOKEN/getWebhookInfo"
```

## Daily Startup

After rebooting:

```powershell
podman start smallbiz-mongodb
podman start smallbiz-bot
podman start smallbiz-dashboard
```

Then start ngrok again if you want Telegram webhook traffic:

```powershell
ngrok http 8000 --url=yoga-deem-anyone.ngrok-free.dev
```

## Apply Code Changes

For normal Python changes, restart the affected container:

```powershell
podman restart smallbiz-bot
podman restart smallbiz-dashboard
```

For dependency, Dockerfile, or startup changes, rebuild and recreate:

```powershell
podman rm -f smallbiz-bot smallbiz-dashboard
podman build -t smallbiz-bot .
```

Then run the bot and dashboard commands again.

## Test Everything

Health check:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Dashboard:

```text
http://localhost:8501
```

Telegram trend examples:

```text
/trends
/trends week
/trends month
what is trending this month?
which items are ordered most?
who are my top customers?
```

## Stop Everything

```powershell
podman stop smallbiz-bot smallbiz-dashboard smallbiz-mongodb
```

## Reset Local Containers

This removes containers but keeps MongoDB data:

```powershell
podman rm -f smallbiz-bot smallbiz-dashboard smallbiz-mongodb
```

This also deletes local MongoDB data:

```powershell
podman volume rm smallbiz-mongodb-data
```
