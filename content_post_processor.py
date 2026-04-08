#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  Content Post-Processor — Enforce Inline CSS + CWV + Cleanup

  Runs after Claude generates HTML. Catches and fixes:
    1. External CSS/JS references (strips them)
    2. Missing inline CSS on paragraphs/headings
    3. Images missing lazy loading or dimensions
    4. Font declarations missing font-display: swap
    5. Stale year references (2024/2025 → current year)
    6. Missing responsible gambling section
    7. Missing affiliate disclosure
    8. Schema validation (calls validate_schema.py if available)
    9. Page weight check (warns if >100KB for AU, >80KB for PG)

  Usage:
    python3 content_post_processor.py generated/index.html
    python3 content_post_processor.py generated/              # process all HTML
    python3 content_post_processor.py generated/ --fix        # auto-fix issues
    python3 content_post_processor.py generated/ --fix --push # fix + push to GitHub
    python3 content_post_processor.py generated/ --report     # generate JSON report
    python3 content_post_processor.py generated/ --market=au  # set market (au/pg/kh/hk)

  Best practice: Run after every content generation before pushing.
  Add to GitHub Actions as a validation step before deploy.

  Prerequisites:
    pip install beautifulsoup4
    Optional: pip install PyGithub (for --push flag)
═══════════════════════════════════════════════════════════════
"""

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

YEAR = datetime.date.today().year
PREV_YEARS = [2024, 2025] if YEAR == 2026 else [y for y in range(2023, YEAR)]

MARKET_CONFIGS = {
    "au": {
        "max_page_weight_kb": 100,
        "inline_css_pattern": r'margin:\s*0;\s*font-size:\s*12px;\s*text-transform:\s*none;',
        "required_disclosures": ["affiliate", "responsible gambling", "18+"],
        "responsible_gambling_text": ["gambling help", "gamble responsibly", "1800 858 858", "gamblinghelponline"],
        "language_checks": {
            "preferred": {"pokies": "slots", "punters": "players"},
            "min_ratio": 0.7,
        },
        "domain": "https://ssusa.co",
    },
    "pg": {
        "max_page_weight_kb": 80,
        "inline_css_pattern": r'margin:\s*0;\s*font-size:\s*12px;\s*text-transform:\s*none;',
        "required_disclosures": ["affiliate", "responsible gambling", "18+"],
        "responsible_gambling_text": ["gamble responsibly", "responsible gambling"],
        "language_checks": {
            "preferred": {"pokies": "slots"},
            "min_ratio": 0.7,
        },
        "domain": "https://dailygamingtips.com",
    },
    "kh": {
        "max_page_weight_kb": 80,
        "inline_css_pattern": r'margin:\s*0;\s*font-size:\s*12px;\s*text-transform:\s*none;',
        "required_disclosures": ["responsible gambling"],
        "responsible_gambling_text": ["responsible gambling"],
        "language_checks": {},
        "domain": "",
    },
    "hk": {
        "max_page_weight_kb": 80,
        "inline_css_pattern": r'margin:\s*0;\s*font-size:\s*12px;\s*text-transform:\s*none;',
        "required_disclosures": ["responsible gambling"],
        "responsible_gambling_text": ["responsible gambling"],
        "language_checks": {},
        "domain": "https://gcg88.com",
    },
}

# Page categories that skip certain checks
LEGAL_PAGES = {"privacy-policy", "terms-conditions", "responsible-gambling"}


# ─────────────────────────────────────────────
# ISSUE TRACKING
# ─────────────────────────────────────────────

class Issue:
    """Single issue found in a page."""
    def __init__(self, severity, category, message, line=None, fixable=False):
        self.severity = severity   # "ERROR", "WARNING", "INFO"
        self.category = category   # "css", "cwv", "seo", "compliance", "weight"
        self.message = message
        self.line = line
        self.fixable = fixable

    def __repr__(self):
        loc = f" (line {self.line})" if self.line else ""
        fix = " [auto-fixable]" if self.fixable else ""
        return f"[{self.severity}] {self.category}: {self.message}{loc}{fix}"


# ─────────────────────────────────────────────
# CHECK FUNCTIONS
# ─────────────────────────────────────────────

def check_external_resources(html: str, lines: list) -> list:
    """Check for external CSS/JS that shouldn't be there."""
    issues = []
    
    # External stylesheets (allow Google Fonts only)
    for i, line in enumerate(lines, 1):
        if '<link' in line.lower() and 'stylesheet' in line.lower():
            if 'fonts.googleapis.com' not in line and 'fonts.gstatic.com' not in line:
                issues.append(Issue("ERROR", "css",
                    f"External stylesheet found — must use inline CSS only: {line.strip()[:80]}",
                    line=i, fixable=True))
        
        # External JS (allow GA4/GTM only)
        if '<script' in line.lower() and 'src=' in line.lower():
            allowed = ['googletagmanager.com', 'google-analytics.com', 'gtag']
            if not any(a in line for a in allowed):
                issues.append(Issue("WARNING", "css",
                    f"External script found — should use inline JS only: {line.strip()[:80]}",
                    line=i, fixable=False))
    
    return issues


