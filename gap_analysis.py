#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  Content Gap Analysis — NeuronWriter + GSC + Crawl4AI + Claude

  Auto-discovers keywords from three sources, then finds content gaps:
    1. NeuronWriter  — related terms + PAA from each analysis
    2. Google Search Console — real queries people used to find your site
    3. Crawl4AI — competitor H2 topics, FAQ questions, content angles

  Keyword pool grows automatically with each run, saved to gap-keywords.json.

  Usage:
    python3 gap_analysis.py                     # run gap analysis
    python3 gap_analysis.py --dry-run           # preview without saving
    python3 gap_analysis.py --discover          # only refresh keyword pool
    python3 gap_analysis.py --keyword "..."     # single keyword
    python3 gap_analysis.py --crawl             # include competitor crawling

  Requires:
    NEURONWRITER_API_KEY + NEURONWRITER_PROJECT
    ANTHROPIC_API_KEY
    google-indexing-key.json  (same service account used for Indexing API)
    crawl4ai  (pip install crawl4ai && crawl4ai-setup)
═══════════════════════════════════════════════════════════════
"""

import anthropic
import argparse
import asyncio
import datetime
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from neuron_seo import get_neuron_recommendations

# Crawl4AI — optional, for competitor scraping
try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    from crawl4ai.markdown_generators import DefaultMarkdownGenerator
    HAS_CRAWL4AI = True
except ImportError:
    HAS_CRAWL4AI = False


# ─────────────────────────────────────────────
# CONFIG — Load from config.json if available
# ─────────────────────────────────────────────

TODAY          = datetime.date.today().isoformat()
QUEUE_PATH     = Path(__file__).parent / "content-queue.json"
REGISTRY_PATH  = Path(__file__).parent / "content-registry.json"
KEYWORDS_PATH  = Path(__file__).parent / "gap-keywords.json"
MODEL          = "claude-sonnet-4-6"
GSC_KEY_FILE   = Path(__file__).parent / "google-indexing-key.json"

_config_path = Path(__file__).parent / "config.json"
if _config_path.exists():
    with open(_config_path) as _f:
        _config = json.load(_f)
    SITE_URL = _config.get("site", {}).get("domain", "https://ssusa.co")
    MARKET = _config.get("_market", "au")
    COUNTRY = _config.get("country", "Australia")
    BRAND = _config.get("site", {}).get("brand", "AussiePokies96")
else:
    SITE_URL = "https://ssusa.co"
    MARKET = "au"
    COUNTRY = "Australia"
    BRAND = "AussiePokies96"

# Seed keywords — the starting point. New ones get added automatically.
SEED_KEYWORDS = [
    "best payid casino australia",
    "payid casino australia",
    "best online casino australia",
    "real money pokies australia",
    "best online pokies australia",
    "no deposit bonus casino australia",
    "fast payout casino australia",
    "crypto casino australia",
    "bitcoin casino australia",
    "how to play pokies online",
    "online gambling australia legal",
    "best casino bonus australia 2026",
    "instant withdrawal casino australia",
    "payid casino deposit australia",
    "e-wallet casino australia",
    "best pokies sites australia",
    "are online casinos legal in australia",
    "casino minimum deposit australia",
]


# ─────────────────────────────────────────────
# KEYWORD POOL — persistent, grows over time
# ─────────────────────────────────────────────

def load_keyword_pool() -> dict:
    """Load keyword pool from gap-keywords.json, merging with seeds."""
    if KEYWORDS_PATH.exists():
        pool = json.loads(KEYWORDS_PATH.read_text(encoding="utf-8"))
    else:
        pool = {"keywords": {}, "_updated": TODAY}

    # Ensure all seeds are present
    for kw in SEED_KEYWORDS:
        if kw not in pool["keywords"]:
            pool["keywords"][kw] = {"source": "seed", "added": TODAY, "runs": 0}

    return pool


def save_keyword_pool(pool: dict) -> None:
    pool["_updated"] = TODAY
    KEYWORDS_PATH.write_text(json.dumps(pool, indent=2, ensure_ascii=False), encoding="utf-8")


def add_keywords_to_pool(pool: dict, keywords: list, source: str) -> int:
    """Add new keywords to pool. Returns count of new ones added."""
    added = 0
    for kw in keywords:
        kw = kw.strip().lower()
        if not kw or len(kw) < 8:
            continue
        if kw not in pool["keywords"]:
            pool["keywords"][kw] = {"source": source, "added": TODAY, "runs": 0}
            added += 1
    return added


def get_keywords_to_run(pool: dict, limit: int) -> list:
    """Return keywords sorted by least-recently-run first."""
    kws = pool["keywords"]
    sorted_kws = sorted(kws.keys(), key=lambda k: (kws[k].get("runs", 0), kws[k].get("last_run", "0")))
    return sorted_kws[:limit]


# ─────────────────────────────────────────────
# SOURCE 1: NEURONWRITER KEYWORD DISCOVERY
# ─────────────────────────────────────────────

def extract_keywords_from_neuron(neuron: dict) -> list:
    """Pull related keywords from a NeuronWriter analysis result."""
    discovered = []

    # Long-tail from suggest questions
    for q in neuron.get("questions_suggest", []):
        q = q.strip().lower()
        if "australia" in q or "aussie" in q or "payid" in q or "pokies" in q or "casino" in q:
            discovered.append(q)

    # PAA questions as keywords
    for q in neuron.get("questions_paa", []):
        q = q.strip().lower()
        if any(w in q for w in ["casino", "pokies", "australia", "payid", "bonus", "deposit", "withdraw"]):
            discovered.append(q)

    # H2 terms that look like keyword phrases
    for term in neuron.get("h2_terms", []):
        term = term.strip().lower()
        if len(term.split()) >= 3:
            discovered.append(term)

    # Content terms as seed phrases
    for t in neuron.get("content_terms", [])[:10]:
        term = t.get("term", "").strip().lower()
        if len(term.split()) >= 2 and any(w in term for w in ["casino", "australia", "payid", "pokies", "bonus"]):
            discovered.append(term)

    return list(set(discovered))


# ─────────────────────────────────────────────
# SOURCE 2: GOOGLE SEARCH CONSOLE
# ─────────────────────────────────────────────

def fetch_gsc_keywords(pool: dict) -> int:
    """Pull top queries from Google Search Console and add to pool."""
    if not GSC_KEY_FILE.exists():
        print(f"   ⚠️   GSC key not found at {GSC_KEY_FILE} — skipping GSC discovery.")
        return 0

    try:
        from google.oauth2 import service_account
        import google.auth.transport.requests as google_transport
    except ImportError:
        print("   ⚠️   google-auth not installed — skipping GSC. Run: pip3 install google-auth")
        return 0

    try:
        creds = service_account.Credentials.from_service_account_file(
            str(GSC_KEY_FILE),
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
        )
        session = google_transport.AuthorizedSession(creds)
    except Exception as e:
        print(f"   ⚠️   GSC credentials error: {e}")
        return 0

    # Query last 90 days — wider window captures more data for newer sites
    end_date   = datetime.date.today().isoformat()
    start_date = (datetime.date.today() - datetime.timedelta(days=90)).isoformat()

    payload = {
        "startDate": start_date,
        "endDate":   end_date,
        "dimensions": ["query"],
        "rowLimit": 200,
        "dimensionFilterGroups": [{
            "filters": [{
                "dimension": "country",
                "operator": "equals",
                "expression": "aus"   # Australia country code
            }]
        }]
    }

    import urllib.parse
    site_encoded = urllib.parse.quote(SITE_URL + "/", safe="")

    try:
        resp = session.post(
            f"https://searchconsole.googleapis.com/v1/sites/{site_encoded}/searchAnalytics/query",
            json=payload,
            timeout=15
        )
        if resp.status_code != 200:
            # Try without country filter (site may have no AUS-specific data yet)
            payload.pop("dimensionFilterGroups", None)
            resp = session.post(
                f"https://searchconsole.googleapis.com/v1/sites/{site_encoded}/searchAnalytics/query",
                json=payload,
                timeout=15
            )

        if resp.status_code != 200:
            print(f"   ⚠️   GSC API error {resp.status_code}: {resp.text[:100]}")
            return 0

        data = resp.json()
        rows = data.get("rows", [])

        if not rows:
            print("   ℹ️   GSC: no query data yet (site too new — check back in 2–4 weeks)")
            return 0

        # Extract queries with at least 1 impression
        gsc_queries = [
            row["keys"][0].lower()
            for row in rows
            if row.get("impressions", 0) >= 1
        ]

        added = add_keywords_to_pool(pool, gsc_queries, source="gsc")
        print(f"   ✅  GSC: {len(rows)} queries fetched, {added} new keywords added to pool")
        return added

    except Exception as e:
        print(f"   ⚠️   GSC fetch failed: {e}")
        return 0


# ─────────────────────────────────────────────
# LOAD EXISTING CONTENT
# ─────────────────────────────────────────────

def load_existing_content() -> set:
    covered = set()
    if REGISTRY_PATH.exists():
        reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        for page in reg.get("pages", []):
            covered.add(page.get("title", "").lower())
            for kw in page.get("keywords", []):
                covered.add(kw.lower())
    if QUEUE_PATH.exists():
        queue = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
        for item in queue.get("queue", []) + queue.get("published", []):
            covered.add(item.get("topic", "").lower())
            covered.add(item.get("slug", "").lower().replace("-", " "))
    return covered


# ─────────────────────────────────────────────
# CRAWL4AI COMPETITOR SCRAPING
# ─────────────────────────────────────────────

async def crawl_competitor_page(url: str) -> dict:
    """Scrape a single competitor page and extract SEO data."""
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
                return {"url": url, "error": "crawl_failed"}

            md = result.markdown.raw_markdown if result.markdown else ""

            h2s = []
            faqs = []
            for line in md.split("\n"):
                line = line.strip()
                if line.startswith("## "):
                    h2s.append(line[3:].strip())
                if "?" in line and 15 < len(line) < 200:
                    if line.startswith(("#", "**", "- ")):
                        faqs.append(line.lstrip("#*- ").strip())

            return {
                "url": url,
                "word_count": len(md.split()),
                "h2_topics": h2s[:15],
                "faq_questions": faqs[:10],
                "content_preview": md[:2000],
            }
    except Exception as e:
        return {"url": url, "error": str(e)}


def crawl_neuron_competitors(neuron: dict) -> list:
    """Crawl the top competitor URLs from NeuronWriter data using Crawl4AI."""
    competitors = neuron.get("competitors", [])
    if not competitors:
        return []

    # Get top 3 competitor URLs
    urls = [c.get("url", "") for c in competitors[:3] if c.get("url")]
    if not urls:
        return []

    print(f"   🕷️  Crawling {len(urls)} competitor pages...")
    results = []
    for url in urls:
        data = asyncio.run(crawl_competitor_page(url))
        if "error" not in data:
            results.append(data)
            print(f"       ✅ {url[:60]}... ({data['word_count']} words, {len(data['h2_topics'])} H2s)")
        else:
            print(f"       ⚠️  {url[:60]}... (failed)")
        time.sleep(1)

    return results


def extract_competitor_gaps(crawled: list, existing: set) -> dict:
    """Extract topics and questions from crawled competitors that we don't cover."""
    all_h2s = []
    all_faqs = []
    for comp in crawled:
        all_h2s.extend(comp.get("h2_topics", []))
        all_faqs.extend(comp.get("faq_questions", []))

    # Deduplicate
    unique_h2s = list(dict.fromkeys(all_h2s))
    unique_faqs = list(dict.fromkeys(all_faqs))

    # Filter out topics we already cover
    uncovered_h2s = [h for h in unique_h2s if not any(kw in h.lower() for kw in existing)]
    uncovered_faqs = [f for f in unique_faqs if not any(kw in f.lower() for kw in existing)]

    return {
        "uncovered_h2_topics": uncovered_h2s[:10],
        "uncovered_faq_questions": uncovered_faqs[:8],
        "competitor_avg_words": sum(c.get("word_count", 0) for c in crawled) // max(len(crawled), 1),
    }


