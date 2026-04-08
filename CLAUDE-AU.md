# CLAUDE.md — AU Market (casino-au)
# This file extends the Master CLAUDE-SEO-AGENT.md
# All universal rules, tasks, workflows, quality gates, and GEO/fan-out strategy are defined there.
# This file contains ONLY AU market-specific configuration and overrides.

---

## SITE CONFIGURATION

```python
SITE = {
    "brand": "AussiePokies96",
    "domain": "https://ssusa.co",
    "author": "Blake Donovan",
    "author_bio": "Blake has reviewed Australian online casinos since 2019, specialising in payout speed and pokie variety.",
    "year": 2026,
    "twitter": "@AussiePokies96",
    "email": "editor@ssusa.co",
}

GITHUB_REPO = "jjjeremyyy/au-casino-generator"
MODEL = "claude-sonnet-4-6"
```

---

## MARKET IDENTITY

- **Market**: Australia (AU)
- **Language**: Australian English — use "pokies" primarily (70%+), "slots" acceptable for keyword variation. Use "punters" primarily, "players" acceptable for natural flow. Both terms are valid — the preferred terms signal stronger AU localisation. Use "mobile" not "cell phone".
- **Currency**: AUD ($) — always display as "$XX AUD"
- **Regulations**: Strict — Interactive Gambling Act 2001. Only promote operators that accept AU players. No operators licensed solely for restricted jurisdictions. Always include responsible gambling messaging (Gambling Help Online 1800 858 858, gamblinghelponline.org.au)
- **Primary Focus**: PayID casinos — this is the #1 differentiator for AU market
- **Secondary Focus**: Fast payouts, pokies variety, crypto options, no KYC where legal

---

## PAGE OUTPUT STRUCTURE

```
generated/
├── index.html                                → Main landing page (8 casino rankings)
├── about.html                                → About page (E-E-A-T optimized)
├── privacy-policy.html                       → Privacy policy
├── terms-conditions.html                     → Terms & conditions
├── sitemap.xml                               → Auto-generated sitemap
├── robots.txt                                → Crawl directives
├── reviews/
│   ├── stake96.html                          → Stake96 Casino review
│   ├── spin2u.html                           → Spin2U Casino review
│   ├── spinza96.html                         → Spinza96 Casino review
│   ├── stakebro77.html                       → StakeBro77 Casino review
│   ├── sage96.html                           → Sage96 Casino review
│   ├── shuffle96.html                        → Shuffle96 Casino review
│   ├── wowza96.html                          → Wowza96 Casino review
│   └── pokiespin96.html                      → PokieSpin96 Casino review
├── guides/
│   ├── best-payid-casinos.html               → Best PayID Casinos AU (pillar page)
│   ├── best-crypto-casinos.html              → Best Crypto Casinos AU
│   ├── best-pokies-australia.html            → Best Pokies AU
│   ├── best-online-pokies-australia.html     → Best Online Pokies AU
│   ├── best-e-wallet-pokies-australia.html   → Best E-Wallet Pokies AU
│   ├── fast-payout-casinos.html              → Fast Payout Casinos AU
│   ├── no-deposit-bonus.html                 → No Deposit Bonus Guide
│   ├── how-to-play-pokies.html               → How to Play Pokies
│   ├── how-to-play-aristocrat-pokies.html    → Aristocrat Pokies Guide
│   ├── how-to-play-jili-pokies.html          → JILI Pokies Guide
│   └── how-to-play-booongo-pokies.html       → Booongo Pokies Guide
└── banking/
    ├── payid-casino-deposits.html            → PayID Deposits Guide
    ├── crypto-casino-deposits.html           → Crypto Deposits Guide
    └── ewallet-casino-deposits.html          → E-Wallet Deposits Guide
```

Generate all AU pages to: `generated/[path].html`
Cloudflare Pages project: `au-casino` (auto-deploys from main branch)

---

## DESIGN TOKENS (AU Theme)

```python
DESIGN = {
    "bg": "#09090f",           # Deep dark background
    "card_bg": "#111520",      # Card background
    "border": "#1d2235",       # Border color
    "gold": "#f8bc2e",         # Primary accent gold
    "green": "#00d97e",        # CTA green (vivid — higher CTR than muted green)
    "red": "#ff4757",          # HOT / urgency badges
    "text": "#edf0f7",         # Primary text
    "muted": "#7a85a0",        # Muted text
    "font_head": "Barlow Condensed",  # Headings (700/800 weight)
    "font_body": "Inter",             # Body (400/500/600 weight)
}
```

