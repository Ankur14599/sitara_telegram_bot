# Telegram Bot Setup Guide

This project should use separate Telegram bots for production and local testing.

## Recommended Setup

Production bot:

```env
TELEGRAM_BOT_TOKEN=production_bot_token
WEBHOOK_SECRET=production_webhook_secret
WEBHOOK_URL=https://smallbiz-telegram-bot.onrender.com
```

Local test bot:

```env
TELEGRAM_BOT_TOKEN=test_bot_token
WEBHOOK_SECRET=local_test_webhook_secret
WEBHOOK_URL=https://your-ngrok-domain.ngrok-free.dev
```

Each Telegram bot token has its own webhook. Registering a webhook for the test bot does not change the production bot webhook.

## Create A Test Bot

1. Open Telegram.
2. Message `@BotFather`.
3. Send:

```text
/newbot
```

4. Choose a display name, for example:

```text
Sitara Test Bot
```

5. Choose a username ending in `bot`, for example:

```text
sitara_test_local_bot
```

6. Copy the token from BotFather into local `.env`:

```env
TELEGRAM_BOT_TOKEN=your_test_bot_token
```

## Local Webhook URL

Telegram must reach your local app through a public HTTPS URL. For local testing, use ngrok:

```powershell
ngrok http 8000 --url=yoga-deem-anyone.ngrok-free.dev
```

Set local `.env`:

```env
WEBHOOK_URL=https://yoga-deem-anyone.ngrok-free.dev
WEBHOOK_SECRET=your_local_test_secret
```

Your full webhook endpoint becomes:

```text
https://yoga-deem-anyone.ngrok-free.dev/webhook/your_local_test_secret
```

## Register The Local Test Bot Webhook

Use the test bot token only:

```powershell
$TOKEN="YOUR_TEST_BOT_TOKEN"; $APP_URL="https://yoga-deem-anyone.ngrok-free.dev"; $SECRET="YOUR_LOCAL_WEBHOOK_SECRET"; Invoke-RestMethod "https://api.telegram.org/bot$TOKEN/setWebhook?url=$APP_URL/webhook/$SECRET"
```

Verify:

```powershell
$TOKEN="YOUR_TEST_BOT_TOKEN"; Invoke-RestMethod "https://api.telegram.org/bot$TOKEN/getWebhookInfo"
```

The `url` returned by `getWebhookInfo` should match:

```text
https://yoga-deem-anyone.ngrok-free.dev/webhook/YOUR_LOCAL_WEBHOOK_SECRET
```

## Register The Production Bot Webhook

Use the production bot token only:

```powershell
$TOKEN="YOUR_PRODUCTION_BOT_TOKEN"; $APP_URL="https://smallbiz-telegram-bot.onrender.com"; $SECRET="YOUR_PRODUCTION_WEBHOOK_SECRET"; Invoke-RestMethod "https://api.telegram.org/bot$TOKEN/setWebhook?url=$APP_URL/webhook/$SECRET"
```

Verify:

```powershell
$TOKEN="YOUR_PRODUCTION_BOT_TOKEN"; Invoke-RestMethod "https://api.telegram.org/bot$TOKEN/getWebhookInfo"
```

## Reset A Webhook

Delete webhook for a bot:

```powershell
$TOKEN="YOUR_BOT_TOKEN"; Invoke-RestMethod "https://api.telegram.org/bot$TOKEN/deleteWebhook"
```

Check webhook status:

```powershell
$TOKEN="YOUR_BOT_TOKEN"; Invoke-RestMethod "https://api.telegram.org/bot$TOKEN/getWebhookInfo"
```

## Local Testing Checklist

1. `.env` uses the test bot token.
2. `.env` uses the local ngrok `WEBHOOK_URL`.
3. `.env` uses local MongoDB:

```env
MONGODB_URI=mongodb://smallbiz-mongodb:27017
MONGODB_DB_NAME=smallbiz_bot
```

4. Podman containers are running:

```powershell
podman start smallbiz-mongodb smallbiz-bot smallbiz-dashboard
```

5. ngrok is running:

```powershell
ngrok http 8000 --url=yoga-deem-anyone.ngrok-free.dev
```

6. Test bot webhook is registered.
7. Send `/start` to the test bot.

## Important Safety Notes

- Do not use the production Telegram token in local `.env`.
- Do not register the production webhook to ngrok unless you intentionally want production users routed to your laptop.
- Use a separate Groq API key for local testing if possible.
- Keep `.env` and any temporary credential files out of Git.
