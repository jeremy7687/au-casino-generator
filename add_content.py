#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  Content Creator + Auto-Interlinking Engine
  
  Creates new blog articles and automatically interlinks them
  with existing pages on your site.

  Three ways to use:
    1. CLI:         python3 add_content.py --topic "Aristocrat pokies RTP guide"
    2. Claude Code: "run add_content.py to create an article about Aristocrat pokies"
    3. Google Sheet: add a row → triggers via Apps Script (see docs)

  What it does:
    1. Generates a blog article via Claude API
    2. Scans content-registry.json for relevant pages
    3. Injects internal links INTO the new article (pointing to existing pages)
    4. Injects links INTO existing pages (pointing back to the new article)
    5. Updates sitemap.xml
    6. Updates content-registry.json
    7. Pushes everything to GitHub

  Prerequisites:
    pip install anthropic PyGithub
    
  Required files:
    content-registry.json  — in the same directory
    generated/             — local output directory (auto-created)
═══════════════════════════════════════════════════════════════
"""

import anthropic
import argparse
import datetime
import json
import os
import re
import sys
import time
from pathlib import Path
from github import Github, GithubException

# GEO optimization — AI search citation formatting + Speakable schema
sys.path.insert(0, str(Path(__file__).parent))
try:
    from geo_optimize import get_full_geo_block
    HAS_GEO = True
except ImportError:
    HAS_GEO = False


# ─────────────────────────────────────────────
# CONFIGURATION — Auto-loaded from config.json
# ─────────────────────────────────────────────
# Place a config.json in your repo root with market-specific values.
# The script auto-detects which market based on the config file.
# See config-au.json and config-pg.json for examples.

MODEL = "claude-sonnet-4-6"
TODAY = datetime.date.today().isoformat()
YEAR = datetime.date.today().year

# Load config.json from the script's directory (repo root)
_config_path = Path(__file__).parent / "config.json"
if not _config_path.exists():
    print(f"⚠️  config.json not found in {Path(__file__).parent}")
    print(f"   Falling back to hardcoded defaults.")
    print(f"   To use market-specific config, create config.json from config-au.json.")
    # Fallback defaults (AU market)
    CONFIG = {
        "_market": "au",
        "github_repo": "jeremy7687/au-casino-generator",
        "site": {
            "brand": "AussiePokies96",
            "domain": "https://ssusa.co",
            "author": "Blake Donovan",
            "author_bio": "Blake has reviewed Australian online casinos since 2019, specialising in payout speed and pokie variety.",
            "email": "editor@ssusa.co",
            "ga4": "",
            "twitter": "@AussiePokies96",
            "hreflang": "en-AU",
        },
        "design": {
            "bg": "#09090f", "card_bg": "#111520", "border": "#1d2235",
            "gold": "#f8bc2e", "green": "#00d97e", "red": "#ff4757",
            "text": "#edf0f7", "muted": "#7a85a0",
            "font_head": "Barlow Condensed", "font_body": "Inter",
        },
        "language": {
            "use": ["pokies", "punters"],
            "avoid": ["slots", "players"],
            "notes": "Use 'pokies' over 'slots' and 'punters' over 'players' at 70%+ ratio.",
        },
        "currency": "AUD",
        "country": "Australia",
        "country_code": "AU",
        "nav_links": "Home | Top Casinos (/) | Guides (/guides/best-payid-casinos/) | About (/about/)",
        "content_paths": {"articles": "blog/{slug}.html", "output_dir": "generated"},
        "responsible_gambling": {
            "text": "Gambling can be addictive. Play responsibly.",
            "helpline": "Gambling Help Online 1800 858 858",
            "style": "Red left border, disclaimer box",
        },
        "interlinking": {"max_links_in_new_article": 8, "max_backlinks_per_page": 2, "min_keyword_match_score": 2},
    }
else:
    with open(_config_path, encoding="utf-8") as _f:
        CONFIG = json.load(_f)

GITHUB_REPO = CONFIG["github_repo"]
MODEL = CONFIG.get("model", MODEL)

SITE = CONFIG["site"]
SITE["year"] = YEAR  # always use current year

DESIGN = CONFIG["design"]

MARKET = CONFIG.get("_market", "unknown")
COUNTRY = CONFIG.get("country", "")
COUNTRY_CODE = CONFIG.get("country_code", "")
CURRENCY = CONFIG.get("currency", "")
NAV_LINKS = CONFIG.get("nav_links", "Home (/)")
HREFLANG = SITE.get("hreflang", "en")

LANGUAGE_RULES = CONFIG.get("language", {})
LANG_USE = LANGUAGE_RULES.get("use", [])
LANG_AVOID = LANGUAGE_RULES.get("avoid", [])
LANG_NOTES = LANGUAGE_RULES.get("notes", "")

RESPONSIBLE_GAMBLING = CONFIG.get("responsible_gambling", {})
RG_TEXT = RESPONSIBLE_GAMBLING.get("text", "Gamble responsibly.")
RG_HELPLINE = RESPONSIBLE_GAMBLING.get("helpline", "")
RG_STYLE = RESPONSIBLE_GAMBLING.get("style", "Red left border, disclaimer box")

CONTENT_PATHS = CONFIG.get("content_paths", {})
ARTICLE_PATH_TEMPLATE = CONTENT_PATHS.get("articles", "blog/{slug}.html")
OUTPUT_DIR = CONTENT_PATHS.get("output_dir", "generated")

INTERLINK_CONFIG = CONFIG.get("interlinking", {})

# Max internal links to inject per direction
MAX_LINKS_IN_NEW_ARTICLE = INTERLINK_CONFIG.get("max_links_in_new_article", 8)
MAX_BACKLINKS_PER_PAGE = INTERLINK_CONFIG.get("max_backlinks_per_page", 2)
MIN_KEYWORD_MATCH_SCORE = INTERLINK_CONFIG.get("min_keyword_match_score", 2)

# Build language instruction string for prompts
if LANG_USE and LANG_AVOID:
    _lang_pairs = [f'prefer "{use}" over "{avoid}" (70/30 ratio — both acceptable)' for use, avoid in zip(LANG_USE, LANG_AVOID)]
    LANGUAGE_INSTRUCTION = "Language guidance: " + ", ".join(_lang_pairs) + ". " + LANG_NOTES
else:
    LANGUAGE_INSTRUCTION = LANG_NOTES or ""

print(f"📍  Market: {MARKET.upper()} ({COUNTRY}) | Brand: {SITE['brand']} | Domain: {SITE['domain']}")


# ─────────────────────────────────────────────
# CONTENT REGISTRY
# ─────────────────────────────────────────────

REGISTRY_PATH = Path(__file__).parent / "content-registry.json"

def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        print(f"❌  {REGISTRY_PATH} not found. Create it first.")
        sys.exit(1)
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        return json.load(f)

def save_registry(registry: dict) -> None:
    registry["_updated"] = TODAY
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    print(f"   📝  Updated content-registry.json")


# ─────────────────────────────────────────────
# KEYWORD-BASED RELEVANCE SCORING
# ─────────────────────────────────────────────

def score_relevance(new_keywords: list, existing_page: dict) -> int:
    """Score how relevant an existing page is to the new article.
    Higher = more relevant. Based on keyword overlap."""
    if existing_page.get("nolink"):
        return 0

    existing_kws = set(k.lower() for k in existing_page.get("keywords", []))
    new_kws = set(k.lower() for k in new_keywords)

    # Direct keyword overlap
    overlap = len(new_kws & existing_kws)

    # Partial word matching (e.g. "pokies" appears in both)
    new_words = set()
    for kw in new_kws:
        new_words.update(kw.split())
    existing_words = set()
    for kw in existing_kws:
        existing_words.update(kw.split())

    word_overlap = len(new_words & existing_words)

    # Category bonus — same category pages are more relevant
    category_bonus = 0
    # (category is set during article creation)

    return overlap * 3 + word_overlap + category_bonus


def find_relevant_pages(new_keywords: list, registry: dict, limit: int = None) -> list:
    """Find existing pages most relevant to the new article's keywords."""
    if limit is None:
        limit = MAX_LINKS_IN_NEW_ARTICLE

    scored = []
    for page in registry["pages"]:
        if page.get("nolink"):
            continue
        score = score_relevance(new_keywords, page)
        if score >= MIN_KEYWORD_MATCH_SCORE:
            scored.append((score, page))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [page for _, page in scored[:limit]]