---

## AU KEYWORD STRATEGY (from keywords-au.json — 35 keywords)

### Primary Keywords (7 — Transactional)
| Keyword | Competition | Notes |
|---------|-------------|-------|
| online casino Australia | Very High | Broadest commercial term. Build toward, not a quick win. |
| online pokies | Very High | Australian-English for slots. ~40k-60k searches/mo. Use "pokies" over "slots" everywhere. |
| real money casino | High | Signals deposit intent. Pair with AU modifier. |
| PayID casino | Medium | 100% AU-specific. Growing fast 2025-2026. Lower KD — key differentiator. |
| casino bonuses Australia | High | Top-of-funnel for bonus-hunters — major AU segment. |
| crypto casino Australia | Medium-High | Surging demand due to IGA restrictions. BTC, ETH, SOL all relevant. |
| payid casino australia | Medium | Lowercase variant — captures organic search behaviour. Target both forms. |

### Long-Tail Keywords (21 — Transactional, lower competition)
| Keyword | Competition | Notes |
|---------|-------------|-------|
| best online casino Australia real money | Medium-High | Core money keyword. Lower KD than head term. Must-have primary page target. |
| PayID casino instant withdrawal Australia | Medium | Combines PayID + fast payout — #1 player priority in 2026. |
| no deposit bonus casino Australia | Medium | Perennially high-intent. Players want to try before depositing. |
| AUD online casino no wagering requirements | Low-Medium | Hot search topic. High conversion. |
| best crypto casino Australia no KYC | Low-Medium | Privacy-focused. Strong niche with growing demand. |
| fast payout casino Australia instant withdrawal | Medium | #1 player priority. High buyer intent. |
| $5 minimum deposit casino Australia | Low-Medium | Targets casual punters. Build cluster: $5, $10, $20 variants. |
| e wallet australia casino | Low-Medium | Captures e-wallet deposit seekers. PayID, POLi, Skrill all qualify. |
| e wallet pokies australia | Low | Pokies-specific e-wallet intent. Internal link target. |
| e-wallet australia pokies | Low | Hyphenated variant — target both forms. |
| e wallet online pokies | Low | Broader variant without AU geo-modifier. Good for body copy. |
| e wallet casino login australia | Low | Login = returning user or mid-decision. How-to guide target. |
| payid casino no deposit bonus | Low-Medium | AU payment + no deposit. Very targeted, strong conversion. |
| best online pokies australia payid | Low-Medium | Natural pillar page target linking to reviews. |
| no deposit payid casino australia | Low-Medium | Word order variant. Google treats these as related but distinct. |
| online slots australia real money | Medium | "Slots" captures international Aussies. Secondary to pokies variants. |
| payid pokies sign up bonus | Low | Sign-up intent + PayID + pokies. Very high conversion. |
| payid pokies no deposit australia | Low | No-risk pokies play. Excellent landing page target. |
| best online pokies australia payid real money | Low | Highly specific. Very low competition, very high buyer intent. |
| instant payid pokies australia | Low | Speed + PayID + pokies. Exact player looking for same-session play. |
| fast payout online pokies australia | Low-Medium | Slightly broader than "instant". Good for comparison page. |

### Informational Keywords (7)
| Keyword | Competition | Notes |
|---------|-------------|-------|
| is online gambling legal in Australia | Low-Medium | Most-searched legal question. IGA creates genuine confusion. Builds trust. |
| how to deposit with PayID at online casino | Low | Procedural how-to. Mid-funnel — close to transacting. |
| are pokies winnings taxed in Australia | Low | Answer: No (recreational). Low competition, builds authority. |
| how do wagering requirements work | Low-Medium | Educates bonus-hunters. Supports bonus pages. |
| best online pokies for real money Australia | Medium | Bottom-of-funnel research. One step from transacting. |
| [casino name] review Australia | Low | Branded review intent. Very high conversion — one click from affiliate link. |
| Solana casino Australia | Low | SOL = rising crypto withdrawal method 2026. Early-mover opportunity. |

