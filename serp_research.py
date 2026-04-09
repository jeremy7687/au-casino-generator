#!/usr/bin/env python3
"""
SERP Research Module — crawl4ai-powered competitor intelligence.

Called by add_content.py before article generation to:
  1. Search Google for the target keyword
  2. Scrape top 5 competitor pages
  3. Extract headings, word count, structure, content gaps
  4. Return a structured dict that gets injected into Claude's prompt
  5. Discover new keyword opportunities from competitor content

Usage as module:
  from serp_research import research_keyword
  data = research_keyword("payid casino australia")

Usage as CLI:
  python3 serp_research.py "payid casino australia"
  python3 serp_research.py "payid casino australia" --discover-keywords
"""

import asyncio
import json
import re
import sys
from pathlib import Path
from datetime import date

NUM_COMPETITORS = 5
TODAY = date.today().isoformat()

_CACHE_DIR = Path(__file__).parent / "serp_cache"
_CACHE_TTL_DAYS = 3  # SERPs shift faster than NeuronWriter analysis


def _cache_path(keyword: str) -> Path:
    slug = keyword.lower().strip().replace(" ", "-").replace("/", "-")
    return _CACHE_DIR / f"{slug}.json"


def _cache_load(keyword: str) -> dict | None:
    path = _cache_path(keyword)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except Exception:
        return None
    cached_at = data.get("_cached_at", "")
    if cached_at:
        age = (date.today() - date.fromisoformat(cached_at)).days
        if age > _CACHE_TTL_DAYS:
            return None
    return data


def _cache_save(keyword: str, result: dict) -> None:
    _CACHE_DIR.mkdir(exist_ok=True)
    to_save = {**result, "_cached_at": TODAY}
    _cache_path(keyword).write_text(json.dumps(to_save, indent=2))

# ─────────────────────────────────────────────
# Core scraping
# ─────────────────────────────────────────────

async def _fetch_serp_urls(keyword: str, browser_config) -> list[str]:
    """Scrape Google SERP and return top competitor URLs."""
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, DefaultMarkdownGenerator

    search_url = f"https://www.google.com/search?q={keyword.replace(' ', '+')}&num=10&gl=au&hl=en"
    crawl_config = CrawlerRunConfig(markdown_generator=DefaultMarkdownGenerator())

    urls = []
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=search_url, config=crawl_config)
        if result.success and result.html:
            for match in re.findall(r'href="/url\?q=(https?://[^&"]+)', result.html):
                clean = match.split("&")[0]
                # Skip irrelevant domains
                skip = ["google.com", "youtube.com", "facebook.com", "wikipedia.org",
                        "reddit.com", "twitter.com", "instagram.com", "linkedin.com"]
                if not any(s in clean for s in skip) and clean not in urls:
                    urls.append(clean)
                if len(urls) >= NUM_COMPETITORS:
                    break

    return urls


async def _scrape_page(url: str, browser_config) -> dict | None:
    """Scrape a single competitor page and extract key data."""
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, DefaultMarkdownGenerator

    crawl_config = CrawlerRunConfig(
        markdown_generator=DefaultMarkdownGenerator(options={"ignore_links": False}),
        page_timeout=20000,
    )

    try:
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=crawl_config)
            if not result.success:
                return None

            html = result.html or ""
            markdown = result.markdown.raw_markdown if result.markdown else ""

            # Title
            title = ""
            m = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
            if m:
                title = m.group(1).strip()

            # Meta description
            desc = ""
            m = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html, re.IGNORECASE)
            if m:
                desc = m.group(1).strip()

            # H2/H3 headings from markdown
            h2 = []
            h3 = []
            for line in markdown.split("\n"):
                line = line.strip()
                if line.startswith("## "):
                    h2.append(line[3:].strip())
                elif line.startswith("### "):
                    h3.append(line[4:].strip())

            # Word count (rough)
            words = len(re.findall(r'\b\w+\b', markdown))

            # FAQ questions — look for question patterns in headings
            faq_qs = [h for h in h2 + h3 if h.endswith("?")]

            return {
                "url": url,
                "title": title,
                "description": desc,
                "word_count": words,
                "h2": h2[:20],
                "h3": h3[:20],
                "faq_questions": faq_qs[:10],
                "content_preview": markdown[:1500],
            }

    except Exception as e:
        print(f"      ⚠️  Scrape failed for {url[:60]}: {e}")
        return None