# ─────────────────────────────────────────────
# CLAUDE API — with retry
# ─────────────────────────────────────────────

def call_claude(prompt: str, label: str, max_tokens: int = 128000) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌  ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    for attempt in range(1, 4):
        try:
            print(f"🤖  Generating {label}..." + (f" (attempt {attempt})" if attempt > 1 else ""))
            response = client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                extra_headers={"anthropic-beta": "output-128k-2025-02-19"},
            )

            html = response.content[0].text.strip()

            # Cost tracking
            u = response.usage
            cost = (u.input_tokens * 3.0 + u.output_tokens * 15.0) / 1_000_000
            print(f"   📊  {u.input_tokens:,} in + {u.output_tokens:,} out = ${cost:.4f}")

            # Strip markdown fences
            if html.startswith("```"):
                html = html.split("\n", 1)[1]
            if html.endswith("```"):
                html = html.rsplit("```", 1)[0]
            html = html.strip()

            # Inject GA4
            ga4_id = SITE.get("ga4", "G-LK39GGY3G3")
            if ga4_id and "googletagmanager.com" not in html and "</head>" in html:
                ga4_snippet = (
                    f'<!-- Google tag (gtag.js) -->\n'
                    f'<script async src="https://www.googletagmanager.com/gtag/js?id={ga4_id}"></script>\n'
                    f'<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag("js",new Date());gtag("config","{ga4_id}");</script>\n'
                )
                html = html.replace("</head>", ga4_snippet + "</head>", 1)

            return html

        except anthropic.RateLimitError:
            wait = 2 ** attempt * 5
            print(f"⏳  Rate limited. Waiting {wait}s...")
            time.sleep(wait)
            if attempt == 3:
                raise
        except Exception as e:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt * 2)


# ─────────────────────────────────────────────
# CONTENT TYPE PROMPT TEMPLATES
# ─────────────────────────────────────────────

