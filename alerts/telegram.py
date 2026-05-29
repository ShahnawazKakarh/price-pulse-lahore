"""
Price Pulse Lahore — Telegram Failure Alerts
Sends a message to your Telegram if the scraper or OCR fails.
QA Pulse by SK · skakarh.com
"""

import logging
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")


def send_alert(message: str) -> bool:
    """Send a Telegram message. Returns True if sent successfully."""
    if not BOT_TOKEN or not CHAT_ID:
        logger.warning("[Alert] Telegram not configured — skipping alert")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id":    CHAT_ID,
        "text":       message,
        "parse_mode": "HTML",
    }

    try:
        r = httpx.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            logger.info("[Alert] Telegram message sent")
            return True
        else:
            logger.error(f"[Alert] Telegram error: {r.status_code} {r.text}")
            return False
    except Exception as e:
        logger.error(f"[Alert] Failed to send Telegram message: {e}")
        return False


def alert_scrape_failure(failed_categories: list[str]) -> None:
    """Alert when scraper fails to fetch one or more categories."""
    cats = ", ".join(failed_categories)
    message = (
        "🚨 <b>Price Pulse Lahore — Scraper Alert</b>\n\n"
        f"Failed to scrape: <code>{cats}</code>\n\n"
        "The government site may be down or its URL structure has changed.\n"
        "Check: https://lahore.punjab.gov.pk/market_rates"
    )
    send_alert(message)


def alert_ocr_failure(failed_categories: list[str]) -> None:
    """Alert when OCR returns empty results for a category."""
    cats = ", ".join(failed_categories)
    message = (
        "⚠️ <b>Price Pulse Lahore — OCR Alert</b>\n\n"
        f"OCR returned no data for: <code>{cats}</code>\n\n"
        "Image may have changed format or Gemini API issue.\n"
        "Manual check needed."
    )
    send_alert(message)


def alert_success(total_records: int, categories: list[str]) -> None:
    """Daily success confirmation — only sent if you want it."""
    cats = ", ".join(categories)
    message = (
        "✅ <b>Price Pulse Lahore — Daily Scrape Complete</b>\n\n"
        f"Records extracted: <b>{total_records}</b>\n"
        f"Categories: {cats}\n"
        f"Data is live."
    )
    send_alert(message)


if __name__ == "__main__":
    # Test your Telegram config
    ok = send_alert("🧪 <b>Price Pulse Lahore</b> — Telegram alert test. If you see this, alerts are working!")
    print("Sent!" if ok else "Failed — check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
