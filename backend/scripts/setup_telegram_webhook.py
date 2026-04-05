"""
One-time script to register the Telegram webhook URL with Telegram's servers.

Usage:
  cd backend
  source venv/bin/activate
  WEBHOOK_URL=https://your-ngrok-or-prod-url.com python scripts/setup_telegram_webhook.py

For local dev, get a public URL first:
  ngrok http 8000
  # copy the https URL, e.g. https://abc123.ngrok-free.app

The webhook URL will be: <WEBHOOK_URL>/api/telegram/webhook
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import httpx
from config import settings

def main():
    webhook_base = os.environ.get("WEBHOOK_URL", "").rstrip("/")
    if not webhook_base:
        print("ERROR: Set the WEBHOOK_URL environment variable.")
        print("  export WEBHOOK_URL=https://abc123.ngrok-free.app")
        sys.exit(1)

    if not settings.telegram_bot_token:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set in .env")
        sys.exit(1)

    webhook_url = f"{webhook_base}/api/telegram/webhook"
    print(f"Registering webhook: {webhook_url}")

    payload = {
        "url": webhook_url,
        "allowed_updates": ["message"],
        "drop_pending_updates": True,
    }
    if settings.telegram_webhook_secret:
        payload["secret_token"] = settings.telegram_webhook_secret

    r = httpx.post(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook",
        json=payload,
        timeout=10.0,
    )
    result = r.json()
    if result.get("ok"):
        print(f"✅ Webhook registered successfully.")
        print(f"   URL: {webhook_url}")
    else:
        print(f"❌ Failed: {result}")
        sys.exit(1)

    # Verify
    info = httpx.get(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/getWebhookInfo",
        timeout=10.0,
    ).json()
    print(f"\nWebhook info: {info.get('result', info)}")


if __name__ == "__main__":
    main()
