#!/usr/bin/env python3
"""
Standalone about.html generator for AussiePokies96.
Generates a Google E-E-A-T–optimised About page via Claude Opus 4.6.

Usage:
    export ANTHROPIC_API_KEY='sk-ant-...'
    python3 generate_about.py
"""

import sys
import os
import json
import pathlib
import anthropic

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from generate_au import SITE, DESIGN, KEYWORDS, casinos

MODEL = "claude-opus-4-6"


def build_eeat_about_prompt(site, casinos, design, keywords):
    primary_kws = ", ".join(f'"{k}"' for k in keywords["primary"])
    kw_rules    = "\n".join(f"- {r}" for r in keywords["rules"])
    top5 = json.dumps(
        [{"name": c["name"], "rank": c["rank"], "score": c["score"], "review_url": c["review_url"]}
         for c in casinos[:5]], indent=2
    )

    return f"""Generate a complete, production-ready HTML About page for {site['brand']}, an Australian online casino affiliate site.

## SITE INFO
- Brand: {site['brand']}
- Domain: {site['domain']}
- Author: {site['author']}
- Author bio: {site['author_bio']}
- Year: {site['year']}
- Canonical URL: {site['domain']}/about/
- Contact email: {site['email']}
- Twitter: {site['twitter']}

## DESIGN TOKENS (match all other pages exactly)
- Body bg: {design['bg']}, Card bg: {design['card_bg']}, Border: {design['border']}
- Gold: {design['gold']}, CTA green: {design['green']}, Red: {design['red']}, Text: {design['text']}, Muted: {design['muted']}
- Fonts: {design['font_head']} (700/800) + {design['font_body']} (400/500/600) via Google Fonts

## TARGET KEYWORD
Primary: "about best payid online casino in australia 2026"
Supporting: {primary_kws}
Content rules:
{kw_rules}

## E-E-A-T REQUIREMENTS (Google's Experience, Expertise, Authoritativeness, Trustworthiness)
This page is critical for Google E-E-A-T signals. Every section must demonstrate:
- EXPERIENCE: Real first-hand testing of casinos (deposits, withdrawals, support tests)
- EXPERTISE: Deep knowledge of AU gambling law, PayID banking, pokies RTP, bonus maths
- AUTHORITATIVENESS: Named author with credentials, years active, specific claims (e.g. "80+ casinos tested")
- TRUSTWORTHINESS: Clear affiliate disclosure, no fake claims, responsible gambling commitment

## REQUIRED PAGE STRUCTURE

### 1. HEAD
- charset UTF-8, viewport
- <title>: About {site['brand']} — {site['author']}, Best PayID Online Casino Australia {site['year']}
- <meta description>: under 160 chars — include author name, years reviewing, AU pokies, PayID expertise
- Canonical: {site['domain']}/about/
- OG meta (type=profile), Twitter card, hreflang en-AU
- Google Fonts preconnect + link
- JSON-LD: Person schema for {site['author']}:
  {{
    "@type": "Person",
    "name": "{site['author']}",
    "jobTitle": "Online Casino Reviewer & Editor",
    "url": "{site['domain']}/about/",
    "sameAs": ["https://twitter.com/AussiePokies96"],
    "knowsAbout": ["online casinos", "PayID banking", "Australian online pokies", "Australian gambling law", "casino bonus analysis", "crypto casinos"],
    "description": "Blake Donovan has reviewed Australian online casinos since 2019, specialising in PayID payout speed, pokie variety and bonus fairness."
  }}
- JSON-LD: Organization schema for {site['brand']}:
  {{
    "@type": "Organization",
    "name": "{site['brand']}",
    "url": "{site['domain']}",
    "logo": "{site['domain']}/logo.png",
    "founder": {{{{ "@type": "Person", "name": "{site['author']}" }}}},
    "description": "Independent Australian online casino review site — {site['year']}"
  }}
- All CSS in <style>

### 2. STICKY NAV (same as all pages)
- Brand "{site['brand']}" in gold linking to {site['domain']}/
- Nav links: Home | Reviews | Guides | About (active state)
- "18+" badge

### 3. HERO
- Breadcrumb: Home › About
- H1: "About {site['brand']}" — include target keyword naturally in subheading
- Subtext: "Independent AU Casino Reviews Since 2019 — Written by a Real Punter Who Tests Every Site"

### 4. AUTHOR PROFILE CARD (large, prominent — critical for E-E-A-T)
Full-width card with:
- Author name: "{site['author']}" (large heading)
- Title: "Senior Casino Reviewer & Editor, {site['brand']} — Since 2019"
- Verified credentials row (icon badges): ✓ 7 Years Reviewing AU Casinos · ✓ 80+ Offshore Casinos Tested · ✓ Real Money Depositor · ✓ PayID Payout Expert
- Full author bio (4–5 sentences): Blake started reviewing Australian online casinos in 2019 when the offshore market was taking off. He has personally deposited real money at 80+ offshore casinos licensed in Curaçao, Malta and Kahnawake. His focus areas are PayID payout speed (he times every withdrawal from request to bank receipt), pokie library depth, and bonus fairness (wagering calculators). He does not accept payment for positive reviews — all rankings are determined solely by testing scores. Based in Sydney, he writes exclusively for the Australian punter market.
- Expertise pills (styled tags): PayID Banking · Pokies RTP Analysis · Bonus T&C Review · Crypto Casinos · AU Gambling Law (IGA) · Live Dealer Games · Responsible Gambling
- Contact: Twitter {site['twitter']} | Email: {site['email']}

### 5. TESTING METHODOLOGY (H2)
"Our {site['year']} Casino Testing Methodology"
Show 6 criteria as numbered cards with icon + heading + 2-3 sentence explanation:

1. **PayID Payout Speed** — We deposit via PayID, play through 1x wagering, then request a withdrawal and time it from submission to funds arriving in a real Australian bank account. Anything over 10 minutes scores below 9.0. Verified using NAB and CBA accounts.

2. **Pokies Library Depth** — We count total titles, check for top providers (Pragmatic Play, Hacksaw, Play'n GO, Evolution, JILI), test load speed on mobile, and verify RTP labels are displayed. A library under 2,000 titles scores below 8.5.

3. **Bonus Fairness Analysis** — We read every T&C line: wagering requirement, max bet during wagering, eligible games %, max cashout cap, time limit, and country restrictions. A bonus with >40x wagering or hidden game exclusions scores below 8.0 for bonus value.

4. **Support Quality** — We contact live chat with a complex PayID question and measure response time and accuracy. We test at peak AU times (7pm–10pm AEDT). Response over 5 minutes or inaccurate answer results in below-8.0 support score.

5. **Licensing & Security** — We verify the offshore licence (Curaçao eGaming, Malta MGA, or equivalent) independently at the licensing authority website, check SSL certificate, and test responsible gambling tools (deposit limits, self-exclusion).

6. **Mobile Experience** — We test every casino on iOS Safari and Android Chrome. Criteria: pokies load without lag, lobby navigation is clean, deposits work end-to-end on mobile, withdrawal requests accessible.

### 6. TESTING PROCESS — HOW A REVIEW IS BUILT (H2)
"How We Build a Casino Review: Step by Step"
Visual step timeline (6 steps as numbered cards):

Step 1: **Initial Research** — Check licence, ownership, launch date, any red flags (player complaints, slow pay reports). If licence is invalid or too many complaints, we stop here.

Step 2: **Account Registration** — Create a real account using Australian details. Test: how long does KYC take? Do they ask for ID upfront or only at withdrawal?

Step 3: **First Deposit & Bonus Claim** — Deposit via PayID (or crypto if no PayID). Claim welcome bonus. Read all bonus T&Cs before depositing. Document exact bonus amount, wagering, max bet, eligible games, time limit.

Step 4: **Pokies Testing** — Play 20+ titles across different providers. Note load speed, RTP display, bet range, mobile performance. Check for certified RNG seals.

Step 5: **Withdrawal Test** — Request a PayID withdrawal. Time it precisely. Check if ID verification is required. Document any fees.

Step 6: **Score & Publish** — Weight 5 criteria (Pokies Library 25%, Payout Speed 25%, Bonus Value 20%, Mobile 15%, Support 15%) to produce the final score. Review is published with the date of testing. We re-test all reviews every 6 months.

### 7. OUR TOP CASINO PICKS (H2)
"Our Current Top 5 Rated AU Casinos"
Show the following 5 casinos as compact review cards in a 3-col grid (desktop), 2-col (tablet), 1-col (mobile). Each card: rank badge (gold), name, score /10, "Read Full Review →" button (links to review_url):
{top5}

### 8. AFFILIATE DISCLOSURE (prominent box)
.disclosure-box with gold left-border:
Heading: "Affiliate Disclosure & Editorial Independence"
Text: "{site['brand']} earns a commission when you sign up at casinos via our links. This fee is paid by the casino — it never affects our review scores, rankings, or editorial content. All scores are determined solely by our testing process, which is applied identically to every casino. We do not accept payment for positive reviews, guaranteed rankings, or promotional mentions. If a casino doesn't meet our testing standards, it will not appear on {site['brand']} regardless of commercial interest."

### 9. OUR COMMITMENT TO RESPONSIBLE GAMBLING (H2)
{site['brand']} promotes responsible gambling. We display 18+ warnings on every page, link to free help services, and never glamourise or exaggerate gambling outcomes. Help resources:
- Gambling Help Online: gamblinghelponline.org.au
- National Helpline: 1800 858 858 (free, 24/7)
- Lifeline: 13 11 14

### 10. CONTACT (H2)
Card: "Get in Touch" — email {site['email']} | Twitter {site['twitter']}. For editorial questions, PR, or affiliate programme details.

### 11. FOOTER
- Brand "{site['brand']}" + affiliate disclaimer
- Footer nav: Home | Reviews | Guides | About | Privacy Policy ({site['domain']}/privacy-policy/) | Terms & Conditions ({site['domain']}/terms-conditions/)
- 18+ responsible gambling disclaimer with 1800 858 858
- © {site['year']} {site['brand']}

## TECHNICAL REQUIREMENTS
- Single self-contained HTML — ALL CSS in <style>, zero external CSS files
- Mobile responsive — nav collapses on mobile, cards stack to 1-col
- Google Fonts (Barlow Condensed + Inter) only external dependency
- No JavaScript required

Return ONLY raw HTML. Start with <!DOCTYPE html>. No markdown. No explanation. Do not truncate."""


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌  ANTHROPIC_API_KEY not set. Run: export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)

    print(f"🤖  Generating about.html via Claude {MODEL}...")
    client = anthropic.Anthropic(api_key=api_key)

    prompt = build_eeat_about_prompt(SITE, casinos, DESIGN, KEYWORDS)
    print(f"   Prompt: {len(prompt):,} chars | Model: {MODEL} | Max tokens: 14,000")

    html_parts = []
    with client.messages.stream(
        model=MODEL,
        max_tokens=14000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}]
    ) as stream:
        for event in stream:
            if event.type == "content_block_delta":
                if event.delta.type == "text_delta":
                    html_parts.append(event.delta.text)

    html = "".join(html_parts).strip()

    # Strip markdown fences if Claude wraps them
    if html.startswith("```"):
        html = html.split("\n", 1)[1]
    if html.endswith("```"):
        html = html.rsplit("```", 1)[0]
    html = html.strip()

    if not html.startswith("<!DOCTYPE") and not html.startswith("<html"):
        print("⚠️  Warning: output may not be valid HTML")
    else:
        print(f"✅  Generated {len(html):,} bytes of valid HTML")

    root = pathlib.Path(__file__).parent

    # Save to project root
    out = root / "about.html"
    out.write_text(html, encoding="utf-8")
    print(f"💾  Saved: {out}")

    # Also save to generated/
    gen = root / "generated" / "about.html"
    gen.parent.mkdir(parents=True, exist_ok=True)
    gen.write_text(html, encoding="utf-8")
    print(f"💾  Saved: {gen}")

    print("\n✅  Done. Open about.html in your browser to preview.")


if __name__ == "__main__":
    main()
