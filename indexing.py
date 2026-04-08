#!/usr/bin/env python3
"""
Google Indexing API — submits URLs for fast crawling.

The service account (google-indexing-key.json) must be added as an
Owner in Google Search Console for the target property.

Usage as module:
    from indexing import submit_url, submit_all_pages
    submit_url("https://ssusa.co/blog/payid-vs-crypto/")
    submit_all_pages()          # submits all pages in generated/

Usage as CLI:
    python3 indexing.py                          # submit all pages
    python3 indexing.py /blog/payid-vs-crypto/   # submit one URL
    python3 indexing.py --sitemap                # submit sitemap ping
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False

try:
    from telegram_notify import notify
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False

DOMAIN       = "https://ssusa.co"
KEY_FILE     = Path(__file__).parent / "google-indexing-key.json"
GENERATED    = Path(__file__).parent / "generated"
SCOPES       = ["https://www.googleapis.com/auth/indexing"]
BATCH_SIZE   = 100   # Google allows 100 URLs per batch request
RATE_DELAY   = 0.5   # seconds between requests


def _get_service():
    """Build authenticated Google Indexing API service."""
    if not HAS_GOOGLE:
        print("❌ google-auth not installed. Run: pip install google-auth google-api-python-client")
        return None
    if not KEY_FILE.exists():
        print(f"❌ Key file not found: {KEY_FILE}")
        return None
    creds = service_account.Credentials.from_service_account_file(
        str(KEY_FILE), scopes=SCOPES
    )
    return build("indexing", "v3", credentials=creds, cache_discovery=False)


def submit_url(url: str, url_type: str = "URL_UPDATED") -> bool:
    """
    Submit a single URL to Google Indexing API.
    url_type: "URL_UPDATED" (new or updated) or "URL_DELETED"
    Returns True on success.
    """
    service = _get_service()
    if not service:
        return False

    # Ensure absolute URL
    if url.startswith("/"):
        url = DOMAIN + url

    try:
        body = {"url": url, "type": url_type}
        service.urlNotifications().publish(body=body).execute()
        print(f"   ✅ Indexed: {url}")
        return True
    except Exception as e:
        err = str(e)
        if "403" in err:
            print(f"   ❌ 403 Forbidden — add service account as Owner in GSC: {url}")
        elif "429" in err:
            print(f"   ⏳ Rate limited — waiting 60s then retrying: {url}")
            time.sleep(60)
            return submit_url(url, url_type)
        else:
            print(f"   ⚠️  Failed: {url} — {err[:100]}")
        return False


def submit_urls(urls: list, label: str = "") -> dict:
    """
    Submit a list of URLs. Returns {"ok": n, "fail": n}.
    """
    service = _get_service()
    if not service:
        return {"ok": 0, "fail": len(urls)}

    ok = fail = 0
    total = len(urls)
    print(f"\n📡  Submitting {total} URL(s) to Google Indexing API{f' ({label})' if label else ''}...")

    for i, url in enumerate(urls, 1):
        if url.startswith("/"):
            url = DOMAIN + url
        try:
            service.urlNotifications().publish(
                body={"url": url, "type": "URL_UPDATED"}
            ).execute()
            print(f"   [{i}/{total}] ✅ {url}")
            ok += 1
        except Exception as e:
            print(f"   [{i}/{total}] ❌ {url} — {str(e)[:80]}")
            fail += 1

        if i % 10 == 0:
            time.sleep(RATE_DELAY)

    print(f"\n   📊 Submitted: {ok} OK | {fail} failed")
    return {"ok": ok, "fail": fail}


def submit_all_pages() -> dict:
    """
    Submit every HTML page in generated/ to Google Indexing API.
    """
    if not GENERATED.exists():
        print("❌ generated/ directory not found")
        return {"ok": 0, "fail": 0}

    urls = []
    for html_file in sorted(GENERATED.rglob("*.html")):
        rel = html_file.relative_to(GENERATED)
        path_str = str(rel)

        # Convert path to URL
        if path_str == "index.html":
            url = DOMAIN + "/"
        else:
            url = DOMAIN + "/" + path_str.replace(".html", "/").replace("\\", "/")

        urls.append(url)

    result = submit_urls(urls, label="full site")

    if HAS_TELEGRAM and result["ok"] > 0:
        notify(
            f"📡 <b>Google Indexing Submitted</b>\n"
            f"✅ {result['ok']} URLs submitted\n"
            f"❌ {result['fail']} failed\n"
            f"🕐 {datetime.now().strftime('%d %b %Y %H:%M')} UTC"
        )

    return result


def submit_new_article(url: str, title: str = "") -> bool:
    """Submit a single newly published article."""
    success = submit_url(url)
    if success and HAS_TELEGRAM:
        notify(
            f"📡 <b>Submitted to Google</b>\n"
            f"🔗 {DOMAIN}{url}\n"
            f"{'📝 ' + title if title else ''}"
        )
    return success


def ping_sitemap() -> bool:
    """Ping Google with sitemap URL for crawl request."""
    import urllib.request
    sitemap_url = f"{DOMAIN}/sitemap.xml"
    ping_url = f"https://www.google.com/ping?sitemap={sitemap_url}"
    try:
        urllib.request.urlopen(ping_url, timeout=10)
        print(f"   ✅ Sitemap pinged: {sitemap_url}")
        return True
    except Exception as e:
        print(f"   ⚠️  Sitemap ping failed: {e}")
        return False


# ── CLI ──
if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] == "--all":
        # Submit all pages
        submit_all_pages()
        ping_sitemap()

    elif args[0] == "--sitemap":
        ping_sitemap()

    elif args[0] == "--new":
        # Submit pages added in last N hours (default 24)
        hours = int(args[1]) if len(args) > 1 else 24
        cutoff = time.time() - (hours * 3600)
        urls = []
        for f in GENERATED.rglob("*.html"):
            if f.stat().st_mtime > cutoff:
                rel = str(f.relative_to(GENERATED))
                url = "/" + rel.replace(".html", "/") if rel != "index.html" else "/"
                urls.append(DOMAIN + url)
        if urls:
            submit_urls(urls, label=f"new pages last {hours}h")
        else:
            print(f"No pages modified in last {hours} hours.")

    else:
        # Submit specific URL(s)
        for url in args:
            submit_url(url)
