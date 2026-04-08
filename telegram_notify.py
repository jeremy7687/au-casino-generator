#!/usr/bin/env python3
"""
Telegram notification module for AussiePokies96 site updates.

Usage as module:
    from telegram_notify import notify
    notify("✅ Article published: PayID vs Crypto")

Usage as CLI:
    python3 telegram_notify.py "Test message"

Required env vars (or set BOT_TOKEN/CHAT_ID directly below):
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID
"""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime

# ── Config ──
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8710651704:AAGEo3YouO5wzhK0p5O57PO0IBAOGp7iRJg")
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "6079860371")
SITE      = "ssusa.co"


def notify(message: str, silent: bool = False) -> bool:
    """Send a Telegram message. Returns True on success."""
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️  Telegram not configured — skipping notification")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_notification": silent,
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"⚠️  Telegram notification failed: {e}")
        return False


# ── Pre-built notification templates ──

def notify_article_published(topic: str, url: str, word_count: int = 0):
    msg = (
        f"✅ <b>New Article Published</b>\n"
        f"📝 {topic}\n"
        f"🔗 https://{SITE}{url}\n"
        f"📊 {word_count:,} chars\n"
        f"🕐 {datetime.now().strftime('%d %b %Y %H:%M')} UTC"
    )
    notify(msg)


def notify_deploy(commit_msg: str, pages_count: int = 0):
    msg = (
        f"🚀 <b>Site Deployed</b>\n"
        f"📦 {commit_msg[:80]}\n"
        f"📄 {pages_count} pages live\n"
        f"🌐 https://{SITE}\n"
        f"🕐 {datetime.now().strftime('%d %b %Y %H:%M')} UTC"
    )
    notify(msg)


def notify_freshness(pages_updated: int, dates_updated: int):
    msg = (
        f"🔄 <b>Dates Refreshed</b>\n"
        f"📄 {pages_updated} pages updated\n"
        f"📅 {dates_updated} dates refreshed\n"
        f"🕐 {datetime.now().strftime('%d %b %Y %H:%M')} UTC"
    )
    notify(msg)


def notify_gap_analysis(gaps_found: int, added_to_queue: int, queue_total: int):
    msg = (
        f"🔍 <b>Gap Analysis Complete</b>\n"
        f"🕳️ {gaps_found} gaps found\n"
        f"➕ {added_to_queue} added to queue\n"
        f"📋 Queue total: {queue_total} articles\n"
        f"🕐 {datetime.now().strftime('%d %b %Y %H:%M')} UTC"
    )
    notify(msg)


def notify_error(workflow: str, error: str):
    msg = (
        f"❌ <b>Workflow Failed: {workflow}</b>\n"
        f"⚠️ {error[:200]}\n"
        f"🔗 https://github.com/jeremy7687/au-casino-generator/actions\n"
        f"🕐 {datetime.now().strftime('%d %b %Y %H:%M')} UTC"
    )
    notify(msg, silent=False)


def notify_weekly_summary(pages_total: int, queue_remaining: int, articles_this_week: int):
    msg = (
        f"📊 <b>Weekly Summary — AussiePokies96</b>\n"
        f"🌐 https://{SITE}\n"
        f"📄 Total pages: {pages_total}\n"
        f"📝 Published this week: {articles_this_week}\n"
        f"📋 Queue remaining: {queue_remaining}\n"
        f"🕐 {datetime.now().strftime('%d %b %Y')}"
    )
    notify(msg)


# ── CLI ──
if __name__ == "__main__":
    msg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "🔔 Test notification from AussiePokies96"
    success = notify(msg)
    print("✅ Sent" if success else "❌ Failed")