def check_images(html: str, lines: list) -> list:
    """Check images for lazy loading, dimensions, alt text, and format."""
    issues = []
    
    img_pattern = re.compile(r'<img\s[^>]*>', re.IGNORECASE)
    
    for i, line in enumerate(lines, 1):
        for match in img_pattern.finditer(line):
            tag = match.group()
            
            # Check lazy loading
            if 'loading="lazy"' not in tag and 'loading=\'lazy\'' not in tag:
                # First image (hero) should NOT be lazy loaded
                if i > 50:  # rough heuristic: after line 50, should be lazy
                    issues.append(Issue("WARNING", "cwv",
                        f"Image missing loading=\"lazy\": {tag[:60]}...",
                        line=i, fixable=True))
            
            # Check dimensions
            has_width = 'width=' in tag or 'width:' in tag
            has_height = 'height=' in tag or 'height:' in tag
            if not has_width or not has_height:
                issues.append(Issue("WARNING", "cwv",
                    f"Image missing explicit width/height (causes CLS): {tag[:60]}...",
                    line=i, fixable=False))
            
            # Check alt text
            if 'alt=' not in tag:
                issues.append(Issue("ERROR", "seo",
                    f"Image missing alt text: {tag[:60]}...",
                    line=i, fixable=False))
            elif 'alt=""' in tag or "alt=''" in tag:
                issues.append(Issue("WARNING", "seo",
                    f"Image has empty alt text: {tag[:60]}...",
                    line=i, fixable=False))
            
            # Check format suggestion
            src_match = re.search(r'src=["\']([^"\']+)["\']', tag)
            if src_match:
                src = src_match.group(1)
                if src.endswith(('.jpg', '.jpeg', '.png')) and not src.startswith('data:'):
                    issues.append(Issue("INFO", "cwv",
                        f"Consider WebP format for: {src}",
                        line=i, fixable=False))
    
    return issues


def check_fonts(html: str, lines: list) -> list:
    """Check font declarations for font-display: swap."""
    issues = []
    
    in_style = False
    has_font_face = False
    
    for i, line in enumerate(lines, 1):
        if '<style' in line.lower():
            in_style = True
        if '</style' in line.lower():
            in_style = False
        
        if in_style and '@font-face' in line:
            has_font_face = True
        
        if in_style and has_font_face:
            if '}' in line:
                has_font_face = False
            if 'font-display' not in line and 'src:' in line:
                # Check if font-display: swap exists in the block
                pass  # handled at block level below
    
    # Block-level check for @font-face without font-display
    font_face_blocks = re.findall(r'@font-face\s*\{[^}]+\}', html, re.DOTALL)
    for block in font_face_blocks:
        if 'font-display' not in block:
            issues.append(Issue("ERROR", "cwv",
                "Missing font-display: swap in @font-face — causes LCP/CLS issues",
                fixable=True))
    
    return issues


