#!/usr/bin/env python3
"""
One-shot compliance fixer for generated HTML pages.
Injects:
  1. Affiliate disclosure banner (above the fold, after <body>)
  2. Responsible gambling strip (before </body>)
  3. WebPage JSON-LD schema for privacy-policy and terms-conditions
Also fixes wowza96's broken JSON-LD schema block.
"""

import re
import json
from pathlib import Path

GENERATED = Path(__file__).parent / "generated"

AFFILIATE_BANNER = '''\n<!-- AFFILIATE DISCLOSURE -->\n<div style="background:rgba(248,188,46,.07);border-bottom:1px solid rgba(248,188,46,.18);padding:.55rem 1rem;font-size:.78rem;color:#7a85a0;text-align:center;" role="note">\n  <strong style="color:#f8bc2e;">Affiliate Disclosure</strong> — AussiePokies96 earns commission when you sign up via links on this page. We only list casinos we have personally tested. T&amp;Cs apply. 18+ only.\n</div>\n'''

RG_STRIP = '''\n<!-- RESPONSIBLE GAMBLING -->\n<div class="rg-strip" role="complementary" aria-label="Responsible gambling" style="margin:2rem 1rem 0;">\n  <strong style="color:var(--red);">18+ only.</strong> Gambling should be for entertainment, not a way to make money. If gambling is affecting you or someone you know, free confidential help is available 24/7: <strong>1800 858 858</strong> &middot; <a href="https://www.gamblinghelponline.org.au/" target="_blank" rel="noopener">gamblinghelponline.org.au</a> &middot; <strong>Lifeline 13 11 14</strong>\n</div>\n'''

# Pages that need compliance injection
COMPLIANCE_PAGES = [
    "banking/crypto-casino-deposits.html",
    "banking/ewallet-casino-deposits.html",
    "banking/payid-casino-deposits.html",
    "guides/best-crypto-casinos.html",
    "guides/best-e-wallet-pokies-australia.html",
    "guides/best-online-pokies-australia.html",
    "guides/best-payid-casinos.html",
    "guides/best-pokies-australia.html",
    "guides/fast-payout-casinos.html",
    "guides/how-to-play-aristocrat-pokies.html",
    "guides/how-to-play-booongo-pokies.html",
    "guides/how-to-play-jili-pokies.html",
    "guides/how-to-play-pokies.html",
    "guides/no-deposit-bonus.html",
]

# Pages needing RG strip specifically
NEEDS_RG = [
    "banking/crypto-casino-deposits.html",
    "banking/payid-casino-deposits.html",
    "guides/best-crypto-casinos.html",
    "guides/best-e-wallet-pokies-australia.html",
    "guides/best-online-pokies-australia.html",
    "guides/best-pokies-australia.html",
    "guides/how-to-play-jili-pokies.html",
    "guides/no-deposit-bonus.html",
]


def inject_compliance(path_str):
    path = GENERATED / path_str
    html = path.read_text(encoding="utf-8")

    changed = False

    # 1. Inject affiliate disclosure after <body> tag if missing
    if "affiliate" not in html.lower():
        html = html.replace("<body>", "<body>" + AFFILIATE_BANNER, 1)
        changed = True
        print(f"   ✅ Injected affiliate disclosure → {path_str}")

    # 2. Inject RG strip — append at end if </body> missing (truncated pages)
    if path_str in NEEDS_RG and "1800 858 858" not in html and "gamblinghelponline" not in html.lower():
        if "</body>" in html:
            html = html.replace("</body>", RG_STRIP + "</body>", 1)
        else:
            html = html + RG_STRIP  # truncated page — append at end
        changed = True
        print(f"   ✅ Injected responsible gambling strip → {path_str}")

    if changed:
        path.write_text(html, encoding="utf-8")


def add_schema_to_legal(path_str, page_type, title, url):
    """Inject a minimal WebPage/Legal JSON-LD schema."""
    path = GENERATED / path_str
    html = path.read_text(encoding="utf-8")

    if '"@context"' in html:
        print(f"   ⏭️  Schema already present → {path_str}")
        return

    schema = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": title,
        "url": f"https://ssusa.co{url}",
        "inLanguage": "en-AU",
        "isPartOf": {"@type": "WebSite", "name": "AussiePokies96", "url": "https://ssusa.co"},
        "publisher": {
            "@type": "Organization",
            "name": "AussiePokies96",
            "url": "https://ssusa.co"
        }
    }

    schema_block = f'\n<script type="application/ld+json">\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n</script>\n'
    html = html.replace("</head>", schema_block + "</head>", 1)
    path.write_text(html, encoding="utf-8")
    print(f"   ✅ Injected WebPage schema → {path_str}")


def fix_wowza96():
    """Remove the broken second schema block in wowza96.html."""
    path = GENERATED / "reviews/wowza96.html"
    html = path.read_text(encoding="utf-8")

    # Find all JSON-LD script blocks
    blocks = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>',
        html, re.DOTALL
    )

    fixed = False
    for i, block in enumerate(blocks):
        try:
            json.loads(block)
        except json.JSONDecodeError as e:
            print(f"   🔧 Fixing broken schema block #{i+1} in wowza96.html: {e}")
            # Remove the broken block entirely
            bad = f'<script type="application/ld+json">{block}</script>'
            html = html.replace(bad, "", 1)
            fixed = True

    if fixed:
        path.write_text(html, encoding="utf-8")
        print(f"   ✅ Fixed wowza96.html schema")
    else:
        print(f"   ⏭️  No broken schema found in wowza96.html")


# ── Run ──

print("\n🔧  Fixing compliance issues...\n")

for p in COMPLIANCE_PAGES:
    inject_compliance(p)

print("\n🔧  Adding schema to legal pages...\n")

add_schema_to_legal(
    "privacy-policy.html",
    "WebPage",
    "Privacy Policy — AussiePokies96",
    "/privacy-policy/"
)
add_schema_to_legal(
    "terms-conditions.html",
    "WebPage",
    "Terms & Conditions — AussiePokies96",
    "/terms-conditions/"
)

print("\n🔧  Fixing wowza96.html schema...\n")
fix_wowza96()

print("\n✅  Done. Run content_post_processor.py to verify.\n")
