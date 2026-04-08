#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  Competitor Audit — Crawl4AI + Claude Analysis

  Crawls competitor sites and SERPs to extract:
  - Site structure, page count, content depth
  - H2 subtopics, FAQ questions, content angles
  - Schema markup, internal linking patterns
  - Content gaps: what they cover that you don't

  Prerequisites:
    pip install crawl4ai anthropic
    crawl4ai-setup

  Usage:
    # Audit a single competitor URL
    python3 competitor_audit.py --url https://competitor-site.com

    # Audit top SERP results for a keyword
    python3 competitor_audit.py --keyword "best payid casino australia"

    # Audit + compare against your content
    python3 competitor_audit.py --keyword "best payid casino australia" --gaps

    # Deep crawl (follow internal links, max 50 pages)
    python3 competitor_audit.py --url https://competitor-site.com --deep

    # Save report as JSON
    python3 competitor_audit.py --keyword "best payid casino australia" --output report.json
═══════════════════════════════════════════════════════════════
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path


# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

MODEL = "claude-sonnet-4-6"
MAX_SERP_RESULTS = 5
MAX_DEEP_PAGES = 50

# Load market config if available
_config_path = Path(__file__).parent / "config.json"
if _config_path.exists():
    with open(_config_path) as f:
        _config = json.load(f)
    SITE_DOMAIN = _config.get("site", {}).get("domain", "")
    MARKET = _config.get("_market", "au")
else:
    SITE_DOMAIN = ""
    MARKET = "au"

REGISTRY_PATH = Path(__file__).parent / "content-registry.json"


# ─────────────────────────────────────────────
# CRAWL4AI — Single Page Scrape
# ─────────────────────────────────────────────

async def scrape_page(url: str) -> dict:
    """Scrape a single page and extract structured SEO data."""
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    from crawl4ai.markdown_generators import DefaultMarkdownGenerator

    browser_config = BrowserConfig(headless=True)
    crawl_config = CrawlerRunConfig(
        markdown_generator=DefaultMarkdownGenerator(
            options={"ignore_links": False}
        )
    )

    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=crawl_config)

            if not result.success:
                print(f"   ⚠️  Failed to crawl: {url}")
                return {"url": url, "error": "crawl_failed"}

            markdown = result.markdown.raw_markdown if result.markdown else ""
            html = result.html or ""

            # Extract structured data from markdown
            headings_h2 = []
            headings_h3 = []
            faqs = []
            word_count = len(markdown.split())

            for line in markdown.split("\n"):
                line = line.strip()
                if line.startswith("## "):
                    headings_h2.append(line[3:].strip())
                elif line.startswith("### "):
                    headings_h3.append(line[4:].strip())
                # Detect FAQ patterns
                if "?" in line and len(line) > 15 and len(line) < 200:
                    if line.startswith("#") or line.startswith("**") or line.startswith("- "):
                        faqs.append(line.lstrip("#*- ").strip())

            # Extract schema types from HTML
            schema_types = []
            for match in re.findall(r'"@type"\s*:\s*"([^"]+)"', html):
                if match not in schema_types:
                    schema_types.append(match)

            # Extract internal links
            internal_links = len(re.findall(r'href="/', html))
            external_links = len(re.findall(r'href="https?://', html)) - internal_links

            # Extract title and meta description
            title = ""
            title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()

            meta_desc = ""
            desc_match = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html, re.IGNORECASE)
            if desc_match:
                meta_desc = desc_match.group(1).strip()

            return {
                "url": url,
                "title": title,
                "meta_description": meta_desc,
                "word_count": word_count,
                "h2_headings": headings_h2[:20],
                "h3_headings": headings_h3[:20],
                "faq_questions": faqs[:15],
                "schema_types": schema_types,
                "internal_links": internal_links,
                "external_links": external_links,
                "content_preview": markdown[:3000],
            }

    except Exception as e:
        print(f"   ❌  Crawl error for {url}: {e}")
        return {"url": url, "error": str(e)}


# ─────────────────────────────────────────────
# CRAWL4AI — Deep Crawl (follow internal links)
# ─────────────────────────────────────────────