def _build_review_prompt(topic: str, slug: str, target_keywords: list,
                         relevant_pages: list, casino_data: dict = None) -> str:
    """Build a review page prompt with score breakdown, pros/cons, verdict."""

    links_block = "\n".join(
        f'- Link to {p["url"]} with anchor text like "{p.get("anchors", [p["title"]])[0]}"'
        for p in relevant_pages
    ) or "- No specific internal links required"

    nav_links = NAV_LINKS
    casino_name = casino_data.get("name", topic.split("Review")[0].strip()) if casino_data else topic

    # If we have operator data from config, include it
    casino_json = ""
    if casino_data:
        casino_json = f"\n## CASINO DATA (use this real data — do not fabricate)\n{json.dumps(casino_data, indent=2)}\n"

    return f"""Generate a complete, production-ready HTML casino REVIEW page for a {COUNTRY} casino affiliate site.

## TOPIC
{topic}

## TARGET KEYWORDS
{json.dumps(target_keywords)}

## SITE INFO
Brand: {SITE['brand']} | Domain: {SITE['domain']} | Author: {SITE['author']}
Author bio: {SITE['author_bio']} | Year: {SITE['year']}
Canonical: {SITE['domain']}/{slug}/

## DESIGN TOKENS
--bg:{DESIGN['bg']} --card-bg:{DESIGN['card_bg']} --border:{DESIGN['border']}
--gold:{DESIGN['gold']} --green:{DESIGN['green']} --text:{DESIGN['text']} --muted:{DESIGN['muted']}
Fonts: '{DESIGN['font_head']}' 700/800 (headings) + '{DESIGN['font_body']}' 400/500/600 (body) via Google Fonts
{casino_json}
## INTERNAL LINKS
{links_block}

## REQUIRED REVIEW STRUCTURE (all sections mandatory)

### HEAD
- All CSS in a single <style> block — no per-element inline styles
- <title> under 60 chars: "{casino_name} Review {COUNTRY} {SITE['year']} — Bonus & PayID | {SITE['brand']}"
- Meta description under 160 chars
- Canonical, hreflang="{SITE.get('hreflang', 'en-AU')}", OG + Twitter cards
- Google Fonts preconnect (font-display: swap)
- JSON-LD: Review schema + FAQPage + BreadcrumbList + Speakable
- No external CSS/JS except Google Fonts

### REVIEW HERO
- Breadcrumb: Home > Reviews > {casino_name}
- H1 with primary keyword
- Author byline + last updated date
- Score card: X.X/10 with star rating and verdict badge

### BONUS CLAIM BOX
- Welcome bonus headline (large text)
- Bonus detail, wagering, min deposit
- CTA button: "Claim Bonus at {casino_name} →" (affiliate link, rel="nofollow noopener sponsored")
- T&Cs disclaimer

### QUICK STATS GRID (6 cards)
- Welcome bonus, score, wagering, min deposit, payout speed, best for

### PROS & CONS
- 2-column grid. 4-5 pros (green ✓), 2-3 cons (red ✗)
- Use real data, not generic filler

### SCORE BREAKDOWN
- Rating bar for each category (Pokies Library, Payout Speed, Bonus Value, Mobile Experience, Support)
- Each X.X/10 with visual bar (width = score/10 * 100%)

### OVERVIEW (200-300 words)
- Atomic answer block in first paragraph: definitive verdict
- What this casino is, who it's best for, unique standout feature
- Internal links to related guides

### WELCOME BONUS BREAKDOWN
- Detailed bonus table (deposit tiers, match %, max bonus, free spins, wagering)
- How to claim (3 numbered steps)
- Wagering calculation in plain English

### GAME LIBRARY
- Total games count, top providers
- Best pokies with RTPs (name 5-6 specific titles)
- Live dealer section

### BANKING & PAYOUTS
- Payment methods table (method, deposit time, withdrawal time, min/max, fees)
- Focus on PayID as primary method
- Crypto options if available

### MOBILE EXPERIENCE
- Responsive design quality, app availability, mobile-specific features

### SAFETY & LICENSING
- License jurisdiction, security measures, responsible gambling tools

### VERDICT BOX
- 2-3 sentence definitive recommendation
- Final score
- CTA button

### FAQ (5 questions)
- Phrased as users would ask an AI assistant
- Each answer 40-60 words, self-contained

### RESPONSIBLE GAMBLING
- {RG_STYLE}
- {RG_TEXT}
- {RG_HELPLINE}

### FOOTER
- Brand + disclaimer + nav + copyright + 18+"""