# ─────────────────────────────────────────────
# CLAUDE GAP ANALYSIS
# ─────────────────────────────────────────────

def analyze_gaps_with_claude(keyword: str, neuron: dict, existing: set,
                             crawl_data: dict = None) -> list:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌  ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    paa       = neuron.get("questions_paa", [])
    suggest   = neuron.get("questions_suggest", [])
    content_q = neuron.get("questions_content", [])
    h2_terms  = neuron.get("h2_terms", [])
    entities  = [e["term"] for e in neuron.get("entities", [])]
    competitors = neuron.get("competitors", [])
    comp_titles = [f"#{c['rank']}: {c['title']}" for c in competitors[:8]]

    # Build Crawl4AI competitor data block
    crawl_block = ""
    if crawl_data:
        crawl_block = f"""
COMPETITOR CRAWL DATA (from Crawl4AI — real page scrapes):
Average competitor word count: {crawl_data.get('competitor_avg_words', 'unknown')}

H2 Topics competitors cover that we DON'T:
{json.dumps(crawl_data.get('uncovered_h2_topics', []), indent=2)}

FAQ Questions competitors answer that we DON'T:
{json.dumps(crawl_data.get('uncovered_faq_questions', []), indent=2)}

IMPORTANT: Prioritize article topics that fill THESE specific gaps — they come from
real competitor pages and represent proven content angles we're missing.
"""

    prompt = f"""You are an SEO content strategist for a {COUNTRY} online casino affiliate site ({BRAND}, {SITE_URL}).

KEYWORD ANALYSED: "{keyword}"

NEURONWRITER DATA:
People Also Ask: {json.dumps(paa)}
Suggested questions: {json.dumps(suggest)}
Content questions from top pages: {json.dumps(content_q)}
H2 topics competitors use: {json.dumps(h2_terms)}
Key entities: {json.dumps(entities)}
Top competitors: {json.dumps(comp_titles)}
{crawl_block}
OUR EXISTING CONTENT (already published or queued):
{json.dumps(sorted(list(existing))[:60], indent=2)}

TASK: Identify 4-6 NEW article topics we should create that:
1. Answer real questions {COUNTRY} players are asking (from PAA/suggest lists above)
2. Are NOT already covered in our existing content
3. Are specific to {COUNTRY} players
4. Each can stand alone as a full article
{f"5. Prioritize topics that fill the Crawl4AI competitor gaps above" if crawl_data else ""}

Return ONLY a JSON array:
[
  {{
    "topic": "Full article title targeting {COUNTRY} players",
    "slug": "url-friendly-slug",
    "keywords": ["primary keyword", "secondary keyword", "tertiary keyword"],
    "gap_reason": "Which question/gap this fills"
  }}
]"""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
            extra_headers={"anthropic-beta": "output-128k-2025-02-19"},
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(text)
    except Exception as e:
        print(f"   ⚠️   Claude analysis failed: {e}")
        return []