async def deep_crawl(url: str, max_pages: int = MAX_DEEP_PAGES) -> list:
    """Deep crawl a site using BFS strategy. Returns list of page data."""
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
    from crawl4ai.markdown_generators import DefaultMarkdownGenerator

    print(f"\n🕷️  Deep crawling {url} (max {max_pages} pages)...")

    strategy = BFSDeepCrawlStrategy(
        max_depth=2,
        include_external=False,
        max_pages=max_pages,
        score_threshold=0.3,
    )

    browser_config = BrowserConfig(headless=True)
    crawl_config = CrawlerRunConfig(
        markdown_generator=DefaultMarkdownGenerator(
            options={"ignore_links": False}
        ),
        deep_crawl_strategy=strategy,
    )

    pages = []
    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            results = await crawler.arun(url=url, config=crawl_config)

            # Handle both single result and list of results
            if not isinstance(results, list):
                results = [results]

            for result in results:
                if not result.success:
                    continue

                md = result.markdown.raw_markdown if result.markdown else ""
                h2s = [line[3:].strip() for line in md.split("\n") if line.strip().startswith("## ")]

                pages.append({
                    "url": result.url,
                    "title": re.search(r'<title>([^<]+)</title>', result.html or "", re.IGNORECASE),
                    "word_count": len(md.split()),
                    "h2_headings": h2s[:10],
                })

                # Clean up title
                if pages[-1]["title"]:
                    pages[-1]["title"] = pages[-1]["title"].group(1).strip()
                else:
                    pages[-1]["title"] = result.url

            print(f"   ✅  Crawled {len(pages)} pages")

    except Exception as e:
        print(f"   ❌  Deep crawl error: {e}")

    return pages


# ─────────────────────────────────────────────
# SERP SCRAPING — Get top results for a keyword
# ─────────────────────────────────────────────

async def scrape_serp(keyword: str, num_results: int = MAX_SERP_RESULTS) -> list:
    """Scrape Google SERP for a keyword and extract top results.
    
    Uses Crawl4AI to fetch the Google results page, then extracts URLs.
    Falls back to scraping individual known competitor URLs if Google blocks.
    """
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    from crawl4ai.markdown_generators import DefaultMarkdownGenerator

    print(f"\n🔍  Searching: \"{keyword}\"")

    # Google search URL
    search_url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}&num={num_results}"

    browser_config = BrowserConfig(
        headless=True,
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    )
    crawl_config = CrawlerRunConfig(
        markdown_generator=DefaultMarkdownGenerator()
    )

    urls = []
    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=search_url, config=crawl_config)

            if result.success and result.html:
                # Extract organic result URLs from Google HTML
                # Pattern: <a href="/url?q=https://..." or direct <a href="https://...">
                for match in re.findall(r'href="/url\?q=(https?://[^&"]+)', result.html):
                    clean_url = match.split("&")[0]
                    # Skip Google's own pages, ads, etc
                    if "google.com" in clean_url or "youtube.com" in clean_url:
                        continue
                    if clean_url not in urls:
                        urls.append(clean_url)
                    if len(urls) >= num_results:
                        break

                # Fallback: try direct href pattern
                if not urls:
                    for match in re.findall(r'<a[^>]+href="(https?://[^"]+)"', result.html):
                        if "google" not in match and "youtube" not in match and "gstatic" not in match:
                            if match not in urls:
                                urls.append(match)
                            if len(urls) >= num_results:
                                break

    except Exception as e:
        print(f"   ⚠️  Google scrape failed: {e}")

    if not urls:
        print("   ⚠️  No SERP results extracted. Google may have blocked the request.")
        print("   💡  Try: python3 competitor_audit.py --url <competitor-url> instead")
        return []

    print(f"   Found {len(urls)} results")

    # Scrape each result page
    competitors = []
    for i, url in enumerate(urls):
        print(f"   Scraping #{i+1}: {url[:80]}...")
        data = await scrape_page(url)
        if "error" not in data:
            data["serp_position"] = i + 1
            competitors.append(data)
        await asyncio.sleep(1)  # Be polite

    return competitors


# ─────────────────────────────────────────────
# GAP ANALYSIS — Compare competitor vs your content
# ─────────────────────────────────────────────

def load_existing_content() -> dict:
    """Load your existing content from content-registry.json."""
    if not REGISTRY_PATH.exists():
        return {"pages": [], "keywords": set(), "topics": set()}

    reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    keywords = set()
    topics = set()
    for page in reg.get("pages", []):
        topics.add(page.get("title", "").lower())
        for kw in page.get("keywords", []):
            keywords.add(kw.lower())

    return {
        "pages": reg.get("pages", []),
        "keywords": keywords,
        "topics": topics,
    }


