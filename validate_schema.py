#!/usr/bin/env python3
"""
JSON-LD schema validator for generated HTML pages.

Checks that each page category has the expected schema types present.
Exits with code 1 if any errors are found (for CI/CD gate usage).

Expected schemas per category:
  index          : WebSite, Organization, ItemList, FAQPage
  reviews/       : Review, FAQPage, BreadcrumbList
  guides/        : Article, FAQPage, BreadcrumbList
  banking/       : Article, BreadcrumbList
  about.html     : WebPage (optional)
  privacy-policy : WebPage (optional)
  terms-cond     : WebPage (optional)

Usage:
  python3 validate_schema.py                    # validate all pages
  python3 validate_schema.py --only index.html  # validate one page
  python3 validate_schema.py --fix              # (future) auto-fix missing schemas
"""

import json
import re
import sys
from pathlib import Path

GENERATED_DIR = Path(__file__).parent / "generated"

# Required schema types per page category
REQUIRED_SCHEMAS: dict[str, list[str]] = {
    "index":   ["WebSite", "Organization", "ItemList", "FAQPage"],
    "reviews": ["Review", "FAQPage", "BreadcrumbList"],
    "guides":  ["Article", "FAQPage", "BreadcrumbList"],
    "banking": ["Article", "BreadcrumbList"],
}

# Optional — just warn, don't fail
OPTIONAL_SCHEMAS: dict[str, list[str]] = {
    "about":   ["WebPage"],
    "privacy": ["WebPage"],
    "terms":   ["WebPage"],
}


def _extract_schema_types(html: str) -> list[str]:
    """Extract all @type values from JSON-LD blocks in an HTML file."""
    types = []
    for block in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE
    ):
        try:
            data = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type"):
                    t = item["@type"]
                    if isinstance(t, list):
                        types.extend(t)
                    else:
                        types.append(t)
        elif isinstance(data, dict):
            # Handle @graph
            if "@graph" in data:
                for item in data["@graph"]:
                    if isinstance(item, dict) and item.get("@type"):
                        t = item["@type"]
                        if isinstance(t, list):
                            types.extend(t)
                        else:
                            types.append(t)
            else:
                t = data.get("@type")
                if t:
                    if isinstance(t, list):
                        types.extend(t)
                    else:
                        types.append(t)
    return types


def _category(rel_path: str) -> str:
    """Derive page category from relative path."""
    p = rel_path.replace("\\", "/")
    if p == "index.html":
        return "index"
    if p.startswith("reviews/"):
        return "reviews"
    if p.startswith("guides/"):
        return "guides"
    if p.startswith("banking/"):
        return "banking"
    if "about" in p:
        return "about"
    if "privacy" in p:
        return "privacy"
    if "terms" in p:
        return "terms"
    return "other"


def validate_file(html_path: Path) -> list[str]:
    """Return list of error strings for a single file (empty = pass)."""
    rel = str(html_path.relative_to(GENERATED_DIR))
    cat = _category(rel)

    required = REQUIRED_SCHEMAS.get(cat, [])
    optional = OPTIONAL_SCHEMAS.get(cat, [])

    if not required and not optional:
        return []  # no rules for this category

    try:
        html = html_path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"Cannot read {rel}: {e}"]

    found = _extract_schema_types(html)
    errors = []

    for schema_type in required:
        if schema_type not in found:
            errors.append(f"  ❌  {rel}: missing required schema @type={schema_type}")

    return errors


def validate_all(only: list[str] | None = None) -> tuple[int, int]:
    """
    Validate all (or filtered) HTML pages.
    Returns (error_count, page_count).
    """
    pages = sorted(GENERATED_DIR.rglob("*.html"))

    if only:
        only_set = {p.strip() for p in only}
        pages = [p for p in pages if str(p.relative_to(GENERATED_DIR)) in only_set]

    total_errors = 0
    page_count = 0

    for page in pages:
        rel = str(page.relative_to(GENERATED_DIR))
        cat = _category(rel)
        if cat == "other":
            continue  # skip responsible-gambling, 404, etc.

        errors = validate_file(page)
        page_count += 1

        if errors:
            for e in errors:
                print(e)
            total_errors += len(errors)
        else:
            found = _extract_schema_types(page.read_text(encoding="utf-8"))
            print(f"  ✅  {rel}: {', '.join(found)}")

    return total_errors, page_count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate JSON-LD schema on generated pages")
    parser.add_argument("--only", help="Comma-separated list of pages to validate (e.g. index.html,reviews/stake96.html)")
    parser.add_argument("--quiet", action="store_true", help="Only print errors, not passes")
    args = parser.parse_args()

    only_list = [p.strip() for p in args.only.split(",")] if args.only else None

    print(f"\n🔍  Validating JSON-LD schemas in generated/\n")
    errors, pages = validate_all(only=only_list)

    print(f"\n{'─'*50}")
    if errors:
        print(f"  ❌  {errors} error(s) across {pages} page(s)")
        sys.exit(1)
    else:
        print(f"  ✅  All {pages} page(s) passed schema validation")
        sys.exit(0)