def _build_guide_prompt(topic: str, slug: str, target_keywords: list,
                        relevant_pages: list) -> str:
    """Build a guide/comparison page prompt."""

    links_block = "\n".join(
        f'- Link to {p["url"]} with anchor text like "{p.get("anchors", [p["title"]])[0]}"'
        for p in relevant_pages
    ) or "- No specific internal links required"

    return f"""Generate a complete, production-ready HTML GUIDE page for a {COUNTRY} casino affiliate site.

## TOPIC
{topic}

## TARGET KEYWORDS
{json.dumps(target_keywords)}

## SITE INFO
Brand: {SITE['brand']} | Domain: {SITE['domain']} | Author: {SITE['author']}
Author bio: {SITE['author_bio']} | Year: {SITE['year']}
Canonical: {SITE['domain']}/{slug}/

## DESIGN TOKENS
--bg:{DESIGN['bg']} --card-bg:{DESIGN['card_bg']} --border:{DESIGN['border']}
--gold:{DESIGN['gold']} --green:{DESIGN['green']} --text:{DESIGN['text']} --muted:{DESIGN['muted']}
Fonts: '{DESIGN['font_head']}' 700/800 + '{DESIGN['font_body']}' 400/500/600 via Google Fonts

## INTERNAL LINKS
{links_block}

## REQUIRED GUIDE STRUCTURE

### HEAD
- All CSS in single <style> block — no inline styles
- <title> under 60 chars with primary keyword + {SITE['brand']}
- Meta description under 160 chars
- Canonical, hreflang, OG + Twitter cards
- Google Fonts (font-display: swap)
- JSON-LD: Article + FAQPage + BreadcrumbList + Speakable
- HowTo schema if the guide has step-by-step instructions

### HERO
- Breadcrumb: Home > Guides > [Guide Title]
- H1 with primary keyword
- Author byline + last updated date + estimated read time

### ARTICLE BODY (2,000-3,500 words)
- Atomic answer block in first 300 words (definitive, authoritative)
- H2 headings phrased as search queries (fan-out aware)
- Start every H2 with a direct answer sentence
- Comparison table of top casinos relevant to this guide topic
- Include specific data: min deposits, withdrawal times, game counts
- Practical how-to steps with numbered lists where appropriate
- Pros/cons section for the topic
- Internal links woven naturally into body
- {LANGUAGE_INSTRUCTION}

### FAQ (5-8 questions)
- Phrased as users would ask an AI assistant
- Each answer 40-60 words, self-contained, citable

### RESPONSIBLE GAMBLING
- {RG_STYLE} | {RG_TEXT} | {RG_HELPLINE}

### FOOTER
- Brand + disclaimer + nav + copyright + 18+"""


def _build_banking_prompt(topic: str, slug: str, target_keywords: list,
                          relevant_pages: list) -> str:
    """Build a banking/payment method guide prompt."""

    links_block = "\n".join(
        f'- Link to {p["url"]} with anchor text like "{p.get("anchors", [p["title"]])[0]}"'
        for p in relevant_pages
    ) or "- No specific internal links required"

    return f"""Generate a complete, production-ready HTML BANKING GUIDE page for a {COUNTRY} casino affiliate site.

## TOPIC
{topic}

## TARGET KEYWORDS
{json.dumps(target_keywords)}

## SITE INFO
Brand: {SITE['brand']} | Domain: {SITE['domain']} | Author: {SITE['author']}
Author bio: {SITE['author_bio']} | Year: {SITE['year']}
Canonical: {SITE['domain']}/{slug}/

## DESIGN TOKENS
--bg:{DESIGN['bg']} --card-bg:{DESIGN['card_bg']} --border:{DESIGN['border']}
--gold:{DESIGN['gold']} --green:{DESIGN['green']} --text:{DESIGN['text']} --muted:{DESIGN['muted']}
Fonts: '{DESIGN['font_head']}' 700/800 + '{DESIGN['font_body']}' 400/500/600 via Google Fonts

## INTERNAL LINKS
{links_block}

## REQUIRED BANKING GUIDE STRUCTURE

### HEAD
- All CSS in single <style> block
- <title>, meta description, canonical, hreflang, OG
- JSON-LD: Article + HowTo + FAQPage + BreadcrumbList
- Google Fonts (font-display: swap)

### HERO
- Breadcrumb: Home > Banking > [Title]
- H1, author byline, last updated

### BODY (1,500-2,500 words)
- Atomic answer block: "To deposit at {COUNTRY} casinos using [method], you need..."
- Step-by-step deposit guide (numbered, with HowTo schema)
- Step-by-step withdrawal guide
- Comparison table: deposit time, withdrawal time, min/max, fees per casino
- Pros/cons of this payment method
- Alternatives section (other payment methods with internal links)
- {LANGUAGE_INSTRUCTION}

### FAQ (5 questions) — payment-specific
### RESPONSIBLE GAMBLING
### FOOTER"""


# ─────────────────────────────────────────────
# ARTICLE GENERATION (type-aware)
# ─────────────────────────────────────────────

def generate_article(topic: str, slug: str, target_keywords: list,
                     relevant_pages: list, registry: dict,
                     neuron_block: str = "", geo_block: str = "",
                     content_type: str = "blog", casino_data: dict = None,
                     competitor_block: str = "") -> str:
    """Generate content based on type: blog, review, guide, or banking.
    All types include humanization, GEO optimization, and <style> block CSS."""

    # ── Type-specific prompt selection ──
    if content_type == "review":
        prompt = _build_review_prompt(topic, slug, target_keywords, relevant_pages, casino_data)
    elif content_type == "guide":
        prompt = _build_guide_prompt(topic, slug, target_keywords, relevant_pages)
    elif content_type == "banking":
        prompt = _build_banking_prompt(topic, slug, target_keywords, relevant_pages)
    else:
        # Default: blog article (existing prompt)
        prompt = _build_blog_prompt(topic, slug, target_keywords, relevant_pages)

    # ── Inject competitor intelligence (crawl4ai SERP research) ──
    if competitor_block:
        prompt += "\n\n" + competitor_block

    # ── Append shared blocks (humanization, GEO, NeuronWriter) ──
    prompt += HUMANIZATION_BLOCK

    prompt += f"""

## TECHNICAL RULES
- Single self-contained HTML — ALL CSS in <style>
- Mobile responsive
- ALL affiliate links (if any): target="_blank" rel="nofollow noopener sponsored"
- Internal links: normal <a href> tags, NO nofollow
- No external JS frameworks
- Use font-display: swap on Google Fonts

Return ONLY raw HTML. Start with <!DOCTYPE html>. No markdown. No explanation."""

    if geo_block:
        prompt += "\n\n" + geo_block
    if neuron_block:
        prompt += "\n\n" + neuron_block

    return call_claude(prompt, slug, max_tokens=128000)


