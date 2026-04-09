#!/usr/bin/env python3
"""
GEO (Generative Engine Optimization) module.

Generates a prompt block that instructs Claude to write content optimised
for AI search citation — Google AI Overviews, Perplexity, ChatGPT, Gemini.

Core principles (2026 GEO reality):
  - AI search engines fan out a single query into 8-12 sub-queries
  - 68% of AI-cited pages are NOT in the top 10 organic results
  - AI extracts at the passage level — every H2 must be a standalone answer unit
  - Speakable schema marks the exact passages AI crawlers should quote

Usage:
  from geo_optimize import get_full_geo_block

  block = get_full_geo_block(
      primary_keyword="best payid casinos australia",
      page_url="https://ssusa.co/guides/best-payid-casinos/",
      page_title="Best PayID Casinos Australia 2026",
      page_type="guide"  # guide | review | list | landing
  )
  # Inject block into Claude's content prompt
"""

from __future__ import annotations


# ── Query fan-out sub-queries per page type ──────────────────────────────────

_FAN_OUT_HINTS: dict[str, list[str]] = {
    "guide": [
        "What is [topic] and how does it work?",
        "Is [topic] safe and legal in Australia?",
        "How do I get started with [topic]?",
        "What are the best [topic] options in 2026?",
        "What fees or limits apply to [topic]?",
        "How fast is [topic] compared to alternatives?",
        "What are the pros and cons of [topic]?",
        "Which Australian banks / operators support [topic]?",
    ],
    "review": [
        "Is [casino] legit and safe for Australians?",
        "What welcome bonus does [casino] offer?",
        "How fast are [casino] withdrawals?",
        "Does [casino] accept PayID and crypto?",
        "What pokies and games does [casino] have?",
        "What is the wagering requirement at [casino]?",
        "Does [casino] have a mobile app?",
        "How do I contact [casino] customer support?",
    ],
    "list": [
        "Which casino ranks #1 for [topic]?",
        "What makes a casino good for [topic]?",
        "How do I choose the best [topic] casino?",
        "Are these [topic] casinos safe and licensed?",
        "What bonuses do [topic] casinos offer?",
        "What is the minimum deposit at [topic] casinos?",
        "How fast are withdrawals at [topic] casinos?",
        "Which [topic] casino is best for pokies?",
    ],
    "landing": [
        "What is [topic]?",
        "How does [topic] work in Australia?",
        "Is [topic] safe to use?",
        "What are the best [topic] options?",
        "How do I start using [topic]?",
    ],
}


def _fan_out_block(page_type: str, keyword: str) -> str:
    hints = _FAN_OUT_HINTS.get(page_type, _FAN_OUT_HINTS["guide"])
    lines = [f"  - {h.replace('[topic]', keyword).replace('[casino]', keyword)}" for h in hints]
    return "\n".join(lines)


def get_full_geo_block(
    primary_keyword: str,
    page_url: str,
    page_title: str,
    page_type: str = "guide",
) -> str:
    """
    Return a GEO optimisation prompt block to inject into Claude's content prompt.

    Args:
        primary_keyword: Target keyword (e.g. "best payid casinos australia")
        page_url:        Canonical URL of the page being generated
        page_title:      Page title (used in Speakable schema)
        page_type:       One of: guide | review | list | landing

    Returns:
        Multi-line string to append to the content generation prompt.
    """
    fan_out = _fan_out_block(page_type, primary_keyword)

    block = f"""
## GEO OPTIMISATION REQUIREMENTS (Generative Engine Optimisation — 2026)

**Target keyword**: {primary_keyword}
**Page URL**: {page_url}
**Page type**: {page_type}

### Why GEO matters
AI search engines (Google AI Overviews, Perplexity, ChatGPT, Gemini) fan out a single
query into 8-12 parallel sub-queries before composing an answer. 68% of AI-cited pages
are NOT in the top 10 organic results — depth and passage clarity matter more than rank.

### Query fan-out — sub-queries this page MUST answer:
{fan_out}

Each sub-query above must be answered SOMEWHERE on this page — either as a dedicated
H2 section or as a clear, self-contained paragraph.

### ATOMIC ANSWER BLOCKS (mandatory)
- Within the first 300 words: include a 40-60 word block that directly answers the
  primary query. Use definitive language: "The best PayID casinos in Australia in 2026
  are...". This block must contain one citable fact or statistic.
- After EACH major H2: open with a 1-2 sentence direct answer before expanding.
  Every H2 section must work as a standalone "answer unit" — someone reading only
  that section must get a complete, useful answer.

### H2 STRUCTURE FOR PASSAGE EXTRACTION
- Frame each H2 heading as if it IS the sub-query: "How Do PayID Casino Deposits Work?"
  not just "Deposits". AI systems match headings to user questions — make them explicit.
- First sentence under each H2 = direct answer (40-60 words max, definitive tone).
- Follow with supporting depth: data, comparisons, step-by-step where relevant.

### FAQ SECTION (mandatory, minimum 5 Q&As)
- Every FAQ question must mirror a likely AI search sub-query.
- Answers: 40-60 words each, authoritative, citable.
- Format for schema extraction: question-answer pairs only. No filler.
- Include FAQPage JSON-LD schema — this directly feeds AI Overview snippets.

### SPEAKABLE SCHEMA (include in JSON-LD)
Generate a SpeakableSpecification block targeting the atomic answer and FAQ sections:
```json
{{
  "@context": "https://schema.org",
  "@type": "SpeakableSpecification",
  "cssSelector": ["p.atomic-answer", "#faq .faq-answer", "h1 + p"]
}}
```
Add class="atomic-answer" to the opening answer paragraph so the selector works.

### ENTITY CLARITY
For every key entity mentioned (casino names, payment methods, game providers,
licensing bodies), include at least one clear attribute statement:
- "Stake96 is a [description] licensed under [license] and accepting Australian players"
- "PayID is an Australian real-time bank payment system operated by NPP Australia"
Explicit entity-attribute pairs help knowledge graphs and AI models cite you correctly.

### CONTENT QUALITY SIGNALS FOR AI CITATION
- Use definitive claims, not hedged ones ("is" not "may be", "takes X minutes" not "can take")
- Include at least 3 data points with dates: "as of April 2026", "updated Q2 2026"
- Use structured formats (comparison tables, numbered steps, bullet lists) — AI extracts
  structured data more reliably than prose
- Cite sources for statistics (even self-referential: "based on our testing")
- Mention the current year naturally in content — freshness is a citation signal

Incorporate ALL of the above. SEO structure takes priority over voice. Atomic answer
blocks stay authoritative and direct — humanise everything else.
"""
    return block.strip()


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "best payid casinos australia"
    pt = sys.argv[2] if len(sys.argv) > 2 else "guide"
    print(get_full_geo_block(
        primary_keyword=kw,
        page_url=f"https://ssusa.co/guides/{kw.replace(' ', '-')}/",
        page_title=f"{kw.title()} — AussiePokies96",
        page_type=pt,
    ))