### Strategic Notes & Language Rules
- Use **"pokies"** primarily (70%+), "slots" acceptable for keyword variation and capturing international search terms — Google is geo-aware, AU punters respond to local language
- Use **"punters"** primarily, "players" acceptable for natural flow — both are valid AU English
- Use **"fast payouts"** primarily over "quick withdrawals"
- **PayID** is your payment differentiator — no other English-speaking market has it. Build dedicated hub pages
- The **IGA targets operators, not players** — Australians are legally free to use offshore sites. Clarify this on every informational page
- **Crypto + no-KYC** is the fastest-growing niche due to IGA-driven demand for offshore alternatives
- **Solana (SOL)** is a rising AU withdrawal method — mention alongside BTC/ETH where relevant
- Use a **hub-and-spoke content architecture**: national hubs ("Best PayID Casinos Australia") with spokes to game-type pages, city pages, and individual reviews
- Each review page must target **"[CasinoName] review Australia"** in `<title>`, H1, and meta description

---

## AU FAN-OUT MAP — "best PayID casino Australia"

When creating content for the head term, ensure these sub-queries are all answered:
1. "PayID casino instant deposit Australia" → section or cluster page
2. "fastest payout online casino AU 2026" → section or cluster page
3. "PayID vs crypto casino deposits Australia" → dedicated comparison page
4. "are PayID casinos safe and licensed" → trust/legal section
5. "PayID casino minimum deposit amount" → banking guide section
6. "best PayID casino bonuses Australia 2026" → bonus comparison page
7. "how to deposit with PayID at online casino" → step-by-step guide
8. "PayID casino withdrawal speed comparison" → comparison table + data

---

## AU OPERATOR DATABASE

### Primary Operators (from generate_au.py — 8 casinos)

| Rank | Operator | Slug | Bonus | Wagering | Min Deposit | Score | Tags |
|------|----------|------|-------|----------|-------------|-------|------|
| 1 | Stake96 Casino | stake96 | Up to $10,000 + 600 Free Spins | 35x | $20 | 9.9 | 10,000+ Pokies, Fast PayID, Live Dealer |
| 2 | Spin2U Casino | spin2u | Up to $20,000 + 500 Free Spins | 38x | $25 | 9.8 | High Roller, Wide Selection |
| 3 | Spinza96 Casino | spinza96 | $3,000 + 200 Free Spins — No KYC | 30x | $10 | 9.8 | No KYC, Low Min Deposit |
| 4 | StakeBro77 Casino | stakebro77 | Up to $7,500 + 350 Free Spins | 35x | $20 | 9.7 | Balanced Offering |
| 5 | Sage96 Casino | sage96 | Up to $5,000 + 300 Free Spins | 35x | $20 | 9.6 | Solid All-Rounder |
| 6 | Shuffle96 Casino | shuffle96 | 250% up to $6,000 + 400 Free Spins | 40x | $20 | 9.5 | High Match %, Many Spins |
| 7 | Wowza96 Casino | wowza96 | Up to $8,000 + 450 Free Spins | 40x | $25 | 9.3 | Big Bonus Package |
| 8 | PokieSpin96 Casino | pokiespin96 | 200% up to $15,000 + 50 Super Spins | 45x | $10 | 9.1 | Huge Bonus, Low Entry |

### Additional Operators (from grok-au1 — 10 casinos, separate site variant)

| Operator | Review File |
|----------|------------|
| Betworld Casino | betworld-casino-review.html |
| Crown Casino | crown-casino-review.html |
| Galaxy Casino | galaxy-casino-review.html |
| Gwin77 Casino | gwin77-casino-review.html |
| HB88 Casino | hb88-casino-review.html |
| MGM7 Casino | mgm7-casino-review.html |
| SpeedAU Casino | speedau-casino-review.html |
| Spinza96 Casino | spinza96-casino-review.html |
| WinShark Casino | winshark-casino-review.html |
| Wowza96 Casino | wowza96-casino-review.html |

*Note: Spinza96 and Wowza96 appear in both sets. grok-au1 is a second site variant with different operators — ensure no content duplication across sites.*

---

## AU CONTENT INVENTORY (Current State)