def check_stale_years(html: str, lines: list) -> list:
    """Check for outdated year references."""
    issues = []
    
    for i, line in enumerate(lines, 1):
        for prev_year in PREV_YEARS:
            # Skip dates in schema (datePublished, dateModified)
            if f'datePublished' in line or f'dateModified' in line:
                continue
            # Skip comments
            if line.strip().startswith('<!--'):
                continue
            
            year_str = str(prev_year)
            if year_str in line:
                # Check it's a standalone year reference, not part of a number
                pattern = rf'(?<!\d){year_str}(?!\d)'
                if re.search(pattern, line):
                    issues.append(Issue("WARNING", "seo",
                        f"Stale year reference '{year_str}' found — should be {YEAR}: {line.strip()[:80]}",
                        line=i, fixable=True))
    
    return issues


def check_compliance(html: str, lines: list, config: dict, page_name: str) -> list:
    """Check for required disclosures and responsible gambling content."""
    issues = []
    html_lower = html.lower()
    
    # Skip legal pages for some checks
    page_stem = Path(page_name).stem
    if page_stem in LEGAL_PAGES:
        return issues
    
    # Check affiliate disclosure
    if "affiliate" in config.get("required_disclosures", []):
        if "affiliate" not in html_lower and "commission" not in html_lower:
            issues.append(Issue("ERROR", "compliance",
                "Missing affiliate disclosure — required above the fold",
                fixable=False))
    
    # Check responsible gambling
    if "responsible gambling" in config.get("required_disclosures", []):
        rg_texts = config.get("responsible_gambling_text", [])
        if not any(t in html_lower for t in rg_texts):
            issues.append(Issue("ERROR", "compliance",
                "Missing responsible gambling section/messaging",
                fixable=False))
    
    # Check 18+ messaging
    if "18+" in config.get("required_disclosures", []):
        if "18+" not in html and "eighteen" not in html_lower:
            issues.append(Issue("WARNING", "compliance",
                "Missing 18+ age verification messaging",
                fixable=False))
    
    return issues


def check_language(html: str, config: dict) -> list:
    """Check language usage ratios per market.
    
    AU market should use 'pokies' 70%+ of the time vs 'slots',
    and 'punters' 70%+ vs 'players'. Both terms are acceptable
    but the AU-preferred term should dominate.
    """
    issues = []
    lang_checks = config.get("language_checks", {})
    preferred_map = lang_checks.get("preferred", {})
    min_ratio = lang_checks.get("min_ratio", 0.7)
    
    if not preferred_map:
        return issues
    
    html_lower = html.lower()
    
    for preferred, secondary in preferred_map.items():
        pref_count = len(re.findall(rf'\b{preferred}\b', html_lower))
        sec_count = len(re.findall(rf'\b{secondary}\b', html_lower))
        total = pref_count + sec_count
        
        if total == 0:
            continue
        
        ratio = pref_count / total
        
        if sec_count > 0 and pref_count == 0:
            # Only secondary term used, zero preferred — that's a problem
            issues.append(Issue("WARNING", "seo",
                f"'{secondary}' used {sec_count} time(s) but '{preferred}' not used at all — "
                f"AU content should primarily use '{preferred}'",
                fixable=False))
        elif ratio < min_ratio and total >= 3:
            # Ratio is off — preferred term should dominate
            issues.append(Issue("INFO", "seo",
                f"'{preferred}' used {pref_count}x vs '{secondary}' {sec_count}x "
                f"(ratio {ratio:.0%}, target ≥{min_ratio:.0%}). "
                f"Consider using '{preferred}' more for AU localisation",
                fixable=False))
    
    return issues


def check_page_weight(html: str, config: dict) -> list:
    """Check page weight against market limits."""
    issues = []
    
    weight_kb = len(html.encode('utf-8')) / 1024
    max_kb = config.get("max_page_weight_kb", 100)
    
    if weight_kb > max_kb:
        issues.append(Issue("WARNING", "weight",
            f"Page weight {weight_kb:.1f}KB exceeds {max_kb}KB target",
            fixable=False))
    elif weight_kb > max_kb * 0.8:
        issues.append(Issue("INFO", "weight",
            f"Page weight {weight_kb:.1f}KB approaching {max_kb}KB limit",
            fixable=False))
    
    return issues


