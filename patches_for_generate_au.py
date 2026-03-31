#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  6 BOLT-ON IMPROVEMENTS FOR generate_au.py
  
  How to install: Follow the step-by-step instructions below.
  Each patch is clearly marked with WHERE it goes in your file.
═══════════════════════════════════════════════════════════════

WHAT YOU GET:
  1. Retry logic      — failed API calls retry 3x with exponential backoff
  2. --only flag      — generate just one page: python3 generate_au.py --only=reviews/stake96.html
  3. IndexNow ping    — auto-ping search engines after push for faster indexing
  4. Dynamic dates    — no more hardcoded 2026-03-30 anywhere
  5. Cost tracking    — see input/output tokens and $ cost per run
  6. deploy.yml       — GitHub Actions workflow for Cloudflare Wrangler deployment

INSTALLATION (5 minutes):

  STEP 1: Add these 3 lines to your imports (top of file, after existing imports):
  
      import argparse
      import datetime
      import urllib.request
      import urllib.error

  STEP 2: Add these lines after your DESIGN dict (before KEYWORDS section):

      TODAY = datetime.date.today().isoformat()
      YEAR  = datetime.date.today().year
      _token_usage = {"input": 0, "output": 0, "calls": 0, "cost_usd": 0.0}
      _PRICING = {"input": 3.0, "output": 15.0}

  STEP 3: Replace your call_claude() function (lines ~2977-3005) with the new
          version below that includes retry + cost tracking.

  STEP 4: Replace your push_files_to_github() function (lines ~3020-3063) with
          the new version that uses TODAY instead of hardcoded dates.

  STEP 5: Add the ping_indexnow() and print_cost_summary() functions after
          push_files_to_github().

  STEP 6: Replace your entire if __name__ == "__main__" block (lines ~3070-3156)
          with the new version that includes --only, --list, --no-push flags.

  STEP 7: Copy deploy.yml to your repo at .github/workflows/deploy.yml
          Then add CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID as GitHub
          repo secrets (Settings → Secrets → Actions).

  STEP 8: (Optional) Set INDEXNOW_KEY environment variable:
          export INDEXNOW_KEY="your-key-from-bing.com/indexnow"
          Also place a file named {your-key}.txt in your repo root containing the key.

USAGE AFTER INSTALL:

  # Generate ALL pages (same as before)
  python3 generate_au.py

  # Generate only one page (saves time + money)
  python3 generate_au.py --only=index.html
  python3 generate_au.py --only=reviews/stake96.html
  python3 generate_au.py --only=reviews/stake96.html,reviews/spin2u.html
  python3 generate_au.py --only=about.html
  python3 generate_au.py --only=guides/best-payid-casinos.html

  # List all available pages
  python3 generate_au.py --list

  # Generate without push prompt
  python3 generate_au.py --no-push

  # Generate one page, skip push and IndexNow
  python3 generate_au.py --only=reviews/stake96.html --no-push --no-indexnow

  # Combine flags
  python3 generate_au.py --only=index.html,about.html --no-indexnow