# ─────────────────────────────────────────────
# ADD TO QUEUE
# ─────────────────────────────────────────────

def add_to_queue(new_topics: list, dry_run: bool = False) -> int:
    if not new_topics:
        return 0

    queue = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    pending_dates = [
        item.get("publish_date", TODAY)
        for item in queue.get("queue", [])
        if item.get("status") == "pending"
    ]
    last_date = datetime.date.fromisoformat(max(pending_dates)) if pending_dates \
                else datetime.date.fromisoformat(TODAY)

    existing_slugs  = {item.get("slug", "") for item in queue.get("queue", [])}
    existing_topics = {item.get("topic", "").lower() for item in queue.get("queue", [])}

    # Derive publish cadence from config (days between articles)
    try:
        cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
        pace = cfg.get("publishing_pace", {})
        max_per_week = pace.get("max_per_week", 3)
        days_between = max(1, round(7 / max_per_week))
    except Exception:
        days_between = 4

    # Cap the scheduling window: don't schedule more than 6 months out
    cap_date = datetime.date.fromisoformat(TODAY) + datetime.timedelta(days=180)
    if last_date > cap_date:
        last_date = cap_date

    added = 0
    for t in new_topics:
        slug  = t.get("slug", "")
        topic = t.get("topic", "")
        if slug in existing_slugs or topic.lower() in existing_topics:
            print(f"   ⏭️   Already queued: {topic}")
            continue

        last_date += datetime.timedelta(days=days_between)
        entry = {
            "topic":        topic,
            "slug":         slug,
            "keywords":     t.get("keywords", []),
            "publish_date": last_date.isoformat(),
            "status":       "pending",
            "_gap_reason":  t.get("gap_reason", ""),
        }

        if dry_run:
            print(f"   [DRY RUN] {topic} → {last_date.isoformat()}")
            print(f"             {t.get('gap_reason','')}")
        else:
            queue["queue"].append(entry)
            existing_slugs.add(slug)
            existing_topics.add(topic.lower())
            print(f"   ✅  Added: {topic} → {last_date.isoformat()}")
            added += 1

    if not dry_run and added > 0:
        queue["_updated"] = TODAY
        QUEUE_PATH.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")

    return added


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Content Gap Analysis — NeuronWriter + GSC + Crawl4AI + Claude")
    parser.add_argument("--dry-run",  action="store_true", help="Preview without saving to queue")
    parser.add_argument("--discover", action="store_true", help="Only refresh keyword pool, skip gap analysis")
    parser.add_argument("--keyword",  type=str, default=None, help="Analyse a single keyword")
    parser.add_argument("--limit",    type=int, default=999, help="Max keywords to analyse (default: all)")
    parser.add_argument("--no-gsc",   action="store_true", help="Skip Google Search Console discovery")
    parser.add_argument("--crawl",    action="store_true",
                       help="Use Crawl4AI to scrape competitor pages for deeper gap analysis. "
                            "Adds ~30s per keyword but finds content angles keyword tools miss.")
    parser.add_argument("--no-crawl", action="store_true", help="Disable Crawl4AI even if installed")
    args = parser.parse_args()

    use_crawl = args.crawl and HAS_CRAWL4AI and not args.no_crawl

    print(f"\n{'='*60}")
    print(f"  🔍  Content Gap Analysis — NeuronWriter + GSC + {'Crawl4AI + ' if use_crawl else ''}Claude")
    print(f"  Market: {MARKET.upper()} ({COUNTRY}) | Site: {SITE_URL}")
    print(f"  Date : {TODAY}")
    print(f"  Mode : {'DRY RUN' if args.dry_run else 'DISCOVER ONLY' if args.discover else 'LIVE'}")
    if args.crawl and not HAS_CRAWL4AI:
        print(f"  ⚠️  --crawl requested but crawl4ai not installed. Run: pip install crawl4ai && crawl4ai-setup")
    print(f"{'='*60}\n")

    # ── Load keyword pool ──
    pool = load_keyword_pool()
    print(f"📦  Keyword pool: {len(pool['keywords'])} keywords loaded\n")

    # ── Source 2: Google Search Console ──
    if not args.no_gsc and not args.keyword:
        print("🔗  Fetching keywords from Google Search Console...")
        gsc_added = fetch_gsc_keywords(pool)
        if gsc_added:
            save_keyword_pool(pool)
        print()

    if args.discover:
        print(f"✅  Keyword pool now has {len(pool['keywords'])} keywords.")
        print(f"    Saved to gap-keywords.json")
        sys.exit(0)

    # ── Select keywords to analyse ──
    if args.keyword:
        keywords = [args.keyword]
    else:
        keywords = get_keywords_to_run(pool, args.limit)

    print(f"🎯  Analysing {len(keywords)} keyword(s):\n")
    for kw in keywords:
        print(f"    • {kw}")
    print()

    existing    = load_existing_content()
    all_gaps    = []
    total_added = 0

    print(f"📚  Existing content: {len(existing)} topics/keywords indexed\n")

    for i, keyword in enumerate(keywords, 1):
        print(f"[{i}/{len(keywords)}] 🔎  \"{keyword}\"")

        neuron = get_neuron_recommendations(keyword)
        if not neuron:
            print(f"   ⚠️   NeuronWriter returned no data — skipping\n")
            continue

        # ── Source 1: extract new keywords from this NeuronWriter result ──
        discovered = extract_keywords_from_neuron(neuron)
        new_kws = add_keywords_to_pool(pool, discovered, source="neuronwriter")
        if new_kws:
            print(f"   🔑  {new_kws} new keyword(s) discovered from NeuronWriter")

        q_count = len(neuron.get("questions_paa", [])) + len(neuron.get("questions_suggest", []))
        print(f"   📊  {q_count} questions | {len(neuron.get('h2_terms',[]))} H2 terms | "
              f"{len(neuron.get('competitors',[]))} competitors")

        # ── Source 3: Crawl4AI competitor scraping ──
        crawl_data = None
        if use_crawl:
            crawled = crawl_neuron_competitors(neuron)
            if crawled:
                crawl_data = extract_competitor_gaps(crawled, existing)
                if crawl_data.get("uncovered_h2_topics"):
                    print(f"   🕳️  Crawl4AI found {len(crawl_data['uncovered_h2_topics'])} uncovered H2 topics")
                if crawl_data.get("uncovered_faq_questions"):
                    print(f"   ❓  Crawl4AI found {len(crawl_data['uncovered_faq_questions'])} unanswered FAQs")

        gaps = analyze_gaps_with_claude(keyword, neuron, existing, crawl_data=crawl_data)
        print(f"   🕳️   {len(gaps)} gap(s) found:")
        for g in gaps:
            print(f"       → {g.get('topic')}")
            all_gaps.append(g)

        added = add_to_queue(gaps, dry_run=args.dry_run)
        total_added += added

        # Mark keyword as run
        if keyword in pool["keywords"]:
            pool["keywords"][keyword]["runs"] = pool["keywords"][keyword].get("runs", 0) + 1
            pool["keywords"][keyword]["last_run"] = TODAY

        # Update existing to avoid re-suggesting same topics
        for g in gaps:
            existing.add(g.get("topic", "").lower())
            existing.add(g.get("slug", "").lower().replace("-", " "))

        print()
        if i < len(keywords):
            time.sleep(2)

    # Save updated pool
    save_keyword_pool(pool)

    print(f"{'='*60}")
    print(f"  ✅  Gap Analysis Complete")
    print(f"  Keywords analysed  : {len(keywords)}")
    print(f"  Gaps found         : {len(all_gaps)}")
    print(f"  Added to queue     : {total_added}")
    print(f"  Keyword pool size  : {len(pool['keywords'])}")
    print(f"  Crawl4AI           : {'enabled' if use_crawl else 'disabled'}")
    if args.dry_run:
        print(f"  (DRY RUN — remove --dry-run to actually add)")
    print(f"{'='*60}")
