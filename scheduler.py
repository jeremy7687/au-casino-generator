#!/usr/bin/env python3
"""
Content Scheduler — picks due articles from content-queue.json and publishes them.
Called by .github/workflows/scheduler.yml on weekdays.

Usage:
  python3 scheduler.py               # auto mode (publishes all due today)
  python3 scheduler.py --dry-run     # preview without generating
  python3 scheduler.py --force-slug blog/payid-vs-crypto-casino-deposits
"""

import json
import subprocess
import sys
import os
from datetime import date
from pathlib import Path

QUEUE_FILE = Path(__file__).parent / "content-queue.json"
DRY_RUN = "--dry-run" in sys.argv
FORCE_SLUG = None
for i, arg in enumerate(sys.argv):
    if arg == "--force-slug" and i + 1 < len(sys.argv):
        FORCE_SLUG = sys.argv[i + 1]

today = date.today()
today_str = today.isoformat()

print(f"\n{'[DRY RUN] ' if DRY_RUN else ''}Content Scheduler — {today_str}")


def load_queue():
    if not QUEUE_FILE.exists():
        print("❌ content-queue.json not found")
        sys.exit(1)
    return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))


def save_queue(data):
    QUEUE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def get_max_per_day(data):
    try:
        config = json.loads(Path("config.json").read_text())
        return config.get("publishing_pace", {}).get("max_per_day", 1)
    except Exception:
        return data.get("settings", {}).get("max_per_day", 1)


def publish_article(item):
    topic = item["topic"]
    slug = item.get("slug", "")
    keywords = item.get("keywords", [])

    print(f"\n📝 Publishing: {topic}")
    print(f"   Slug: {slug}")
    print(f"   Keywords: {', '.join(keywords[:3])}")

    if DRY_RUN:
        print("   [DRY RUN] Would call: python3 add_content.py")
        return True

    cmd = ["python3", "add_content.py", "--topic", topic]
    if slug:
        cmd += ["--slug", slug]
    if keywords:
        cmd += ["--keywords", ",".join(keywords)]

    env = os.environ.copy()
    result = subprocess.run(cmd, env=env, capture_output=False)

    if result.returncode == 0:
        print(f"   ✅ Published: {topic}")
        return True
    else:
        print(f"   ❌ Failed to publish: {topic} (exit {result.returncode})")
        return False


# ── Main ──

data = load_queue()
queue = data.get("queue", [])
max_per_day = get_max_per_day(data)

if FORCE_SLUG:
    due = [x for x in queue if x.get("slug") == FORCE_SLUG and x["status"] == "pending"]
    if not due:
        print(f"❌ No pending item with slug: {FORCE_SLUG}")
        sys.exit(1)
else:
    due = [x for x in queue if x["status"] == "pending" and x.get("publish_date", "9999") <= today_str]

if not due:
    print("✅ No articles due today — nothing to publish")
    sys.exit(0)

print(f"\n📋 {len(due)} article(s) due | max per day: {max_per_day}")
to_publish = due[:max_per_day]
published = 0

for item in to_publish:
    success = publish_article(item)
    if success and not DRY_RUN:
        item["status"] = "published"
        item["published_date"] = today_str
        published += 1

if not DRY_RUN and published:
    save_queue(data)
    print(f"\n✅ Published {published} article(s). Queue updated.")
elif DRY_RUN:
    print(f"\n[DRY RUN] Would publish {len(to_publish)} article(s).")

remaining = len([x for x in queue if x["status"] == "pending"])
print(f"📊 Queue: {remaining} pending articles remaining\n")
