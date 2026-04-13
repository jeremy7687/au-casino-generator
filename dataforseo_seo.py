#!/usr/bin/env python3
"""
DataForSEO API wrapper — replaces NeuronWriter + Crawl4AI for gap analysis.

Fetches SERP data (organic results, PAA, related searches) and related keywords.
Returns the same structure as the old neuron_seo.get_neuron_recommendations().

Required env vars:
    DATAFORSEO_LOGIN    — from app.dataforseo.com
    DATAFORSEO_PASSWORD — from app.dataforseo.com
"""

import base64
import datetime
import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path


_CACHE_DIR = Path(__file__).parent / "dataforseo_cache"
_CACHE_TTL_DAYS = 7
API_BASE = "https://api.dataforseo.com"

# Australia location code + language
DEFAULT_LOCATION = 2036
DEFAULT_LANG = "en"


# ── Cache ──

def _cache_path(keyword: str) -> Path:
    slug = keyword.lower().strip().replace(" ", "-").replace("/", "-")
    return _CACHE_DIR / f"{slug}.json"


def _cache_load(keyword: str) -> dict | None:
    path = _cache_path(keyword)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    cached_at = data.get("_cached_at", "")
    if cached_at:
        age = (datetime.date.today() - datetime.date.fromisoformat(cached_at)).days
        if age > _CACHE_TTL_DAYS:
            return None
    return data


def _cache_save(keyword: str, result: dict) -> None:
    _CACHE_DIR.mkdir(exist_ok=True)
    to_save = {**result, "_cached_at": datetime.date.today().isoformat()}
    _cache_path(keyword).write_text(json.dumps(to_save, indent=2, ensure_ascii=False), encoding="utf-8")


# ── HTTP ──

def _auth_header() -> str:
    login = os.environ.get("DATAFORSEO_LOGIN", "")
    password = os.environ.get("DATAFORSEO_PASSWORD", "")
    token = base64.b64encode(f"{login}:{password}".encode()).decode()
    return f"Basic {token}"


def _post(endpoint: str, payload: list) -> dict:
    url = f"{API_BASE}{endpoint}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": _auth_header(),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"status_code": e.code, "status_message": body[:300]}
    except Exception as e:
        return {"status_code": 0, "status_message": str(e)}


# ── API calls ──

def _fetch_serp(keyword: str, location_code: int, language_code: str) -> dict:
    """Fetch organic SERP results, PAA, and related searches."""
    resp = _post("/v3/serp/google/organic/live/advanced", [{
        "keyword": keyword,
        "location_code": location_code,
        "language_code": language_code,
        "depth": 10,
        "se_domain": "google.com.au",
    }])

    if resp.get("status_code") != 20000:
        print(f"   ⚠️   DataForSEO SERP error: {resp.get('status_message', '')[:100]}")
        return {}

    tasks = resp.get("tasks", [])
    if not tasks or tasks[0].get("status_code") != 20000:
        msg = tasks[0].get("status_message", "") if tasks else "no tasks"
        print(f"   ⚠️   DataForSEO SERP task error: {msg[:100]}")
        return {}

    result = tasks[0].get("result", [])
    if not result:
        return {}

    items = result[0].get("items", []) or []
    competitors, paa, related = [], [], []

    for item in items:
        t = item.get("type", "")
        if t == "organic":
            competitors.append({
                "url":   item.get("url", ""),
                "title": item.get("title", ""),
                "rank":  item.get("rank_absolute", 0),
                "word_count": 0,
            })
        elif t == "people_also_ask":
            for entry in (item.get("items") or []):
                q = entry.get("title", "").strip()
                if q:
                    paa.append(q)
        elif t == "related_searches":
            for entry in (item.get("items") or []):
                q = entry.get("title", "").strip()
                if q:
                    related.append(q)

    return {
        "competitors":      competitors[:10],
        "questions_paa":    paa[:10],
        "related_searches": related[:10],
    }


def _fetch_related_keywords(keyword: str, location_code: int, language_code: str) -> list:
    """Fetch related keywords from DataForSEO Labs."""
    resp = _post("/v3/dataforseo_labs/google/related_keywords/live", [{
        "keyword":       keyword,
        "location_code": location_code,
        "language_code": language_code,
        "limit":         30,
    }])

    if resp.get("status_code") != 20000:
        return []

    tasks = resp.get("tasks", [])
    if not tasks or tasks[0].get("status_code") != 20000:
        return []

    result = tasks[0].get("result", [])
    if not result:
        return []

    keywords = []
    for item in (result[0].get("items") or []):
        kw = (item.get("keyword_data") or {}).get("keyword", "").strip()
        if kw:
            keywords.append(kw)

    return keywords