async def _run_research(keyword: str) -> dict:
    """Async entry point — runs full SERP research."""
    try:
        from crawl4ai import BrowserConfig  # noqa
    except ImportError:
        print("   ⚠️  crawl4ai not installed — run: pip install crawl4ai && crawl4ai-setup")
        return _empty_result(keyword)

    browser_config = BrowserConfig(
        headless=True,
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    )

    print(f"   🔍  SERP research: \"{keyword}\"")

    # Step 1: Get competitor URLs
    urls = await _fetch_serp_urls(keyword, browser_config)
    if not urls:
        print("   ⚠️  No SERP URLs found (Google may have blocked). Continuing without competitor data.")
        return _empty_result(keyword)

    print(f"   📋  Found {len(urls)} competitor URLs")

    # Step 2: Scrape each competitor
    competitors = []
    for i, url in enumerate(urls):
        print(f"      #{i+1}: {url[:70]}...")
        data = await _scrape_page(url, browser_config)
        if data:
            data["position"] = i + 1
            competitors.append(data)
            print(f"           ✅ {data['word_count']:,} words | {len(data['h2'])} H2s")
        await asyncio.sleep(1.5)

    if not competitors:
        return _empty_result(keyword)

    return _build_analysis(keyword, competitors)


def _build_analysis(keyword: str, competitors: list) -> dict:
    """Build structured analysis from scraped competitor data."""
    avg_words = sum(c["word_count"] for c in competitors) // max(len(competitors), 1)
    target_words = max(avg_words + 300, 2000)  # beat the average by 300 words minimum

    # Collect all H2s/H3s across competitors
    all_h2 = []
    all_h3 = []
    all_faq_qs = []
    for c in competitors:
        all_h2.extend(c["h2"])
        all_h3.extend(c["h3"])
        all_faq_qs.extend(c.get("faq_questions", []))

    # Deduplicate while preserving order
    seen = set()
    unique_h2 = []
    for h in all_h2:
        norm = h.lower().strip()
        if norm not in seen:
            seen.add(norm)
            unique_h2.append(h)

    seen = set()
    unique_faq_qs = []
    for q in all_faq_qs:
        norm = q.lower().strip()
        if norm not in seen:
            seen.add(norm)
            unique_faq_qs.append(q)

    # Discover new keywords from headings (phrases not in original keyword)
    keyword_words = set(keyword.lower().split())
    discovered_keywords = []
    for h in unique_h2[:30]:
        h_lower = h.lower()
        # Look for keyword-like phrases in headings
        if len(h_lower.split()) >= 3 and len(h_lower) < 80:
            # If the heading contains "australia" or relevant terms, it's a keyword candidate
            if any(term in h_lower for term in ["australia", "australian", "payid", "casino", "pokie", "bonus", "crypto"]):
                words_in_heading = set(h_lower.split())
                # Only add if it introduces new terms
                new_terms = words_in_heading - keyword_words
                if len(new_terms) >= 2:
                    discovered_keywords.append(h_lower)

    return {
        "keyword": keyword,
        "date": TODAY,
        "competitor_count": len(competitors),
        "avg_word_count": avg_words,
        "target_word_count": target_words,
        "competitors": [
            {
                "position": c["position"],
                "url": c["url"],
                "title": c["title"],
                "word_count": c["word_count"],
                "h2": c["h2"][:10],
                "faq_questions": c.get("faq_questions", [])[:5],
            }
            for c in competitors
        ],
        "all_competitor_h2s": unique_h2[:40],
        "faq_questions_to_cover": unique_faq_qs[:15],
        "discovered_keywords": discovered_keywords[:10],
    }


def _empty_result(keyword: str) -> dict:
    return {
        "keyword": keyword,
        "date": TODAY,
        "competitor_count": 0,
        "avg_word_count": 1500,
        "target_word_count": 2000,
        "competitors": [],
        "all_competitor_h2s": [],
        "faq_questions_to_cover": [],
        "discovered_keywords": [],
    }


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def research_keyword(keyword: str, refresh: bool = False) -> dict:
    """
    Main entry point. Returns competitor analysis dict.
    Uses a local cache (serp_cache/) with a 3-day TTL.
    Pass refresh=True to force a fresh crawl.
    Safe to call even if crawl4ai is not installed (returns empty result).
    """
    if not refresh:
        cached = _cache_load(keyword)
        if cached:
            age = (date.today() - date.fromisoformat(cached["_cached_at"])).days
            print(f"   💾  SERP: cached results for \"{keyword}\" ({age}d old)")
            return cached
    try:
        result = asyncio.run(_run_research(keyword))
        if result["competitor_count"] > 0:
            _cache_save(keyword, result)
        return result
    except Exception as e:
        print(f"   ⚠️  SERP research failed: {e}")
        return _empty_result(keyword)