def find_content_gaps(competitors: list, existing: dict) -> dict:
    """Compare competitor content against yours to find gaps."""

    # Collect all competitor H2 topics, FAQ questions
    all_h2s = []
    all_faqs = []
    all_schemas = set()
    competitor_word_counts = []

    for comp in competitors:
        if "error" in comp:
            continue
        all_h2s.extend(comp.get("h2_headings", []))
        all_faqs.extend(comp.get("faq_questions", []))
        all_schemas.update(comp.get("schema_types", []))
        competitor_word_counts.append(comp.get("word_count", 0))

    # Deduplicate
    unique_h2s = list(dict.fromkeys(all_h2s))
    unique_faqs = list(dict.fromkeys(all_faqs))

    # Find H2 topics you don't cover
    uncovered_h2s = []
    for h2 in unique_h2s:
        h2_lower = h2.lower()
        covered = any(kw in h2_lower for kw in existing["keywords"]) or \
                  any(h2_lower in topic for topic in existing["topics"])
        if not covered:
            uncovered_h2s.append(h2)

    # Find FAQ questions you don't answer
    uncovered_faqs = []
    for faq in unique_faqs:
        faq_lower = faq.lower()
        covered = any(kw in faq_lower for kw in existing["keywords"])
        if not covered:
            uncovered_faqs.append(faq)

    # Schema gaps
    your_schemas = set()
    for page in existing["pages"]:
        # We don't track schema per page in registry, so just note common ones
        your_schemas.update(["Article", "FAQPage", "BreadcrumbList"])

    schema_gaps = all_schemas - your_schemas

    return {
        "competitor_count": len(competitors),
        "avg_word_count": sum(competitor_word_counts) // max(len(competitor_word_counts), 1),
        "your_page_count": len(existing["pages"]),
        "uncovered_h2_topics": uncovered_h2s[:20],
        "uncovered_faq_questions": uncovered_faqs[:15],
        "schema_gaps": list(schema_gaps),
        "competitors": [
            {
                "url": c.get("url", ""),
                "title": c.get("title", ""),
                "word_count": c.get("word_count", 0),
                "h2_count": len(c.get("h2_headings", [])),
                "schema_types": c.get("schema_types", []),
            }
            for c in competitors if "error" not in c
        ]
    }


def generate_gap_report_with_claude(gaps: dict, keyword: str) -> list:
    """Use Claude to turn raw gaps into actionable article topics."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("   ⚠️  ANTHROPIC_API_KEY not set — skipping Claude analysis")
        return []

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""You are an SEO content strategist for a casino affiliate site targeting {MARKET.upper()} market.

KEYWORD: "{keyword}"

COMPETITOR ANALYSIS (from Crawl4AI):
- {gaps['competitor_count']} competitors analyzed
- Average word count: {gaps['avg_word_count']}
- Our site has {gaps['your_page_count']} pages

H2 TOPICS COMPETITORS COVER THAT WE DON'T:
{json.dumps(gaps['uncovered_h2_topics'][:15], indent=2)}

FAQ QUESTIONS COMPETITORS ANSWER THAT WE DON'T:
{json.dumps(gaps['uncovered_faq_questions'][:10], indent=2)}

SCHEMA TYPES WE'RE MISSING:
{json.dumps(gaps['schema_gaps'], indent=2)}

TASK: Generate 5-8 specific article topics we should create to fill these gaps.
Each topic should:
1. Directly address an uncovered H2 topic or FAQ question from above
2. Be specific to {MARKET.upper()} market
3. Include target keywords
4. Explain why this gap matters for rankings

Return ONLY a JSON array:
[
  {{
    "topic": "Full article title",
    "slug": "url-friendly-slug",
    "keywords": ["primary", "secondary", "tertiary"],
    "gap_reason": "Which competitor topic/question this fills",
    "priority": "high/medium/low"
  }}
]"""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(text)
    except Exception as e:
        print(f"   ⚠️  Claude gap analysis failed: {e}")
        return []


# ─────────────────────────────────────────────
# PRINT REPORT
# ─────────────────────────────────────────────