# ─────────────────────────────────────────────
# HUMANIZATION BLOCK (shared across all content types)
# ─────────────────────────────────────────────

HUMANIZATION_BLOCK = f"""

## WRITING VOICE — CRITICAL

You are writing as {SITE['author']} for {SITE['brand']}. Write like a real reviewer.

### Priority Order (When Rules Conflict):
1. SEO structure (H-tags, schema, atomic answers) — never compromise
2. GEO optimization (atomic answer blocks stay authoritative and structured)
3. Humanized voice (everything OUTSIDE atomic answer blocks)

### Voice Rules:
1. SENTENCE VARIETY — Mix lengths. 25 words then 4 then 15 then 8. Never three similar-length in a row.
2. CONTRACTIONS — Always. "don't" not "do not". "it's" not "it is".
3. REAL DATA, NOT FAKE EXPERIENCE — Use real operator data. Say "we reviewed" or "based on our testing" — NOT fabricated first-person stories with fake dates.
4. OPINIONS — Take clear positions. "The wagering here is steep — 45x is above average."
5. CASUAL ASIDES — "(worth noting if you're a high roller)", "which surprised us".
6. NATURAL TRANSITIONS — "So here's the thing." "But there's a catch." Don't overuse "Furthermore"/"Moreover". Normal connectors fine occasionally.
7. SECOND PERSON — "You'll want to check the wagering before you deposit."
8. SPECIFIC OVER GENERAL — "3,200+ pokies from Pragmatic Play, Evolution, Hacksaw" not "wide range of pokies".
9. PARAGRAPH RHYTHM — Vary length. 4 sentences, then 1, then 3, then 2.
10. READING LEVEL — 7th-8th grade. "use" not "utilise". "fast" not "expeditious".

### Words to AVOID OVERUSING (max 1 per article):
"comprehensive", "robust", "leverage", "utilize", "delve", "embark", "realm", "elevate",
"foster", "cutting-edge", "seamless", "It's worth noting", "In today's", "In conclusion"
"""


def _build_blog_prompt(topic, slug, target_keywords, relevant_pages):
    """Build a blog article prompt."""
    links_block = "\n".join(
        f'- Link to {p["url"]} with anchor text like "{p.get("anchors", [p["title"]])[0]}"'
        for p in relevant_pages
    ) or "- No specific internal links required"

    return f"""Generate a complete, production-ready HTML blog article for a {COUNTRY} casino affiliate site.

## TOPIC
{topic}

## TARGET KEYWORDS
{json.dumps(target_keywords)}

## SITE INFO
Brand: {SITE['brand']} | Domain: {SITE['domain']} | Author: {SITE['author']}
Author bio: {SITE['author_bio']} | Year: {SITE['year']}
Canonical: {SITE['domain']}/blog/{slug}/

## DESIGN TOKENS
--bg:{DESIGN['bg']} --card-bg:{DESIGN['card_bg']} --border:{DESIGN['border']}
--gold:{DESIGN['gold']} --green:{DESIGN['green']} --text:{DESIGN['text']} --muted:{DESIGN['muted']}
Fonts: '{DESIGN['font_head']}' 700/800 + '{DESIGN['font_body']}' 400/500/600 via Google Fonts

## INTERNAL LINKS
{links_block}

## ATOMIC ANSWER BLOCKS
1. FIRST 300 WORDS: 40-60 word atomic answer — direct, definitive.
2. AFTER EVERY H2: Start with direct answer that stands alone.
3. H2 headings phrased as search queries (fan-out aware).

## PAGE STRUCTURE

### HEAD
- All CSS in single <style> block — no inline styles
- <title> under 60 chars + "{SITE['brand']}"
- Meta description under 160 chars
- Canonical, hreflang="{SITE.get('hreflang', 'en')}", OG + Twitter cards
- Google Fonts (font-display: swap)
- JSON-LD: Article + FAQPage + BreadcrumbList + Speakable

### BODY (1,500-2,500 words)
- {LANGUAGE_INSTRUCTION}
- H2/H3 as questions/search queries
- Comparison table where relevant
- Pros/cons or key takeaways
- Internal links woven naturally
- Start every H2 with direct answer

### FAQ (5 questions, self-contained answers)
### RESPONSIBLE GAMBLING ({RG_TEXT} | {RG_HELPLINE})
### FOOTER (brand + disclaimer + 18+)"""


# ─────────────────────────────────────────────
# AUTO-INTERLINKING: Inject backlinks into existing pages
# ─────────────────────────────────────────────