def build_competitor_prompt_block(analysis: dict) -> str:
    """
    Convert analysis dict into a Claude prompt block that instructs Claude
    to write content that beats these specific competitors.
    """
    if analysis["competitor_count"] == 0:
        return ""

    competitors_summary = "\n".join(
        f"  #{c['position']}: {c['title'][:70]} ({c['word_count']:,} words) — {c['url'][:60]}"
        for c in analysis["competitors"]
    )

    h2_list = "\n".join(f"  - {h}" for h in analysis["all_competitor_h2s"][:25])
    faq_list = "\n".join(f"  - {q}" for q in analysis["faq_questions_to_cover"][:12])

    block = f"""
## COMPETITOR INTELLIGENCE (via live SERP research — {analysis['date']})

Top {analysis['competitor_count']} ranking pages for "{analysis['keyword']}":
{competitors_summary}

Average competitor word count: {analysis['avg_word_count']:,} words
**Your target: {analysis['target_word_count']:,}+ words** (beat the average by 300+ words minimum)

### H2 headings competitors are using (cover ALL of these plus add unique sections):
{h2_list}

### FAQ questions competitors are answering (answer ALL of these plus more):
{faq_list if faq_list else "  - (none detected)"}

### Your competitive edge — include sections competitors MISSED:
- More specific data (exact numbers, percentages, timeframes)
- Step-by-step processes (numbered lists with real detail)
- Comparison tables with real operator data
- Australia-specific angles (AUD, PayID, Australian licensing, RG helpline)
- Stronger FAQ with longer, more complete answers
- Updated {date.today().year} information competitors haven't refreshed
"""
    return block


def add_discovered_keywords_to_queue(analysis: dict, queue_file: str = "content-queue.json") -> int:
    """
    Appends newly discovered keywords to content-queue.json as pending articles.
    Returns number of keywords added.
    """
    if not analysis.get("discovered_keywords"):
        return 0

    queue_path = Path(queue_file)
    if not queue_path.exists():
        return 0

    try:
        data = json.loads(queue_path.read_text(encoding="utf-8"))
    except Exception:
        return 0

    existing_topics = {item["topic"].lower() for item in data.get("queue", [])}
    existing_slugs = {item.get("slug", "") for item in data.get("queue", [])}

    added = 0
    # Schedule new keywords starting 2 weeks out, Mon/Wed/Fri pace
    from datetime import date, timedelta
    last_date = max(
        (date.fromisoformat(item.get("publish_date", TODAY))
         for item in data.get("queue", []) if item.get("publish_date")),
        default=date.today()
    )

    for kw in analysis["discovered_keywords"]:
        # Skip if similar topic already in queue
        if kw.lower() in existing_topics:
            continue

        # Generate slug
        slug_base = re.sub(r'[^a-z0-9\s-]', '', kw.lower())
        slug_base = re.sub(r'[\s_]+', '-', slug_base).strip('-')[:60]
        slug = f"blog/{slug_base}"

        if slug in existing_slugs:
            continue

        # Next Mon/Wed/Fri after last scheduled date
        last_date += timedelta(days=2)
        while last_date.weekday() not in [0, 2, 4]:  # Mon=0, Wed=2, Fri=4
            last_date += timedelta(days=1)

        new_item = {
            "topic": kw.title(),
            "slug": slug,
            "keywords": [kw, f"{kw} 2026"],
            "publish_date": last_date.isoformat(),
            "status": "pending",
            "priority": "medium",
            "type": "blog",
            "cluster": "discovered",
            "discovered_from": analysis["keyword"],
        }

        data["queue"].append(new_item)
        existing_topics.add(kw.lower())
        existing_slugs.add(slug)
        added += 1
        print(f"   💡  Added to queue: {kw.title()} → {last_date.isoformat()}")

    if added:
        data["_updated"] = TODAY
        queue_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return added


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 serp_research.py \"keyword\" [--discover-keywords]")
        sys.exit(1)

    keyword = sys.argv[1]
    discover = "--discover-keywords" in sys.argv

    analysis = research_keyword(keyword)

    print(f"\n{'='*60}")
    print(f"  SERP Research Results — {keyword}")
    print(f"{'='*60}")
    print(f"  Competitors found : {analysis['competitor_count']}")
    print(f"  Avg word count    : {analysis['avg_word_count']:,}")
    print(f"  Target word count : {analysis['target_word_count']:,}")
    print(f"\n  H2 topics to cover ({len(analysis['all_competitor_h2s'])}):")
    for h in analysis["all_competitor_h2s"][:15]:
        print(f"    - {h}")
    print(f"\n  FAQ questions ({len(analysis['faq_questions_to_cover'])}):")
    for q in analysis["faq_questions_to_cover"][:8]:
        print(f"    - {q}")
    if analysis["discovered_keywords"]:
        print(f"\n  Discovered keywords ({len(analysis['discovered_keywords'])}):")
        for kw in analysis["discovered_keywords"]:
            print(f"    - {kw}")

    if discover:
        added = add_discovered_keywords_to_queue(analysis)
        print(f"\n  Added {added} keyword(s) to content-queue.json")

    print(f"{'='*60}\n")