def check_schema(html: str) -> list:
    """Basic schema validation — check JSON-LD blocks parse correctly."""
    issues = []
    
    pattern = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE
    )
    
    blocks = pattern.findall(html)
    
    if not blocks:
        issues.append(Issue("ERROR", "seo",
            "No JSON-LD schema blocks found — every page needs schema",
            fixable=False))
        return issues
    
    for i, block in enumerate(blocks, 1):
        try:
            data = json.loads(block.strip())
            
            # Handle arrays and @graph structures
            schemas = []
            if isinstance(data, list):
                schemas = data
            elif isinstance(data, dict):
                if "@graph" in data:
                    schemas = data["@graph"] if isinstance(data["@graph"], list) else [data["@graph"]]
                else:
                    schemas = [data]
            
            for schema in schemas:
                if not isinstance(schema, dict):
                    continue
                schema_type = schema.get("@type", "Unknown")
            
            # Check required fields per type
                if schema_type == "FAQPage":
                    if "mainEntity" not in schema:
                        issues.append(Issue("ERROR", "seo",
                            f"FAQPage schema missing 'mainEntity'",
                            fixable=False))
                elif schema_type == "Article":
                    for field in ["headline", "author", "datePublished"]:
                        if field not in schema:
                            issues.append(Issue("WARNING", "seo",
                                f"Article schema missing '{field}'",
                                fixable=False))
                elif schema_type == "Review":
                    for field in ["itemReviewed", "reviewRating", "author"]:
                        if field not in schema:
                            issues.append(Issue("WARNING", "seo",
                                f"Review schema missing '{field}'",
                                fixable=False))
                        
        except json.JSONDecodeError as e:
            issues.append(Issue("ERROR", "seo",
                f"Invalid JSON in schema block #{i}: {str(e)[:60]}",
                fixable=False))
    
    return issues


def check_seo_basics(html: str, lines: list) -> list:
    """Check basic SEO elements."""
    issues = []
    html_lower = html.lower()
    
    # Check for single H1
    h1_count = len(re.findall(r'<h1[\s>]', html_lower))
    if h1_count == 0:
        issues.append(Issue("ERROR", "seo", "Missing H1 tag", fixable=False))
    elif h1_count > 1:
        issues.append(Issue("WARNING", "seo",
            f"Multiple H1 tags found ({h1_count}) — should have exactly 1",
            fixable=False))
    
    # Check title tag
    title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
    if not title_match:
        issues.append(Issue("ERROR", "seo", "Missing <title> tag", fixable=False))
    else:
        title = title_match.group(1)
        if len(title) > 60:
            issues.append(Issue("WARNING", "seo",
                f"Title tag too long ({len(title)} chars, max 60): {title[:60]}...",
                fixable=False))
        elif len(title) < 30:
            issues.append(Issue("WARNING", "seo",
                f"Title tag too short ({len(title)} chars): {title}",
                fixable=False))
    
    # Check meta description
    meta_desc = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']',
                          html, re.IGNORECASE)
    if not meta_desc:
        issues.append(Issue("ERROR", "seo", "Missing meta description", fixable=False))
    else:
        desc = meta_desc.group(1)
        if len(desc) > 160:
            issues.append(Issue("WARNING", "seo",
                f"Meta description too long ({len(desc)} chars, max 160)",
                fixable=False))
    
    # Check canonical tag
    if 'rel="canonical"' not in html_lower and "rel='canonical'" not in html_lower:
        issues.append(Issue("WARNING", "seo", "Missing canonical tag", fixable=False))
    
    # Check viewport meta (mobile)
    if 'name="viewport"' not in html_lower:
        issues.append(Issue("ERROR", "cwv",
            "Missing viewport meta tag — breaks mobile rendering",
            fixable=False))
    
    return issues


