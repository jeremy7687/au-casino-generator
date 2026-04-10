#!/usr/bin/env python3
"""
Freshness Updater — updates hardcoded dates in all generated HTML pages.

Updates:
  1. dateModified in JSON-LD schema blocks
  2. Visible "Updated DD Month YYYY" text in page headers
  3. "Last updated: DD Month YYYY" text
  4. Copyright year in footers

Usage:
  python3 freshness_updater.py            # dry-run (preview changes)
  python3 freshness_updater.py --update   # write changes to files
"""

import re
import sys
from pathlib import Path
from datetime import date

try:
    from telegram_notify import notify_freshness
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False

GENERATED = Path(__file__).parent / "generated"

today = date.today()
TODAY_ISO = today.strftime("%Y-%m-%d")           # 2026-04-08
TODAY_LONG = today.strftime("%-d %B %Y")         # 8 April 2026
YEAR = str(today.year)                           # 2026

DRY_RUN = "--update" not in sys.argv


def update_page(path: Path) -> int:
    """Update dates in a single HTML file. Returns number of changes made."""
    html = path.read_text(encoding="utf-8")
    original = html
    changes = 0

    # 1. JSON-LD dateModified  e.g.  "dateModified": "2026-03-31"
    new_html, n = re.subn(
        r'("dateModified"\s*:\s*")(\d{4}-\d{2}-\d{2})(")',
        rf'\g<1>{TODAY_ISO}\g<3>',
        html
    )
    if n:
        html = new_html
        changes += n

    # 2. Visible "Updated DD Month YYYY"  e.g.  Updated 31 March 2026
    new_html, n = re.subn(
        r'Updated\s+\d{1,2}\s+\w+\s+\d{4}',
        f'Updated {TODAY_LONG}',
        html
    )
    if n:
        html = new_html
        changes += n

    # 3. "Last updated: DD Month YYYY"
    new_html, n = re.subn(
        r'(Last updated:\s*)\d{1,2}\s+\w+\s+\d{4}',
        rf'\g<1>{TODAY_LONG}',
        html,
        flags=re.IGNORECASE
    )
    if n:
        html = new_html
        changes += n

    # 4. Copyright year in footer  e.g.  © 2025 or © 2026
    new_html, n = re.subn(
        r'©\s*\d{4}\s*(AussiePokies96)',
        rf'© {YEAR} \g<1>',
        html
    )
    if n:
        html = new_html
        changes += n

    if changes and html != original:
        rel = path.relative_to(GENERATED)
        if DRY_RUN:
            print(f"   [DRY RUN] Would update {changes} date(s) → {rel}")
        else:
            path.write_text(html, encoding="utf-8")
            print(f"   ✅ Updated {changes} date(s) → {rel}")

    return changes


def update_sitemap_lastmod(sitemap_path: Path) -> bool:
    """Update all <lastmod> dates in sitemap.xml to today. Returns True if changed."""
    if not sitemap_path.exists():
        return False
    xml = sitemap_path.read_text(encoding="utf-8")
    updated, n = re.subn(
        r'(<lastmod>)\d{4}-\d{2}-\d{2}(</lastmod>)',
        rf'\g<1>{TODAY_ISO}\g<2>',
        xml
    )
    if n and updated != xml:
        if not DRY_RUN:
            sitemap_path.write_text(updated, encoding="utf-8")
        print(f"   {'[DRY RUN] Would update' if DRY_RUN else 'Updated'} {n} <lastmod> date(s) in {sitemap_path.name}")
        return True
    return False


# ── Main ──

print(f"\n{'[DRY RUN] ' if DRY_RUN else ''}Freshness Updater")
print(f"   Today: {TODAY_LONG}  ({TODAY_ISO})")
print(f"   Target dir: {GENERATED}\n")

if not GENERATED.exists():
    print("❌ generated/ directory not found. Run generate_au.py first.")
    sys.exit(1)

html_files = sorted(GENERATED.rglob("*.html"))
total_files = 0
total_changes = 0

for f in html_files:
    n = update_page(f)
    if n:
        total_files += 1
        total_changes += n

# Update sitemap lastmod dates
update_sitemap_lastmod(GENERATED / "sitemap.xml")

print(f"\n{'Would update' if DRY_RUN else 'Updated'} {total_changes} date(s) across {total_files} file(s).")
if DRY_RUN:
    print("Run with --update to apply changes.\n")
else:
    print("Done. Deploy with: wrangler pages deploy generated --project-name=au-casino\n")
    if HAS_TELEGRAM and total_changes > 0:
        notify_freshness(total_files, total_changes)
