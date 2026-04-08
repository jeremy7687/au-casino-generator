#!/usr/bin/env python3
"""
SERP Competitor Analyzer + Casino Page Generator
Uses Crawl4AI to analyze top-ranking pages, then Claude API
to generate a page designed to outrank them.

Prerequisites:
    pip3 install crawl4ai anthropic
    crawl4ai-setup

Environment variables:
    ANTHROPIC_API_KEY   — from console.anthropic.com
"""

import asyncio
import os
import re
import sys
import json
import time
from pathlib import Path
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.markdown_generators import DefaultMarkdownGenerator
import anthropic


# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

# How many competitor pages to analyze
NUM_COMPETITORS = 5

# Claude model for page generation
MODEL = "claude-sonnet-4-6"

# Output filename
OUTPUT_FILE = "au_index.html"

# Load config if available
_config_path = Path(__file__).parent / "config.json"
if _config_path.exists():
    with open(_config_path) as _f:
        _cfg = json.load(_f)
    TARGET_KEYWORD = f"best online casinos {_cfg.get('country', 'Australia')} 2026"
    CASINO_DATA = {
        "market": _cfg.get("country", "Australia"),
        "market_code": _cfg.get("_market", "au"),
        "year": 2026,
        "site_name": _cfg.get("site", {}).get("brand", "AussiePokies96"),
        "casinos": []
    }
else:
    TARGET_KEYWORD = "best online casinos australia 2026"
    CASINO_DATA = {
        "market": "Australia",
        "market_code": "au",
        "year": 2026,
        "site_name": "AussiePokies96",
        "casinos": []
    }


# ─────────────────────────────────────────────
# STEP 1: Search & Scrape Competitors with Crawl4AI
# ─────────────────────────────────────────────

def analyze_competitors():
    print(f"\n🔍 Searching: \"{TARGET_KEYWORD}\"")
    print(f"   Analyzing top {NUM_COMPETITORS} results...\n")

    # Scrape competitor URLs — use Crawl4AI to fetch each one
    competitors = asyncio.run(_scrape_competitors())

    if not competitors:
        print("⚠️  No competitor data collected.")
        sys.exit(1)

    print(f"\n✅ Analyzed {len(competitors)} competitor pages")

    # Build analysis summary
    analysis = {
        "keyword": TARGET_KEYWORD,
        "num_competitors": len(competitors),
        "avg_content_length": sum(c["content_length_chars"] for c in competitors) // max(len(competitors), 1),
        "competitors": competitors
    }

    with open("competitor_analysis.json", "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2)
    print(f"💾 Saved analysis to competitor_analysis.json")

    return analysis


async def _scrape_competitors():
    """Scrape Google SERP and extract competitor page data."""

    # Step 1: Get competitor URLs from Google
    search_url = f"https://www.google.com/search?q={TARGET_KEYWORD.replace(' ', '+')}&num={NUM_COMPETITORS}"

    browser_config = BrowserConfig(
        headless=True,
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    )
    crawl_config = CrawlerRunConfig(
        markdown_generator=DefaultMarkdownGenerator()
    )

    urls = []
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=search_url, config=crawl_config)
        if result.success and result.html:
            for match in re.findall(r'href="/url\?q=(https?://[^&"]+)', result.html):
                clean = match.split("&")[0]
                if "google.com" not in clean and "youtube.com" not in clean:
                    if clean not in urls:
                        urls.append(clean)
                    if len(urls) >= NUM_COMPETITORS:
                        break

    if not urls:
        print("   ⚠️  Could not extract SERP URLs. Google may have blocked.")
        return []

    # Step 2: Scrape each competitor page
    competitors = []
    crawl_config = CrawlerRunConfig(
        markdown_generator=DefaultMarkdownGenerator(options={"ignore_links": False})
    )

    for i, url in enumerate(urls):
        print(f"   #{i+1}: Scraping {url[:70]}...")
        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=crawl_config)
                if not result.success:
                    continue

                markdown = result.markdown.raw_markdown if result.markdown else ""
                html = result.html or ""

                # Extract title
                title = ""
                title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
                if title_match:
                    title = title_match.group(1).strip()

                # Extract meta description
                desc = ""
                desc_match = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html, re.IGNORECASE)
                if desc_match:
                    desc = desc_match.group(1).strip()

                # Extract headings
                headings = []
                for line in markdown.split("\n"):
                    line = line.strip()
                    if line.startswith("## "):
                        headings.append(line[3:].strip())
                    elif line.startswith("### "):
                        headings.append(line[4:].strip())

                print(f"       ✅ {title[:50]}... ({len(markdown)} chars)")

                competitors.append({
                    "position": i + 1,
                    "url": url,
                    "title": title,
                    "description": desc,
                    "content_length_chars": len(markdown),
                    "h2_h3_headings": headings[:15],
                    "content_preview": markdown[:2000]
                })

        except Exception as e:
            print(f"       ⚠️  Failed: {e}")

        await asyncio.sleep(1)

    return competitors


# ─────────────────────────────────────────────
# STEP 2: Generate Page with Claude API
# ─────────────────────────────────────────────