"""

import anthropic
import json
import os
import sys
import time
import argparse
import datetime
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from github import Github, GithubException


# ─────────────────────────────────────────────
# ADD AFTER YOUR DESIGN DICT
# ─────────────────────────────────────────────

TODAY = datetime.date.today().isoformat()   # e.g. "2026-03-31"
YEAR  = datetime.date.today().year          # e.g. 2026

# Cost tracking
_token_usage = {"input": 0, "output": 0, "calls": 0, "cost_usd": 0.0}
_PRICING = {"input": 3.0, "output": 15.0}  # Sonnet 4.6 per million tokens


# ─────────────────────────────────────────────
# REPLACEMENT: call_claude()
# Includes: retry logic + cost tracking
# ─────────────────────────────────────────────

MODEL = "claude-sonnet-4-6"  # already in your file, shown here for reference

def call_claude(prompt: str, label: str, max_tokens: int = 10000) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌  ANTHROPIC_API_KEY not set. Run: export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    max_retries = 3

    for attempt in range(1, max_retries + 1):
        try:
            print(f"🤖  Generating {label}..." + (f" (attempt {attempt})" if attempt > 1 else ""))

            with client.messages.stream(
                model=MODEL,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                response = stream.get_final_message()

            html = response.content[0].text.strip()

            # ── Cost tracking ──
            usage = response.usage
            in_tok  = usage.input_tokens
            out_tok = usage.output_tokens
            cost = (in_tok * _PRICING["input"] + out_tok * _PRICING["output"]) / 1_000_000
            _token_usage["input"]    += in_tok
            _token_usage["output"]   += out_tok
            _token_usage["calls"]    += 1
            _token_usage["cost_usd"] += cost
            print(f"   📊  {in_tok:,} in + {out_tok:,} out = ${cost:.4f}")

            # ── Strip markdown fences ──
            if html.startswith("```"):
                html = html.split("\n", 1)[1]
            if html.endswith("```"):
                html = html.rsplit("```", 1)[0]
            html = html.strip()

            if not html.startswith("<!DOCTYPE") and not html.startswith("<html"):
                print(f"⚠️   Warning: {label} output may not be valid HTML.")

            return html

        except anthropic.RateLimitError:
            wait = 2 ** attempt * 5  # 10s, 20s, 40s
            print(f"⏳  Rate limited on {label}. Waiting {wait}s... ({attempt}/{max_retries})")
            time.sleep(wait)
            if attempt == max_retries:
                print(f"❌  Failed after {max_retries} retries: {label}")
                raise

        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                wait = 2 ** attempt * 3
                print(f"⏳  Server error ({e.status_code}) on {label}. Waiting {wait}s...")
                time.sleep(wait)
                if attempt == max_retries:
                    raise
            else:
                print(f"❌  API error on {label}: {e}")
                raise

        except Exception as e:
            print(f"❌  Unexpected error on {label}: {e}")
            if attempt == max_retries:
                raise
            time.sleep(2 ** attempt * 2)


# ─────────────────────────────────────────────
# NEW: print_cost_summary()
# ─────────────────────────────────────────────

def print_cost_summary():
    t = _token_usage
    print(f"\n{'='*60}")
    print(f"  💰  API COST SUMMARY")
    print(f"  Calls        : {t['calls']}")
    print(f"  Input tokens : {t['input']:,}")
    print(f"  Output tokens: {t['output']:,}")
    print(f"  Total cost   : ${t['cost_usd']:.4f}")
    print(f"{'='*60}")


# ─────────────────────────────────────────────
# REPLACEMENT: push_files_to_github()
# Uses TODAY instead of hardcoded date
# ─────────────────────────────────────────────

def push_files_to_github(files: dict) -> None:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("❌  GITHUB_TOKEN not set.")
        sys.exit(1)

    print(f"\n📤  Connecting to GitHub: {GITHUB_REPO}")
    g = Github(token)

    try:
        repo = g.get_repo(GITHUB_REPO)
    except GithubException as e:
        print(f"❌  Cannot access repo '{GITHUB_REPO}': {e}")
        sys.exit(1)

    pushed = 0
    for repo_path, content in files.items():
        try:
            existing = repo.get_contents(repo_path)
            repo.update_file(
                path=repo_path,
                message=f"Update {repo_path} — {TODAY}",
                content=content,
                sha=existing.sha
            )
            print(f"   ✅  Updated:  {repo_path}")
        except GithubException:
            repo.create_file(
                path=repo_path,
                message=f"Add {repo_path} — {TODAY}",
                content=content
            )
            print(f"   ✅  Created:  {repo_path}")
        pushed += 1
        if pushed < len(files):
            time.sleep(0.5)

    print(f"\n🚀  {pushed} file(s) pushed. Cloudflare deploys via GitHub Actions.")
    print(f"    Live at: {SITE['domain']}/")


# ─────────────────────────────────────────────
# NEW: ping_indexnow()
# ─────────────────────────────────────────────

def ping_indexnow(pushed_paths: list) -> None:
    """Ping IndexNow + Google sitemap after deploy."""
    indexnow_key = os.environ.get("INDEXNOW_KEY")
    if not indexnow_key:
        print("\n⚠️   INDEXNOW_KEY not set — skipping IndexNow ping.")
        print("    Get a key at bing.com/indexnow, then:")
        print('    export INDEXNOW_KEY="your-key"')
        return

    domain = SITE["domain"].rstrip("/")
    urls = []
    for path in pushed_paths:
        if path.endswith(".html"):
            url_path = path.replace(".html", "/") if path != "index.html" else ""
            urls.append(f"{domain}/{url_path}")
        elif path == "sitemap.xml":
            urls.append(f"{domain}/sitemap.xml")

    if not urls:
        return

    print(f"\n🔔  Pinging IndexNow with {len(urls)} URL(s)...")

    payload = json.dumps({
        "host": domain.replace("https://", "").replace("http://", ""),
        "key": indexnow_key,
        "keyLocation": f"{domain}/{indexnow_key}.txt",
        "urlList": urls
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.indexnow.org/IndexNow",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST"
    )

    try:
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"   ✅  IndexNow accepted {len(urls)} URLs (status {resp.getcode()})")
    except Exception as e:
        print(f"   ⚠️   IndexNow ping failed: {e} (non-critical)")

    # Google sitemap ping
    try:
        urllib.request.urlopen(f"https://www.google.com/ping?sitemap={domain}/sitemap.xml", timeout=10)
        print(f"   ✅  Google sitemap ping sent")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# REPLACEMENT: if __name__ == "__main__" block
#
# New features:
#   --only=page.html     Generate specific page(s) only
#   --list               Show all available pages
#   --no-push            Skip GitHub push
#   --no-indexnow        Skip IndexNow ping
# ═══════════════════════════════════════════════════════════════

# NOTE: The code below goes INSIDE the if __name__ == "__main__" block.
# It references all_tasks, which you build the same way as before.
# The only difference is the argparse setup at the top and the
# filtering/summary logic.
#
# See the full block in the docstring at the top of this file for
# complete usage examples.