def inject_backlinks(new_article_url: str, new_article_title: str,
                     new_keywords: list, relevant_pages: list) -> dict:
    """For each relevant existing page, inject a contextual link to the new article.
    Returns dict of {path: updated_html} for pages that were modified."""

    updated_pages = {}

    for page in relevant_pages[:5]:  # Limit backlinks to top 5 most relevant pages
        page_path = Path("generated") / page["path"]
        if not page_path.exists():
            print(f"   ⚠️   Skipping backlink for {page['path']} — file not found locally")
            continue

        html = page_path.read_text(encoding="utf-8")

        # Check if this page already links to the new article
        if new_article_url in html:
            print(f"   ⏭️   {page['path']} already links to {new_article_url}")
            continue

        # Find a good insertion point — look for the last </section> before </footer>
        # or the last <p> in a content section
        anchor_text = new_article_title
        link_html = f'<a href="{new_article_url}">{anchor_text}</a>'

        # Strategy: find a relevant paragraph and append a contextual sentence
        # We'll use a simple approach: inject a "Related reading" link before the FAQ
        # or responsible gambling section

        injection_candidates = [
            '<!-- RELATED READING INJECTION POINT -->',  # explicit marker if present
            '<section class="content-section" id="faq"',
            '<section class="content-section" id="responsible-gambling"',
            'id="faq"',
            'class="rg-box"',
        ]

        injected = False
        for marker in injection_candidates:
            if marker in html:
                related_block = f'''<div class="related-reading" style="background:var(--card-bg,{DESIGN['card_bg']});border-left:3px solid var(--gold,{DESIGN['gold']});padding:16px 20px;margin:24px 0;border-radius:4px;">
  <p style="margin:0;color:var(--text,{DESIGN['text']});font-size:14px;"><strong>Related:</strong> {link_html}</p>
</div>
'''
                html = html.replace(marker, related_block + marker, 1)
                injected = True
                break

        if injected:
            page_path.write_text(html, encoding="utf-8")
            updated_pages[page["path"]] = html
            print(f"   🔗  Injected backlink in {page['path']} → {new_article_url}")
        else:
            print(f"   ⚠️   Could not find injection point in {page['path']}")

    return updated_pages


# ─────────────────────────────────────────────
# CLAUDE-POWERED SMART INTERLINKING (for edge cases)
# ─────────────────────────────────────────────

def smart_interlink_check(new_topic: str, new_keywords: list, registry: dict) -> list:
    """Use Claude to find non-obvious relevant pages that keyword matching might miss.
    Only called when keyword matching returns fewer than 3 results."""

    pages_summary = []
    for page in registry["pages"]:
        if page.get("nolink"):
            continue
        pages_summary.append(f"- {page['url']}: {page['title']} (keywords: {', '.join(page.get('keywords', [])[:5])})")

    prompt = f"""I'm writing a new article about: "{new_topic}"
Target keywords: {json.dumps(new_keywords)}

Here are all existing pages on my site:
{chr(10).join(pages_summary)}

Which of these existing pages should my new article link to?
Only include pages that are genuinely relevant — a reader of my article would find them useful.

Return ONLY a JSON array of URL paths, nothing else. Example:
["/guides/best-payid-casinos/", "/reviews/stake96/"]"""

    try:
        result = call_claude(prompt, "smart-interlink-check", max_tokens=500)
        # Parse the JSON array
        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[1]
        if result.endswith("```"):
            result = result.rsplit("```", 1)[0]
        urls = json.loads(result.strip())

        # Convert URLs back to page objects
        url_to_page = {p["url"]: p for p in registry["pages"]}
        return [url_to_page[u] for u in urls if u in url_to_page]
    except Exception as e:
        print(f"   ⚠️   Smart interlink check failed: {e}")
        return []


# ─────────────────────────────────────────────
# SITEMAP UPDATE
# ─────────────────────────────────────────────

def update_sitemap(new_url: str, domain: str) -> str | None:
    """Add new article to sitemap.xml. Returns updated XML or None."""
    sitemap_path = Path("generated/sitemap.xml")
    if not sitemap_path.exists():
        print("   ⚠️   sitemap.xml not found — skipping update")
        return None

    sitemap = sitemap_path.read_text(encoding="utf-8")

    # Check if URL already exists
    full_url = f"{domain}{new_url}"
    if full_url in sitemap:
        print(f"   ⏭️   {new_url} already in sitemap.xml")
        return None

    # Insert before </urlset>
    new_entry = f"""  <url>
    <loc>{full_url}</loc>
    <lastmod>{TODAY}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>

</urlset>"""

    sitemap = sitemap.replace("</urlset>", new_entry)
    sitemap_path.write_text(sitemap, encoding="utf-8")
    print(f"   🗺️   Added {new_url} to sitemap.xml")
    return sitemap


# ─────────────────────────────────────────────
# GITHUB PUSH
# ─────────────────────────────────────────────