# ── Main entry point ──

def get_dataforseo_recommendations(
    keyword: str,
    language_code: str = DEFAULT_LANG,
    location_code: int = DEFAULT_LOCATION,
    refresh: bool = False,
) -> dict:
    """
    Return DataForSEO SEO data for keyword.
    Uses a local cache (dataforseo_cache/) with a 7-day TTL.
    Returns an empty-but-valid structure on any failure.
    """
    empty = {
        "questions_paa": [], "questions_suggest": [], "questions_content": [],
        "h2_terms": [], "entities": [], "competitors": [], "content_terms": [],
        "target_word_count": None, "prompt_block": "",
    }

    if not refresh:
        cached = _cache_load(keyword)
        if cached:
            age = (datetime.date.today() - datetime.date.fromisoformat(cached["_cached_at"])).days
            print(f"   💾  DataForSEO: cached results for \"{keyword}\" ({age}d old)")
            return cached

    login = os.environ.get("DATAFORSEO_LOGIN", "")
    password = os.environ.get("DATAFORSEO_PASSWORD", "")

    if not login or not password:
        print("   ⚠️   DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD not set — skipping DataForSEO")
        return empty

    print(f"   🔍  DataForSEO: fetching SERP data for \"{keyword}\"...")
    serp = _fetch_serp(keyword, location_code, language_code)
    if not serp:
        return empty

    time.sleep(0.5)

    print(f"   🔗  DataForSEO: fetching related keywords...")
    rel_kws = _fetch_related_keywords(keyword, location_code, language_code)

    competitors = serp.get("competitors", [])
    paa         = serp.get("questions_paa", [])
    searches    = serp.get("related_searches", [])

    # Build suggestions: related searches + question-form related keywords
    _q_words = {"how", "what", "why", "when", "where", "which", "can", "is", "are", "do", "does"}
    suggest = list(searches)
    for kw in rel_kws:
        if kw.split()[0].lower() in _q_words:
            suggest.append(kw)
    suggest = list(dict.fromkeys(suggest))[:15]

    # H2 terms derived from competitor page titles
    h2_terms = [c["title"] for c in competitors if c.get("title")]

    # Content terms: non-question related keywords
    content_terms = [
        {"term": kw} for kw in rel_kws
        if kw.split()[0].lower() not in _q_words
    ][:20]

    print(
        f"   ✅  DataForSEO: {len(paa)} PAA | {len(suggest)} suggestions | "
        f"{len(competitors)} competitors | {len(rel_kws)} related keywords"
    )

    result = {
        "questions_paa":     paa,
        "questions_suggest": suggest,
        "questions_content": [],
        "h2_terms":          h2_terms,
        "entities":          [],
        "competitors":       competitors,
        "content_terms":     content_terms,
        "target_word_count": None,
        "prompt_block":      _build_prompt_block(paa, suggest, content_terms, h2_terms),
    }

    _cache_save(keyword, result)
    return result


def _build_prompt_block(paa, suggest, terms, h2s) -> str:
    lines = ["\n## DATAFORSEO SEO DATA"]

    if h2s:
        lines.append("\n### Top competitor page titles:")
        for h in h2s[:10]:
            lines.append(f"  - {h}")

    all_qs = list(dict.fromkeys(paa + suggest))
    if all_qs:
        lines.append("\n### Questions to answer (PAA + search suggestions):")
        for q in all_qs[:15]:
            lines.append(f"  - {q}")

    term_strs = [t["term"] if isinstance(t, dict) else str(t) for t in terms]
    if term_strs:
        lines.append("\n### Key terms to naturally include in content:")
        lines.append("  " + ", ".join(term_strs[:25]))

    lines.append("\nIncorporate ALL of the above naturally — never keyword-stuff.")
    return "\n".join(lines)


# ── CLI test ──
if __name__ == "__main__":
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "best payid casino australia"
    result = get_dataforseo_recommendations(kw)
    print(json.dumps({k: v for k, v in result.items() if k != "prompt_block"}, indent=2))
    if result.get("prompt_block"):
        print("\n--- PROMPT BLOCK ---")
        print(result["prompt_block"])