def generate_page(analysis):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    # Build the competitor summary for Claude
    comp_summary = []
    for c in analysis["competitors"]:
        comp_summary.append({
            "position": c["position"],
            "title": c["title"],
            "url": c["url"],
            "content_length": c["content_length_chars"],
            "headings": c["h2_h3_headings"],
            "description": c["description"]
        })

    prompt = f"""You are an expert SEO affiliate page builder. I'm going to give you:
1. Competitor analysis from the top {analysis['num_competitors']} Google results for "{analysis['keyword']}"
2. My casino data to feature on the page

Your job: Generate a COMPLETE, production-ready HTML page that is designed to OUTRANK these competitors.

## COMPETITOR ANALYSIS
{json.dumps(comp_summary, indent=2)}

Average competitor content length: {analysis['avg_content_length']} characters.

## MY CASINO DATA
{json.dumps(CASINO_DATA, indent=2)}

## SEO STRATEGY
Based on the competitor analysis above:
- Match or exceed the average content length ({analysis['avg_content_length']} chars)
- Cover ALL the topics/headings the competitors cover, plus add unique sections they missed
- Write a better, more comprehensive title tag and meta description than any competitor
- Include content sections that demonstrate E-E-A-T (Experience, Expertise, Authority, Trust)
- Add an FAQ section answering questions the competitors don't cover well

## TECHNICAL REQUIREMENTS
- Single self-contained HTML file — ALL CSS in <style>, no external dependencies
- Dark theme (#0d0f1a body) with gold (#d4a017) accents, white text
- Professional, high-conversion design
- Each casino as a card with: rank badge, name, bonus, score bar, tags, "HOT" badge if hot=true, green CTA button
- ALL affiliate links: target="_blank" rel="nofollow noopener sponsored"
- <head> must include:
  - Optimized <title> tag (better than all competitors above)
  - Optimized <meta description> (better than all competitors above)
  - charset utf-8, viewport meta
  - ItemList JSON-LD schema for casinos
  - FAQPage JSON-LD schema for the FAQ section
  - Organization JSON-LD schema
  - Article JSON-LD schema
- Mobile responsive
- Sticky header
- Table of contents linking to each section
- Gambling disclaimer footer: "18+ only. Gambling can be addictive. Please play responsibly."
- System font stack, no external fonts
- IMPORTANT: Total page content should be at LEAST {max(analysis['avg_content_length'], 5000)} characters to be competitive

Return ONLY the raw HTML. No markdown fences. No explanation. Start with <!DOCTYPE html>."""

    print(f"\n🤖 Generating HTML with Claude ({MODEL})...")
    print(f"   Target content length: {max(analysis['avg_content_length'], 5000)}+ characters")
    print(f"   This may take 30-60 seconds...\n")

    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,  # Higher limit for longer content
        messages=[{"role": "user", "content": prompt}]
    )

    html = response.content[0].text.strip()

    # Strip markdown fences if present
    if html.startswith("```"):
        html = html.split("\n", 1)[1]
    if html.endswith("```"):
        html = html.rsplit("```", 1)[0]
    html = html.strip()

    if not html.startswith("<!DOCTYPE") and not html.startswith("<html"):
        print("⚠️  Warning: Output may not be valid HTML.")

    # Save the page
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ Generated: {OUTPUT_FILE}")
    print(f"   File size: {len(html):,} characters")
    print(f"   Competitor avg: {analysis['avg_content_length']:,} characters")

    if len(html) > analysis['avg_content_length']:
        print(f"   ✅ Your page is LONGER than the average competitor")
    else:
        print(f"   ⚠️  Your page is shorter — consider adding more content via Claude Code")

    return html


# ─────────────────────────────────────────────
# STEP 3: Summary Report
# ─────────────────────────────────────────────

def print_summary(analysis, html):
    print("\n" + "=" * 60)
    print("  SERP ANALYSIS + PAGE GENERATION COMPLETE")
    print("=" * 60)
    print(f"  Target keyword : {analysis['keyword']}")
    print(f"  Competitors    : {analysis['num_competitors']} pages analyzed")
    print(f"  Avg comp length: {analysis['avg_content_length']:,} chars")
    print(f"  Your page      : {len(html):,} chars")
    print(f"  Output file    : {OUTPUT_FILE}")
    print(f"  Analysis file  : competitor_analysis.json")
    print("=" * 60)
    print("\n  NEXT STEPS:")
    print(f"  1. Preview:  open {OUTPUT_FILE}")
    print(f"  2. Refine:   Open in VS Code → Claude Code")
    print(f"  3. Deploy:   Push to GitHub → Cloudflare auto-deploys")
    print("=" * 60)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  SERP Competitor Analyzer + Page Generator")
    print(f"  Keyword: \"{TARGET_KEYWORD}\"")
    print("=" * 60)

    # Step 1: Analyze competitors
    analysis = analyze_competitors()

    # Step 2: Generate page
    html = generate_page(analysis)

    # Step 3: Summary
    print_summary(analysis, html)