def push_files(files: dict) -> None:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("❌  GITHUB_TOKEN not set.")
        sys.exit(1)

    g = Github(token)
    try:
        repo = g.get_repo(GITHUB_REPO)
    except GithubException as e:
        print(f"❌  Cannot access repo: {e}")
        sys.exit(1)

    pushed = 0
    for path, content in files.items():
        try:
            existing = repo.get_contents(path)
            repo.update_file(path=path, message=f"Update {path} — {TODAY}",
                           content=content, sha=existing.sha)
            print(f"   ✅  Updated: {path}")
        except GithubException:
            repo.create_file(path=path, message=f"Add {path} — {TODAY}",
                           content=content)
            print(f"   ✅  Created: {path}")
        pushed += 1
        if pushed < len(files):
            time.sleep(0.5)

    print(f"\n🚀  {pushed} file(s) pushed.")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert topic text to URL-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')[:80]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create new blog article with auto-interlinking")
    parser.add_argument("--topic", type=str, required=True,
                       help='Article topic, e.g. "Best Aristocrat pokies to play in Australia 2026"')
    parser.add_argument("--slug", type=str, default=None,
                       help="URL slug (auto-generated from topic if not provided)")
    parser.add_argument("--keywords", type=str, default=None,
                       help='Comma-separated keywords, e.g. "aristocrat pokies,aristocrat slots online"')
    parser.add_argument("--no-backlinks", action="store_true",
                       help="Skip injecting backlinks into existing pages")
    parser.add_argument("--no-push", action="store_true",
                       help="Generate locally only, don't push to GitHub")
    parser.add_argument("--smart", action="store_true",
                       help="Use Claude to find additional relevant pages for interlinking")
    parser.add_argument("--neuron", action="store_true",
                       help="Fetch NeuronWriter SEO recommendations before generating.\n"
                            "Uses 1 NeuronWriter credit. Adds ~60s but better SEO.")
    parser.add_argument("--geo", action="store_true", default=True,
                       help="Add GEO optimization for AI search visibility (default: on).")
    parser.add_argument("--no-geo", action="store_true",
                       help="Disable GEO optimization (not recommended).")
    parser.add_argument("--no-serp", action="store_true",
                       help="Skip SERP competitor research (faster, lower quality).")
    parser.add_argument("--type", type=str, default="blog",
                       choices=["blog", "review", "guide", "banking"],
                       help="Content type: blog (default), review, guide, or banking.\n"
                            "Each type uses a specialized prompt template with appropriate\n"
                            "structure, schema, and sections.")
    parser.add_argument("--casino-data", type=str, default=None,
                       help="Path to JSON file with casino operator data (for review pages).\n"
                            "Contains: name, bonus, min_deposit, score, score_breakdown, etc.")
    args = parser.parse_args()

    # ── Setup ──
    slug = args.slug or slugify(args.topic)
    article_path = ARTICLE_PATH_TEMPLATE.format(slug=slug)
    article_url = f"/{article_path.replace('.html', '/')}".replace('//', '/')

    # Parse keywords
    if args.keywords:
        keywords = [k.strip() for k in args.keywords.split(",")]
    else:
        # Auto-generate keywords from topic
        keywords = [args.topic.lower()]
        # Add individual significant words
        for word in args.topic.lower().split():
            if len(word) > 4 and word not in ["about", "guide", "australia", "australian", "best", "online"]:
                keywords.append(word)

    content_type = getattr(args, 'type', 'blog')

    print("\n" + "=" * 60)
    print(f"  📝  Content Generator + Auto-Interlinker")
    print(f"  Type     : {content_type}")
    print(f"  Topic    : {args.topic}")
    print(f"  Slug     : {slug}")
    print(f"  Path     : {article_path}")
    print(f"  Keywords : {', '.join(keywords)}")
    print("=" * 60)

    # ── Load registry ──
    registry = load_registry()

    # Check if article already exists
    existing_urls = [p["url"] for p in registry["pages"]]
    if article_url in existing_urls:
        print(f"\n⚠️   Article already exists at {article_url}")
        print(f"    To regenerate, remove it from content-registry.json first.")
        sys.exit(1)

    # ── Find relevant pages for interlinking ──
    print(f"\n🔍  Finding relevant pages for interlinking...")
    relevant_pages = find_relevant_pages(keywords, registry)
    print(f"   Found {len(relevant_pages)} keyword-matched pages")

    # Smart interlink check if not enough matches
    if len(relevant_pages) < 3 or args.smart:
        print(f"   🧠  Running Claude smart interlink check...")
        smart_pages = smart_interlink_check(args.topic, keywords, registry)
        # Merge, dedup
        existing_urls_set = {p["url"] for p in relevant_pages}
        for sp in smart_pages:
            if sp["url"] not in existing_urls_set:
                relevant_pages.append(sp)
                existing_urls_set.add(sp["url"])
        print(f"   Total relevant pages: {len(relevant_pages)}")

    for rp in relevant_pages:
        print(f"   → {rp['url']}: {rp['title']}")

    # ── Fetch NeuronWriter SEO data (if --neuron) ──
    neuron_block = ""
    neuron_query_id = None
    if args.neuron:
        try:
            from neuron_seo import get_neuron_recommendations
            primary_kw = keywords[0] if keywords else args.topic
            neuron_data = get_neuron_recommendations(primary_kw)
            if neuron_data and neuron_data.get("prompt_block"):
                neuron_block = neuron_data["prompt_block"]
                neuron_query_id = neuron_data.get("query_id")
                print(f"   ✅  NeuronWriter: {len(neuron_data.get('content_terms', []))} terms, "
                      f"{neuron_data.get('target_word_count', '?')} target words")
            else:
                print(f"   ⚠️   NeuronWriter failed, generating without SEO data")
        except ImportError:
            print(f"   ❌  neuron_seo.py not found. Generating without NeuronWriter.")
        except Exception as e:
            print(f"   ⚠️   NeuronWriter error: {e}. Generating without SEO data.")

    # ── Build GEO optimization block (AI search citation formatting) ──
    geo_block = ""
    use_geo = args.geo and not args.no_geo
    if use_geo and HAS_GEO:
        primary_kw = keywords[0] if keywords else args.topic
        page_url = f"{SITE['domain']}/blog/{slug}/"
        page_title = f"{args.topic} — {SITE['brand']}"
        geo_block = get_full_geo_block(
            primary_keyword=primary_kw,
            page_url=page_url,
            page_title=page_title,
            page_type="guide"
        )
        print(f"   ✅  GEO: Atomic answers + Speakable schema + AI-citation formatting enabled")
    elif use_geo and not HAS_GEO:
        print(f"   ⚠️   geo_optimize.py not found. GEO instructions are embedded in prompt instead.")
    else:
        print(f"   ⏭️   GEO disabled (--no-geo)")

    # ── Load casino data if provided (for review pages) ──
    casino_data = None
    if args.casino_data:
        try:
            with open(args.casino_data, encoding="utf-8") as f:
                casino_data = json.load(f)
            print(f"   ✅  Casino data loaded: {casino_data.get('name', 'unknown')}")
        except Exception as e:
            print(f"   ⚠️   Casino data failed to load: {e}")

    # ── SERP competitor research (crawl4ai) ──
    competitor_block = ""
    if not getattr(args, 'no_serp', False):
        print(f"\n🔍  Running SERP competitor research...")
        try:
            from serp_research import research_keyword, build_competitor_prompt_block, add_discovered_keywords_to_queue
            primary_kw = keywords[0] if keywords else args.topic
            serp_data = research_keyword(primary_kw)
            competitor_block = build_competitor_prompt_block(serp_data)
            if serp_data["competitor_count"] > 0:
                print(f"   ✅  Analyzed {serp_data['competitor_count']} competitors | "
                      f"avg {serp_data['avg_word_count']:,} words | "
                      f"target {serp_data['target_word_count']:,}+ words")
                # Auto-discover new keywords from competitor content
                added = add_discovered_keywords_to_queue(serp_data)
                if added:
                    print(f"   💡  Added {added} new keyword(s) to content queue")
            else:
                print(f"   ⚠️   No competitor data — generating without SERP intelligence")
        except ImportError:
            print(f"   ⚠️   serp_research.py not found — skipping competitor research")
        except Exception as e:
            print(f"   ⚠️   SERP research error: {e} — continuing without competitor data")

    # ── Generate article ──
    content_type = getattr(args, 'type', 'blog')
    print(f"\n📄  Generating {content_type} article...")
    article_html = generate_article(
        topic=args.topic,
        slug=slug,
        target_keywords=keywords,
        relevant_pages=relevant_pages,
        registry=registry,
        neuron_block=neuron_block,
        geo_block=geo_block,
        content_type=content_type,
        casino_data=casino_data,
        competitor_block=competitor_block,
    )

    # Save locally
    out_path = Path(OUTPUT_DIR) / article_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(article_html, encoding="utf-8")
    print(f"   💾  Saved: {OUTPUT_DIR}/{article_path} ({len(article_html):,} bytes)")

    # ── Inject backlinks into existing pages ──
    updated_pages = {}
    if not args.no_backlinks:
        print(f"\n🔗  Injecting backlinks into existing pages...")
        updated_pages = inject_backlinks(
            new_article_url=article_url,
            new_article_title=args.topic,
            new_keywords=keywords,
            relevant_pages=relevant_pages
        )
        if not updated_pages:
            print("   ℹ️   No backlinks injected (pages not found locally or already linked)")

    # ── Update registry ──
    print(f"\n📋  Updating content registry...")
    new_entry = {
        "path": article_path,
        "url": article_url,
        "title": args.topic,
        "category": content_type,
        "keywords": keywords,
        "anchors": [args.topic, args.topic.split("—")[0].strip() if "—" in args.topic else args.topic]
    }
    registry["pages"].append(new_entry)
    save_registry(registry)

    # ── Update sitemap ──
    print(f"\n🗺️   Updating sitemap...")
    updated_sitemap = update_sitemap(article_url, SITE["domain"])

    # ── Collect all files to push ──
    files_to_push = {article_path: article_html}
    files_to_push["content-registry.json"] = json.dumps(registry, indent=2, ensure_ascii=False)

    for path, html in updated_pages.items():
        files_to_push[path] = html

    if updated_sitemap:
        files_to_push["sitemap.xml"] = updated_sitemap

    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"  ✅  SUMMARY")
    print(f"  Type            : {content_type}")
    print(f"  New page        : {article_path}")
    print(f"  Internal links  : {len(relevant_pages)} pages linked FROM article")
    print(f"  Backlinks added : {len(updated_pages)} existing pages updated")
    print(f"  Files to push   : {len(files_to_push)}")
    print(f"{'='*60}")

    # ── Push ──
    if args.no_push:
        print("\n⏸️   --no-push set. Review generated/ then push manually.")
    else:
        push = input("\nPush all files to GitHub? (y/n): ").strip().lower()
        if push == "y":
            push_files(files_to_push)
        else:
            print("⏸️   Skipped. Review generated/ then re-run to push.")