**~25 pages live** as of April 2026:
- Homepage: 1 (index.html — 92KB, approaching 100KB limit)
- Casino Reviews: 8 (Stake96, Spin2U, Spinza96, StakeBro77, Sage96, Shuffle96, Wowza96, PokieSpin96)
- Guides: 11 (PayID casinos, crypto casinos, pokies, fast payout, no deposit, e-wallet, how-to-play, Aristocrat, JILI, Booongo, best online pokies)
- Banking: 3 (PayID deposits, crypto deposits, e-wallet deposits)
- Legal: 3 (about, privacy policy, terms & conditions)

**Content Queue**: Not yet set up — needs `content-queue.json` and `scheduler.py` (adapt from PG market)

**Content Expansion Needed** (PG has these, AU doesn't yet):
- `add_content.py` — Content creator + auto-interlinking (use shared version with config.json)
- `cluster_planner.py` — Topical cluster builder (adapt from PG)
- `gap_analysis.py` — NeuronWriter + GSC gap analysis (adapt from PG)
- `scheduler.py` — Auto-publisher from content queue (adapt from PG)
- `freshness_updater.py` — Content freshness auto-updater (adapt from PG)
- `validate_schema.py` — JSON-LD schema validator (adapt from PG)
- `content-registry.json` — Page inventory for interlinking (needs creating)
- `content-queue.json` — Publishing queue (needs creating)
- `magnet-templates.json` — Link magnet templates (adapt from PG)
- `google_apps_script.js` — Google Sheet auto-deploy (adapt from PG)

---

## AU CONTENT TEMPLATES

### Review Page Title Pattern
```
[Casino Name] Review Australia 2026 — [Key USP]
```
Examples (from actual operators):
- "Stake96 Casino Review Australia 2026 — 10,000+ Pokies & Fast PayID Payouts"
- "Spinza96 Casino Review Australia 2026 — No KYC PayID Casino with $3,000 Bonus"
- "Spin2U Casino Review Australia 2026 — $20,000 Welcome Bonus & 500 Free Spins"

### Meta Description Pattern
```
[Casino Name] review for Australian punters in 2026. [Bonus detail]. [PayID/payout detail]. [Pokies count]. Read our expert review →
```
Examples:
- "Stake96 Casino offers Australian punters up to $10,000 + 600 free spins in 2026. PayID payouts in under 5 minutes. 10,000+ pokies. Read our expert review →"

### H1 Pattern
Same as title tag — keyword front-loaded, includes "Australia" and year.

### Score Breakdown Pattern (from generate_au.py)
Each review includes a detailed score breakdown:
```
Pokies Library: X.X / 10
Payout Speed: X.X / 10
Bonus Value: X.X / 10
Mobile Experience: X.X / 10
Support: X.X / 10
Overall: X.X / 10
```

### Pros/Cons Pattern
Every review includes pros and cons. Example (Stake96):
- ✅ 10,000+ pokies from top AU providers
- ✅ PayID payouts processed in under 5 minutes
- ✅ 24/7 live dealer tables including AU-friendly hours
- ✅ 5-deposit welcome structure — sustained bankroll boost
- ❌ No dedicated iOS/Android app
- ❌ 35x wagering requirement on bonus funds

---

## AU WEB DESIGN GUIDELINES

### Design Philosophy
Australian players expect **clean, trust-forward, Western-style layouts**. They're accustomed to professional comparison sites (similar to Finder, Canstar). Design should feel authoritative and transparent — not flashy or cluttered.

### Layout Principles
- **Desktop**: Wide comparison tables, side-by-side operator cards, clear hierarchy. Horizontal navigation. White space matters — don't over-crowd.
- **Mobile**: Responsive, thumb-friendly. Sticky CTA bar at bottom. Collapsible comparison tables. Cards stack vertically. Mobile is ~65% of AU gambling traffic.
- **Hero section**: Lead with the value proposition — "Best PayID Casinos Australia 2026" with a clear subheading explaining what the page delivers. No animated sliders — they hurt CWV.

### Trust Signals (Critical for AU)
- PayID badge/icon prominent near top of every review
- "Last updated: [date]" visible in hero area
- Author photo + bio with credentials
- Affiliate disclosure above the fold (non-negotiable for AU compliance)
- Responsible gambling logo/link visible without scrolling
- Star ratings with clear methodology explanation
- License/jurisdiction badges per operator

### Color & Typography
- Dark theme (dark navy/charcoal backgrounds) with gold accents — premium casino feel
- High contrast text (white/light grey on dark) — WCAG AA compliant
- Green CTAs (#00d97e) — tested higher CTR than muted greens in iGaming
- Use system fonts or lightweight web fonts (Inter, Barlow Condensed) — no heavy font loads
- Font sizes: body 14-16px on desktop, 12-14px on mobile. Never below 12px.

### Comparison Tables (AU Must-Have)
Australian users expect detailed comparison tables. Every list/review page needs one:
```
Columns: Casino Name | PayID | Min Deposit | Bonus | Withdrawal Speed | Pokies Count | Rating | CTA
```
- Sortable if possible (CSS-only, no JS frameworks)
- Mobile: horizontal scroll or card-based layout
- Highlight "Editor's Pick" or "Best PayID" with gold accent border
- Include real data — never placeholder values

### CTA Design
- Primary CTA: High-contrast green button (#00d97e) with white text
- Text: Action-oriented — "Visit Casino →", "Claim Bonus →", "Play Now →"
- Placement: After each review card, in comparison table rows, sticky bottom bar on mobile
- Never use misleading CTA text ("Guaranteed Win", "Free Money")

### Page Speed Requirements
- Total HTML page weight: <100KB (inline CSS, no external stylesheets)
- No heavy JavaScript frameworks — vanilla JS only where needed
- Images: WebP format, lazy loading, explicit width/height
- Fonts: preload primary font, use font-display: swap
- Target: LCP ≤2.5s, CLS ≤0.1, INP ≤200ms

---

## AU-SPECIFIC SCHEMA

Every AU page should include these additional schema properties:
```json
{
  "@type": "Organization",
  "areaServed": {
    "@type": "Country",
    "name": "Australia"
  },
  "availableLanguage": "English"
}
```

---

## AU COMPLIANCE RULES (Non-Negotiable)

- Every review/list page must include responsible gambling section with:
  - Gambling Help Online: 1800 858 858
  - Website: gamblinghelponline.org.au
  - Self-exclusion information
  - "Gamble responsibly" messaging
- Affiliate disclosure must appear above the fold, before any CTA
- Never guarantee winnings or imply gambling is a reliable income source
- All bonus claims must include full T&Cs (wagering, max cashout, expiry, eligible games)
- Do not promote operators explicitly banned under Australian law
- Age verification messaging: "18+ only. Gambling can be addictive."

---

## AU NeuronWriter SETTINGS

```
Engine: google.com.au
Language: English
```

---

## AU llms.txt

```
# llms.txt for ssusa.co

name: AussiePokies96
description: Expert reviews of PayID casinos and online pokies for Australian players
topics: PayID casinos, online pokies, casino reviews, bonus comparisons, payout speeds, crypto casinos, e-wallet pokies, no deposit bonuses
authority: Independent iGaming review site specialising in Australian online casinos since 2019
author: Blake Donovan
update_frequency: weekly
language: en-AU
geo_target: Australia
contact: editor@ssusa.co
```

---

## AU SCRIPTS REFERENCE

| Script | Description | Usage |
|--------|-------------|-------|
| `generate_au.py` | **MAIN GENERATOR**: Creates index.html + 8 review pages via Claude API, pushes to GitHub. Contains SITE config, DESIGN tokens, casino data, keyword loading, cost tracking. 184KB — the core engine. | `python3 generate_au.py` |
| `generate_remaining.py` | Generates all non-index, non-review pages (about, privacy, terms, 11 guides, 3 banking pages). Imports everything from generate_au.py. | `python3 generate_remaining.py` |
| `generate_about.py` | Standalone About page generator using Claude Opus 4.6 for E-E-A-T optimization. | `python3 generate_about.py` |
| `patches_for_generate_au.py` | 6 bolt-on improvements: retry logic (3x exponential backoff), `--only` flag, IndexNow ping, dynamic dates, cost tracking, deploy.yml. | Apply patches per instructions in file |
| `keywords-au.json` | Full AU keyword database (35 keywords) with intent, competition, and strategic notes. Loaded by generate_au.py at runtime. | Referenced by all generators |

### Available CLI Flags (from patches)
```bash
python3 generate_au.py                        # Generate all pages
python3 generate_au.py --only=reviews/stake96.html  # Generate single page
python3 generate_au.py --list                  # List all available pages
python3 generate_au.py --no-push               # Generate locally, don't push to GitHub
```

### Guide/Banking Pages Generated by generate_remaining.py
```
guides/best-payid-casinos.html              → PayID Casinos pillar page
guides/best-crypto-casinos.html             → Crypto Casinos guide
guides/best-pokies-australia.html           → Best Pokies guide
guides/best-online-pokies-australia.html    → Online Pokies guide
guides/best-e-wallet-pokies-australia.html  → E-Wallet Pokies guide
guides/fast-payout-casinos.html             → Fast Payout guide
guides/no-deposit-bonus.html                → No Deposit Bonus guide
guides/how-to-play-pokies.html              → How to Play Pokies
guides/how-to-play-aristocrat-pokies.html   → Aristocrat Pokies provider guide
guides/how-to-play-jili-pokies.html         → JILI Pokies provider guide
guides/how-to-play-booongo-pokies.html      → Booongo Pokies provider guide
banking/payid-casino-deposits.html          → PayID banking guide
banking/crypto-casino-deposits.html         → Crypto banking guide
banking/ewallet-casino-deposits.html        → E-Wallet banking guide
```

### IndexNow Integration (from patches)
After pushing to GitHub, auto-ping search engines for faster indexing:
```python
# Set environment variable:
export INDEXNOW_KEY="your-indexnow-key"
# Automatically pings after push — no manual action needed
```

### Cost Tracking
generate_au.py tracks API usage per run:
- Model: claude-sonnet-4-6 ($3/$15 per million tokens)
- Tracks: input tokens, output tokens, API calls, total USD cost
- Prints summary after each run

---

## AU-SPECIFIC TASK OVERRIDES

### Content Creation
- Use `generate_au.py` for full site regeneration (index + 8 reviews)
- Use `generate_remaining.py` for guides, banking, and legal pages
- Use `generate_about.py` for Opus-quality About page (E-E-A-T critical)
- Use `add_content.py` for new articles — loads config.json automatically, includes GEO optimization
- `geo_optimize.py` is integrated into `add_content.py` — atomic answers, Speakable schema, and AI-citation formatting are applied automatically
- Run `content_post_processor.py generated/ --market=au --fix` before every push
- All content must pass NeuronWriter scoring on `google.com.au` engine
- Internal links should reference AU pillar pages: best-payid-casinos.html, best-pokies-australia.html, payid-casino-deposits.html

### Content Expansion (Next Steps)
AU site currently lacks these scripts that PG market has — consider building:
- `add_content.py` — Content creator + auto-interlinking engine (exists in PG, adapt for AU)
- `cluster_planner.py` — Topical cluster builder (exists in PG, adapt for AU)
- `gap_analysis.py` — Content gap analysis with NeuronWriter + GSC (exists in PG, adapt for AU)
- `scheduler.py` — Auto-publisher from content queue (exists in PG, adapt for AU)
- `freshness_updater.py` — Content freshness auto-updater (exists in PG, adapt for AU)
- `validate_schema.py` — JSON-LD schema validator (exists in PG, adapt for AU)
- `content-registry.json` — Single source of truth for interlinking (needs creating for AU)
- `content-queue.json` — Publishing queue (needs creating for AU)

### Competitor Research
- Key AU competitors to monitor: [add competitor domains here]
- Focus analysis on: PayID positioning, pokies coverage depth, operator count, e-wallet coverage, crypto coverage
- Use Crawl4AI to scrape competitor sites (master CLAUDE.md has full workflow)

### Deployment
- GitHub repo: `jjjeremyyy/au-casino-generator`
- Cloudflare Pages project: `au-casino`
- Deploy: auto on push to main via `.github/workflows/deploy.yml` (Wrangler)
- Commit message format: `feat(au): add [category]/[slug]` or `update(au): refresh [slug]`
- IndexNow: auto-pings after push (requires `INDEXNOW_KEY` env var)
- Sitemap: auto-generated at `generated/sitemap.xml`, submitted to https://ssusa.co/sitemap.xml
- Robots.txt: Allow /, Disallow /.tmp/ /data/ /generated/
