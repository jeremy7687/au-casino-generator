#!/usr/bin/env python3
"""
NeuronWriter API wrapper — creates a query, polls for results, returns SEO data.

Required env vars:
    NEURONWRITER_API_KEY   — from app.neuronwriter.com/api-docs
    NEURONWRITER_PROJECT   — project ID (e.g. ea854f7f5c5bcfda)
"""

import datetime
import os
import time
import json
from pathlib import Path
try:
    import requests
except ImportError:
    requests = None


_CACHE_DIR = Path(__file__).parent / "neuron_cache"
_CACHE_TTL_DAYS = 7


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
        age = (datetime.date.today() - datetime.date.fromisoformat(cached_at)).days
        if age > _CACHE_TTL_DAYS:
            return None
    return data


def _cache_save(keyword: str, result: dict) -> None:
    _CACHE_DIR.mkdir(exist_ok=True)
    to_save = {**result, "_cached_at": datetime.date.today().isoformat()}
    _cache_path(keyword).write_text(json.dumps(to_save, indent=2))


API_BASE = "https://app.neuronwriter.com/neuron-api/0.5"


def get_neuron_recommendations(keyword: str, language: str = "English", country: str = "com.au", refresh: bool = False) -> dict:
    """
    Return NeuronWriter SEO data for keyword.
    Uses a local cache (neuron_cache/) with a 7-day TTL.
    Pass refresh=True to force a fresh API call.
    Returns an empty-but-valid structure on any failure.
    """
    if not refresh:
        cached = _cache_load(keyword)
        if cached:
            age = (datetime.date.today() - datetime.date.fromisoformat(cached["_cached_at"])).days
            print(f"   💾  NeuronWriter: cached results for \"{keyword}\" ({age}d old)")
            return cached

    api_key = os.environ.get("NEURONWRITER_API_KEY", "")
    project_id = os.environ.get("NEURONWRITER_PROJECT", "")

    empty = {
        "questions_paa": [], "questions_suggest": [], "questions_content": [],
        "h2_terms": [], "entities": [], "competitors": [], "content_terms": [],
        "target_word_count": None, "prompt_block": "",
    }

    if not api_key:
        print(f"   ⚠️   NEURONWRITER_API_KEY not set — skipping NeuronWriter")
        return empty

    if not project_id:
        print(f"   ⚠️   NEURONWRITER_PROJECT not set — skipping NeuronWriter")
        return empty

    if requests is None:
        print(f"   ⚠️   requests not installed — run: pip install requests")
        return empty

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    # ── Step 1: Create query ──
    print(f"   🧠  NeuronWriter: creating query for \"{keyword}\"...")
    try:
        resp = requests.post(
            f"{API_BASE}/writer/new-query",
            headers=headers,
            json={
                "project": project_id,
                "keyword": keyword,
                "engine": f"google.{country}",
                "language": language,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"   ⚠️   NeuronWriter new-query failed: {e}")
        return empty

    query_id = data.get("query_id") or data.get("id")
    if not query_id:
        print(f"   ⚠️   NeuronWriter: no query_id in response: {data}")
        return empty

    print(f"   ⏳  Query created (id: {query_id}). Waiting for analysis...")

    # ── Step 2: Poll until ready (max 90s) ──
    result = None
    for attempt in range(18):  # 18 × 5s = 90s max
        time.sleep(5)
        try:
            resp = requests.get(
                f"{API_BASE}/writer/get-query",
                headers=headers,
                params={"query_id": query_id},
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()
            status = result.get("status", "")
            if status == "done":
                print(f"   ✅  NeuronWriter analysis ready")
                break
            elif status == "error":
                print(f"   ⚠️   NeuronWriter query error: {result}")
                return empty
            else:
                print(f"      ⏳  Status: {status} (attempt {attempt+1}/18)")
        except Exception as e:
            print(f"   ⚠️   NeuronWriter poll error: {e}")
            if attempt >= 5:
                return empty

    if not result or result.get("status") != "done":
        print(f"   ⚠️   NeuronWriter timed out — continuing without SEO data")
        return empty

    # ── Step 3: Parse results and cache ──
    parsed = _parse_result(result, query_id)
    _cache_save(keyword, parsed)
    return parsed


def _parse_result(result: dict, query_id: str) -> dict:
    """Extract useful SEO data from NeuronWriter response."""

    # Questions
    questions_paa = [q.get("query", q) if isinstance(q, dict) else q
                     for q in result.get("questions_paa", [])[:10]]
    questions_suggest = [q.get("query", q) if isinstance(q, dict) else q
                         for q in result.get("questions_suggest", [])[:10]]
    questions_content = [q.get("query", q) if isinstance(q, dict) else q
                         for q in result.get("questions_content", [])[:10]]

    # Content terms / keywords to include
    content_terms = []
    for t in result.get("content_terms", [])[:40]:
        if isinstance(t, dict):
            content_terms.append(t.get("term") or t.get("keyword") or str(t))
        else:
            content_terms.append(str(t))

    # H2 suggestions
    h2_terms = []
    for t in result.get("h2_terms", result.get("headings", []))[:20]:
        if isinstance(t, dict):
            h2_terms.append(t.get("term") or t.get("heading") or str(t))
        else:
            h2_terms.append(str(t))

    # Entities
    entities = []
    for e in result.get("entities", [])[:20]:
        if isinstance(e, dict):
            entities.append(e.get("name") or e.get("entity") or str(e))
        else:
            entities.append(str(e))

    # Competitors
    competitors = []
    for c in result.get("competitors", [])[:10]:
        if isinstance(c, dict):
            competitors.append({
                "url": c.get("url", ""),
                "title": c.get("title", ""),
                "word_count": c.get("word_count", 0),
            })

    # Target word count
    target_wc = (result.get("target_word_count")
                 or result.get("recommended_word_count")
                 or result.get("avg_word_count"))

    # Build prompt block for Claude
    prompt_block = _build_prompt_block(
        questions_paa, questions_suggest, questions_content,
        content_terms, h2_terms, entities, target_wc
    )

    return {
        "query_id": query_id,
        "questions_paa": questions_paa,
        "questions_suggest": questions_suggest,
        "questions_content": questions_content,
        "h2_terms": h2_terms,
        "entities": entities,
        "competitors": competitors,
        "content_terms": content_terms,
        "target_word_count": target_wc,
        "prompt_block": prompt_block,
    }


def _build_prompt_block(paa, suggest, content_qs, terms, h2s, entities, target_wc) -> str:
    """Build the NeuronWriter instructions block injected into Claude's prompt."""
    lines = ["\n## NEURONWRITER SEO REQUIREMENTS"]

    if target_wc:
        lines.append(f"Target word count: {target_wc}+ words (NeuronWriter recommended)")

    if h2s:
        lines.append(f"\n### Suggested H2 headings to include (use as-is or adapt):")
        for h in h2s[:12]:
            lines.append(f"  - {h}")

    all_qs = list(dict.fromkeys(paa + suggest + content_qs))
    if all_qs:
        lines.append(f"\n### Questions to answer (PAA + search suggestions):")
        for q in all_qs[:15]:
            lines.append(f"  - {q}")

    if terms:
        lines.append(f"\n### Key terms to naturally include in content:")
        lines.append("  " + ", ".join(terms[:30]))

    if entities:
        lines.append(f"\n### Entities to mention (brands, orgs, concepts):")
        lines.append("  " + ", ".join(entities[:15]))

    lines.append("\nIncorporate ALL of the above naturally — never keyword-stuff.")
    return "\n".join(lines)


# ── CLI test ──
if __name__ == "__main__":
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "best payid casino australia"
    result = get_neuron_recommendations(kw)
    print(json.dumps({k: v for k, v in result.items() if k != "prompt_block"}, indent=2))
    if result.get("prompt_block"):
        print("\n--- PROMPT BLOCK ---")
        print(result["prompt_block"])