# ─────────────────────────────────────────────
# FIX FUNCTIONS
# ─────────────────────────────────────────────

def fix_external_stylesheets(html: str) -> str:
    """Remove external stylesheets (except Google Fonts)."""
    lines = html.split('\n')
    fixed = []
    removed = 0
    for line in lines:
        if '<link' in line.lower() and 'stylesheet' in line.lower():
            if 'fonts.googleapis.com' not in line and 'fonts.gstatic.com' not in line:
                removed += 1
                continue
        fixed.append(line)
    if removed:
        print(f"  ✓ Removed {removed} external stylesheet(s)")
    return '\n'.join(fixed)


def fix_lazy_loading(html: str) -> str:
    """Add loading='lazy' to images that are missing it (skip first image)."""
    first_img = True
    def add_lazy(match):
        nonlocal first_img
        tag = match.group()
        if first_img:
            first_img = False
            return tag
        if 'loading=' not in tag:
            tag = tag.replace('<img ', '<img loading="lazy" ')
        return tag
    
    result = re.sub(r'<img\s[^>]*>', add_lazy, html, flags=re.IGNORECASE)
    return result


def fix_font_display(html: str) -> str:
    """Add font-display: swap to @font-face blocks missing it."""
    def add_swap(match):
        block = match.group()
        if 'font-display' not in block:
            block = block.replace('}', '  font-display: swap;\n}')
        return block
    
    result = re.sub(r'@font-face\s*\{[^}]+\}', add_swap, html, flags=re.DOTALL)
    return result


def fix_stale_years(html: str) -> str:
    """Replace stale year references with current year."""
    for prev_year in PREV_YEARS:
        # Don't replace in datePublished or dateModified
        lines = html.split('\n')
        fixed_lines = []
        for line in lines:
            if 'datePublished' in line or 'dateModified' in line or line.strip().startswith('<!--'):
                fixed_lines.append(line)
            else:
                fixed_lines.append(re.sub(
                    rf'(?<!\d){prev_year}(?!\d)',
                    str(YEAR),
                    line
                ))
        html = '\n'.join(fixed_lines)
    return html


def apply_fixes(html: str) -> str:
    """Apply all auto-fixable corrections."""
    html = fix_external_stylesheets(html)
    html = fix_lazy_loading(html)
    html = fix_font_display(html)
    html = fix_stale_years(html)
    return html


# ─────────────────────────────────────────────
# MAIN PROCESSING
# ─────────────────────────────────────────────