def print_report(competitors: list, gaps: dict = None, suggested_topics: list = None):
    """Print a formatted audit report."""

    print(f"\n{'='*60}")
    print(f"  COMPETITOR AUDIT REPORT")
    print(f"{'='*60}")

    for comp in competitors:
        if "error" in comp:
            continue
        pos = comp.get("serp_position", "?")
        print(f"\n  #{pos} — {comp.get('title', 'Unknown')[:60]}")
        print(f"       URL: {comp.get('url', '')[:70]}")
        print(f"       Words: {comp.get('word_count', 0):,}")
        print(f"       H2s: {len(comp.get('h2_headings', []))}")
        print(f"       FAQs: {len(comp.get('faq_questions', []))}")
        print(f"       Schema: {', '.join(comp.get('schema_types', [])) or 'none'}")
        print(f"       Links: {comp.get('internal_links', 0)} internal, {comp.get('external_links', 0)} external")

        if comp.get("h2_headings"):
            print(f"       H2 Topics:")
            for h2 in comp["h2_headings"][:8]:
                print(f"         • {h2}")

    if gaps:
        print(f"\n{'='*60}")
        print(f"  GAP ANALYSIS")
        print(f"{'='*60}")
        print(f"\n  Avg competitor word count: {gaps['avg_word_count']:,}")
        print(f"  Your pages: {gaps['your_page_count']}")

        if gaps["uncovered_h2_topics"]:
            print(f"\n  📋 Uncovered H2 Topics ({len(gaps['uncovered_h2_topics'])}):")
            for h2 in gaps["uncovered_h2_topics"][:10]:
                print(f"     • {h2}")

        if gaps["uncovered_faq_questions"]:
            print(f"\n  ❓ Unanswered FAQ Questions ({len(gaps['uncovered_faq_questions'])}):")
            for faq in gaps["uncovered_faq_questions"][:8]:
                print(f"     • {faq}")

        if gaps["schema_gaps"]:
            print(f"\n  🔧 Schema Gaps: {', '.join(gaps['schema_gaps'])}")

    if suggested_topics:
        print(f"\n{'='*60}")
        print(f"  SUGGESTED ARTICLES TO FILL GAPS")
        print(f"{'='*60}")
        for i, topic in enumerate(suggested_topics, 1):
            print(f"\n  {i}. {topic['topic']}")
            print(f"     Keywords: {', '.join(topic.get('keywords', []))}")
            print(f"     Priority: {topic.get('priority', '?')}")
            print(f"     Gap: {topic.get('gap_reason', '')}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Competitor Audit — Crawl4AI + Claude Analysis")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", type=str, help="Audit a single competitor URL")
    group.add_argument("--keyword", type=str, help="Audit top SERP results for a keyword")

    parser.add_argument("--deep", action="store_true",
                       help="Deep crawl the site (follow internal links, up to 50 pages)")
    parser.add_argument("--gaps", action="store_true",
                       help="Compare against your content and suggest articles to fill gaps")
    parser.add_argument("--output", type=str, default=None,
                       help="Save report as JSON to this file")
    parser.add_argument("--num-results", type=int, default=MAX_SERP_RESULTS,
                       help=f"Number of SERP results to analyze (default: {MAX_SERP_RESULTS})")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  🕷️  Competitor Audit — Crawl4AI")
    print(f"  Market: {MARKET.upper()} | Domain: {SITE_DOMAIN or 'not configured'}")
    print(f"{'='*60}")

    # ── Run audit ──
    if args.url:
        if args.deep:
            pages = asyncio.run(deep_crawl(args.url, max_pages=MAX_DEEP_PAGES))
            competitors = pages  # Deep crawl returns list of page data
            # Also get detailed data for the main page
            main_page = asyncio.run(scrape_page(args.url))
            if "error" not in main_page:
                competitors = [main_page] + [p for p in pages if p.get("url") != args.url]
        else:
            page_data = asyncio.run(scrape_page(args.url))
            competitors = [page_data] if "error" not in page_data else []
    else:
        competitors = asyncio.run(scrape_serp(args.keyword, num_results=args.num_results))

    if not competitors:
        print("\n❌  No competitor data collected. Check URLs/keyword and try again.")
        sys.exit(1)

    # ── Gap analysis ──
    gaps = None
    suggested = None
    if args.gaps:
        existing = load_existing_content()
        gaps = find_content_gaps(competitors, existing)
        keyword = args.keyword or args.url
        suggested = generate_gap_report_with_claude(gaps, keyword)

    # ── Print report ──
    print_report(competitors, gaps, suggested)

    # ── Save to file ──
    if args.output:
        report = {
            "keyword": args.keyword or args.url,
            "market": MARKET,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "competitors": competitors,
            "gaps": gaps,
            "suggested_topics": suggested,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n💾  Report saved to {args.output}")

    print(f"\n{'='*60}")
    print(f"  ✅  Audit complete — {len(competitors)} pages analyzed")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