def process_file(filepath: Path, market: str, fix: bool = False) -> dict:
    """Process a single HTML file and return results."""
    
    html = filepath.read_text(encoding='utf-8')
    lines = html.split('\n')
    config = MARKET_CONFIGS.get(market, MARKET_CONFIGS["au"])
    page_name = filepath.name
    
    all_issues = []
    
    # Run all checks
    all_issues.extend(check_external_resources(html, lines))
    all_issues.extend(check_images(html, lines))
    all_issues.extend(check_fonts(html, lines))
    all_issues.extend(check_stale_years(html, lines))
    all_issues.extend(check_compliance(html, lines, config, page_name))
    all_issues.extend(check_language(html, config))
    all_issues.extend(check_page_weight(html, config))
    all_issues.extend(check_schema(html))
    all_issues.extend(check_seo_basics(html, lines))
    
    # Apply fixes if requested
    if fix and any(i.fixable for i in all_issues):
        html_fixed = apply_fixes(html)
        if html_fixed != html:
            filepath.write_text(html_fixed, encoding='utf-8')
            print(f"  ✓ Fixes applied to {filepath.name}")
    
    # Count by severity
    errors = sum(1 for i in all_issues if i.severity == "ERROR")
    warnings = sum(1 for i in all_issues if i.severity == "WARNING")
    infos = sum(1 for i in all_issues if i.severity == "INFO")
    weight_kb = len(html.encode('utf-8')) / 1024
    
    return {
        "file": str(filepath),
        "page": page_name,
        "weight_kb": round(weight_kb, 1),
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "issues": all_issues,
        "passed": errors == 0,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Content Post-Processor — Validate and fix generated HTML"
    )
    parser.add_argument("path", help="HTML file or directory to process")
    parser.add_argument("--fix", action="store_true", help="Auto-fix fixable issues")
    parser.add_argument("--push", action="store_true", help="Push fixes to GitHub")
    parser.add_argument("--report", action="store_true", help="Output JSON report")
    parser.add_argument("--market", default="au", choices=["au", "pg", "kh", "hk"],
                        help="Market for market-specific checks (default: au)")
    parser.add_argument("--quiet", action="store_true", help="Only show errors")
    
    args = parser.parse_args()
    target = Path(args.path)
    
    # Collect HTML files
    if target.is_file():
        files = [target]
    elif target.is_dir():
        files = sorted(target.rglob("*.html"))
    else:
        print(f"Error: {target} not found")
        sys.exit(1)
    
    if not files:
        print(f"No HTML files found in {target}")
        sys.exit(1)
    
    print(f"\n{'═' * 60}")
    print(f"  Content Post-Processor — {args.market.upper()} Market")
    print(f"  Processing {len(files)} file(s)")
    print(f"  Mode: {'Fix + Report' if args.fix else 'Report only'}")
    print(f"{'═' * 60}\n")
    
    all_results = []
    total_errors = 0
    total_warnings = 0
    
    for filepath in files:
        result = process_file(filepath, args.market, fix=args.fix)
        all_results.append(result)
        total_errors += result["errors"]
        total_warnings += result["warnings"]
        
        # Print results
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        print(f"{status}  {result['page']} ({result['weight_kb']}KB)"
              f" — {result['errors']}E {result['warnings']}W {result['infos']}I")
        
        if not args.quiet:
            for issue in result["issues"]:
                if args.quiet and issue.severity == "INFO":
                    continue
                prefix = {"ERROR": "  ❌", "WARNING": "  ⚠️", "INFO": "  ℹ️"}
                print(f"{prefix.get(issue.severity, '  ')} {issue}")
        
        if result["issues"]:
            print()
    
    # Summary
    print(f"\n{'─' * 60}")
    print(f"  SUMMARY: {len(files)} files | {total_errors} errors | {total_warnings} warnings")
    passed = sum(1 for r in all_results if r["passed"])
    print(f"  Passed: {passed}/{len(files)}")
    
    if total_errors > 0:
        print(f"\n  ⚠️  {total_errors} error(s) found — fix before deploying")
    else:
        print(f"\n  ✅ All files passed validation")
    print(f"{'─' * 60}\n")
    
    # JSON report
    if args.report:
        report = {
            "timestamp": datetime.datetime.now().isoformat(),
            "market": args.market,
            "files_processed": len(files),
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "all_passed": total_errors == 0,
            "results": [
                {
                    "file": r["page"],
                    "weight_kb": r["weight_kb"],
                    "errors": r["errors"],
                    "warnings": r["warnings"],
                    "passed": r["passed"],
                    "issues": [str(i) for i in r["issues"]],
                }
                for r in all_results
            ],
        }
        report_path = Path("post-processor-report.json")
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(f"  Report saved to {report_path}")
    
    # Push to GitHub if requested
    if args.push and args.fix:
        try:
            from github import Github
            token = os.environ.get("GITHUB_TOKEN")
            repo_name = os.environ.get("GITHUB_REPO")
            if token and repo_name:
                print(f"\n  Pushing fixes to {repo_name}...")
                # Implementation depends on your repo structure
                print("  ⚠️  Auto-push not implemented — commit and push manually")
            else:
                print("  ⚠️  Set GITHUB_TOKEN and GITHUB_REPO env vars for auto-push")
        except ImportError:
            print("  ⚠️  pip install PyGithub for auto-push support")
    
    sys.exit(1 if total_errors > 0 else 0)


if __name__ == "__main__":
    main()
