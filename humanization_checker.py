#!/usr/bin/env python3
"""
humanization_checker.py — AI Pattern Detector & Text Humanizer

Scans generated HTML files for detectable AI writing patterns:
- Overused AI words/phrases
- Uniform sentence length (no rhythm variation)
- Excessive adverb stacking
- Unnatural transition phrases
- Missing contractions in informal copy
- Repetitive paragraph openers

Usage:
    python3 humanization_checker.py                         # scan all pages
    python3 humanization_checker.py generated/reviews/stake96.html
    python3 humanization_checker.py --fix                   # auto-fix what can be fixed
    python3 humanization_checker.py --score                 # show humanization score per page
    python3 humanization_checker.py --report                # export humanization-report.json
"""

import json
import re
import sys
import datetime
from pathlib import Path
from collections import Counter

BASE      = Path(__file__).parent
GENERATED = BASE / "generated"

# ── AI Tell-tale Patterns ──────────────────────────────────────────────────

# Words/phrases that AI overuses — flag if >1 per page
AI_OVERUSED_WORDS = [
    "comprehensive", "robust", "leverage", "utilize", "utilise",
    "delve", "delves", "embark", "realm", "elevate", "elevates",
    "foster", "fosters", "cutting-edge", "seamless", "seamlessly",
    "it's worth noting", "it is worth noting", "in today's",
    "in conclusion", "in summary", "furthermore", "moreover",
    "additionally", "subsequently", "nevertheless", "notwithstanding",
    "paramount", "crucial", "pivotal", "transformative", "holistic",
    "synergy", "synergistic", "dynamic", "landscape", "ecosystem",
    "empower", "empowers", "showcase", "showcases", "facilitate",
    "facilitates", "ensure", "ensures", "streamline", "streamlines",
    "innovative", "state-of-the-art", "game-changing", "groundbreaking",
    "meticulous", "meticulously", "undeniably", "unquestionably",
    "intricacies", "nuanced", "multifaceted", "plethora",
    "testament to", "in the realm of", "at the forefront",
    "by leveraging", "moving forward", "going forward",
    "as we navigate", "in this day and age",
]

# Phrases that scream AI — flag any occurrence
AI_DEAD_GIVEAWAYS = [
    "as an ai", "as an artificial intelligence", "i cannot", "i am unable",
    "i don't have access", "based on my training", "my knowledge cutoff",
    "i must emphasize", "i want to make it clear", "it's important to note that",
    "please note that", "it is imperative", "one must consider",
    "in order to ensure", "with that being said", "having said that",
    "that being said", "needless to say", "it goes without saying",
    "without further ado", "dive deep into", "deep dive",
]

# Good contractions that SHOULD appear (absence is suspicious in informal copy)
CONTRACTIONS_EXPECTED = [
    ("do not", "don't"), ("it is", "it's"), ("you are", "you're"),
    ("they are", "they're"), ("we are", "we're"), ("will not", "won't"),
    ("cannot", "can't"), ("does not", "doesn't"), ("is not", "isn't"),
    ("are not", "aren't"), ("have not", "haven't"), ("would not", "wouldn't"),
]

# Transition phrases that indicate unnatural flow when overused
ROBOTIC_TRANSITIONS = [
    "first and foremost", "last but not least", "in light of",
    "with regard to", "with respect to", "in terms of",
    "it should be noted", "it can be seen", "it is clear that",
    "this allows for", "this enables", "this ensures",
    "one of the key", "one of the most important",
    "play a crucial role", "plays a key role",
]

# ── Text Extraction ────────────────────────────────────────────────────────

def extract_text(html: str) -> str:
    """Extract visible body text from HTML, strip tags."""
    # Remove script, style, head blocks
    html = re.sub(r'<(script|style|head)[^>]*>.*?</\1>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    # Remove JSON-LD blocks
    html = re.sub(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    # Strip all tags
    text = re.sub(r'<[^>]+>', ' ', html)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    # Simple sentence splitter — split on .!? followed by space+capital
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    return [s.strip() for s in sentences if len(s.strip()) > 15]


def extract_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs (rough — split on double newline or block boundary)."""
    return [p.strip() for p in re.split(r'\n\s*\n', text) if len(p.strip()) > 30]


# ── Checks ─────────────────────────────────────────────────────────────────

def check_overused_words(text: str) -> list[dict]:
    """Flag AI-overused words that appear more than once."""
    issues = []
    text_lower = text.lower()
    for word in AI_OVERUSED_WORDS:
        count = text_lower.count(word.lower())
        if count > 1:
            issues.append({"type": "overused_word", "word": word, "count": count,
                           "severity": "high" if count > 3 else "medium"})
    return issues


def check_dead_giveaways(text: str) -> list[dict]:
    """Flag absolute AI giveaway phrases."""
    issues = []
    text_lower = text.lower()
    for phrase in AI_DEAD_GIVEAWAYS:
        if phrase in text_lower:
            issues.append({"type": "ai_giveaway", "phrase": phrase, "severity": "critical"})
    return issues


def check_sentence_rhythm(text: str) -> list[dict]:
    """Flag monotonous sentence lengths — 5+ consecutive sentences of similar length."""
    sentences = extract_sentences(text)
    if len(sentences) < 6:
        return []

    issues = []
    word_counts = [len(s.split()) for s in sentences]

    # Check for 5+ consecutive sentences within 3 words of each other
    streak = 1
    for i in range(1, len(word_counts)):
        if abs(word_counts[i] - word_counts[i-1]) <= 3:
            streak += 1
            if streak >= 5:
                issues.append({
                    "type": "monotone_rhythm",
                    "message": f"{streak} consecutive sentences of similar length (~{word_counts[i]} words)",
                    "severity": "medium"
                })
                streak = 1  # Reset to avoid re-flagging same run
        else:
            streak = 1

    return issues


def check_missing_contractions(text: str) -> list[dict]:
    """Flag formal expansions that should be contractions in casual copy."""
    issues = []
    text_lower = text.lower()
    # Only flag if the formal form appears 3+ times
    for formal, contraction in CONTRACTIONS_EXPECTED:
        count = text_lower.count(formal)
        if count >= 3:
            issues.append({
                "type": "missing_contractions",
                "formal": formal,
                "preferred": contraction,
                "count": count,
                "severity": "low"
            })
    return issues


def check_robotic_transitions(text: str) -> list[dict]:
    """Flag overused robotic transition phrases."""
    issues = []
    text_lower = text.lower()
    for phrase in ROBOTIC_TRANSITIONS:
        count = text_lower.count(phrase)
        if count >= 2:
            issues.append({
                "type": "robotic_transition",
                "phrase": phrase,
                "count": count,
                "severity": "medium"
            })
    return issues


def check_paragraph_openers(text: str) -> list[dict]:
    """Flag repetitive paragraph openers."""
    paragraphs = extract_paragraphs(text)
    if len(paragraphs) < 4:
        return []

    openers = []
    for p in paragraphs:
        words = p.split()[:3]
        opener = " ".join(words).lower().rstrip(".,;:")
        openers.append(opener)

    counts = Counter(openers)
    issues = []
    for opener, count in counts.items():
        if count >= 3 and len(opener) > 3:
            issues.append({
                "type": "repetitive_opener",
                "opener": opener,
                "count": count,
                "severity": "medium"
            })
    return issues


def check_word_repetition(text: str) -> list[dict]:
    """Flag non-stop overuse of specific content words (casino-specific)."""
    words = re.findall(r'\b[a-z]{4,}\b', text.lower())
    total = len(words)
    if total < 100:
        return []

    counts = Counter(words)
    # Exclude stop words and expected casino terms
    exclude = {
        "that", "this", "with", "from", "have", "they", "your", "their",
        "when", "will", "also", "been", "more", "than", "into", "over",
        "some", "what", "where", "which", "while", "each", "most", "both",
        "casino", "pokies", "bonus", "payid", "australia", "aussie",
        "deposit", "withdrawal", "punters", "players", "online", "sites",
        "best", "good", "great", "free", "play", "real", "money", "time",
    }
    issues = []
    for word, count in counts.most_common(20):
        if word in exclude:
            continue
        frequency = count / total * 100
        if frequency > 2.5 and count > 8:  # >2.5% frequency
            issues.append({
                "type": "word_overuse",
                "word": word,
                "count": count,
                "frequency_pct": round(frequency, 1),
                "severity": "low"
            })
    return issues


# ── Auto-fix ───────────────────────────────────────────────────────────────

FIXABLE_REPLACEMENTS = {
    # Formal → casual contractions in paragraph text only
    " do not ": " don't ",
    " it is ": " it's ",
    " you are ": " you're ",
    " they are ": " they're ",
    " will not ": " won't ",
    " cannot ": " can't ",
    " does not ": " doesn't ",
    " is not ": " isn't ",
    " are not ": " aren't ",
    # Robotic transitions → casual
    "Furthermore, ": "Also, ",
    "Moreover, ": "And, ",
    "Additionally, ": "Plus, ",
    "Subsequently, ": "Then, ",
    "Nevertheless, ": "Still, ",
    "It should be noted that ": "",
    "It is important to note that ": "",
    "It is worth noting that ": "",
    "It's worth noting that ": "",
    # Overused words → simpler alternatives
    " utilize ": " use ",
    " utilise ": " use ",
    " leverage ": " use ",
    " facilitate ": " help ",
    " ensure ": " make sure ",
    " paramount ": " critical ",
    " pivotal ": " key ",
    " comprehensive ": " full ",
    " streamline ": " simplify ",
    " showcase ": " show ",
}


def auto_fix_html(html: str) -> tuple[str, int]:
    """Apply safe text replacements in paragraph content only. Returns (fixed_html, count)."""
    fixes = 0
    # Only fix inside <p>...</p> blocks to avoid breaking CSS/JS
    def fix_paragraph(m):
        nonlocal fixes
        content = m.group(0)
        for old, new in FIXABLE_REPLACEMENTS.items():
            count = content.count(old)
            if count > 0:
                content = content.replace(old, new)
                fixes += count
        return content

    html = re.sub(r'<p[^>]*>.*?</p>', fix_paragraph, html, flags=re.DOTALL | re.IGNORECASE)
    return html, fixes


# ── Scoring ────────────────────────────────────────────────────────────────

def humanization_score(issues: list[dict]) -> int:
    """Score 0-100 (100 = perfectly human). Deduct for each issue by severity."""
    deductions = {"critical": 25, "high": 10, "medium": 5, "low": 2}
    total = sum(deductions.get(i["severity"], 3) for i in issues)
    return max(0, 100 - total)


def score_label(score: int) -> str:
    if score >= 85:
        return "✅ Human-like"
    if score >= 70:
        return "⚠️  Somewhat AI"
    if score >= 50:
        return "🟠 Likely AI"
    return "🔴 AI-Detectable"


# ── Page Analysis ──────────────────────────────────────────────────────────

def analyse_page(path: Path) -> dict:
    html = path.read_text(encoding="utf-8", errors="ignore")
    text = extract_text(html)

    issues = []
    issues += check_dead_giveaways(text)
    issues += check_overused_words(text)
    issues += check_robotic_transitions(text)
    issues += check_missing_contractions(text)
    issues += check_sentence_rhythm(text)
    issues += check_paragraph_openers(text)
    issues += check_word_repetition(text)

    score = humanization_score(issues)
    return {
        "path": str(path.relative_to(GENERATED)) if path.is_absolute() and GENERATED in path.parents else str(path),
        "score": score,
        "label": score_label(score),
        "issue_count": len(issues),
        "issues": issues,
        "word_count": len(text.split()),
    }


def find_all_pages() -> list[Path]:
    return sorted(GENERATED.rglob("*.html"))


# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AI Pattern Checker & Humanization Validator")
    parser.add_argument("paths", nargs="*", help="Specific HTML file(s) to check")
    parser.add_argument("--fix",    action="store_true", help="Auto-fix detectable patterns in-place")
    parser.add_argument("--score",  action="store_true", help="Show score summary only")
    parser.add_argument("--report", action="store_true", help="Export humanization-report.json")
    parser.add_argument("--min-score", type=int, default=0, help="Only show pages below this score")
    args = parser.parse_args()

    # Determine target files
    if args.paths:
        pages = [Path(p) for p in args.paths if Path(p).exists()]
    else:
        pages = find_all_pages()

    if not pages:
        print("No HTML files found.")
        sys.exit(1)

    results = []
    print(f"\n🔍  Checking {len(pages)} page(s) for AI patterns...\n")

    for page in pages:
        result = analyse_page(page)
        results.append(result)

        if args.score:
            # Score-only mode: one line per page
            if result["score"] <= (args.min_score or 100):
                print(f"  {result['label']}  {result['score']:3d}/100  {result['path']}")
            continue

        if args.min_score and result["score"] >= args.min_score:
            continue

        # Full output
        print(f"{'─' * 60}")
        print(f"  {result['label']}  Score: {result['score']}/100  |  {result['path']}")
        print(f"  Words: {result['word_count']}  |  Issues: {result['issue_count']}")

        if result["issues"]:
            by_severity = {"critical": [], "high": [], "medium": [], "low": []}
            for issue in result["issues"]:
                by_severity[issue["severity"]].append(issue)

            for sev in ["critical", "high", "medium", "low"]:
                for issue in by_severity[sev]:
                    icon = {"critical": "🚨", "high": "🔴", "medium": "🟡", "low": "🔵"}[sev]
                    t = issue["type"]
                    if t == "overused_word":
                        print(f"    {icon} [{sev}] Overused: '{issue['word']}' × {issue['count']}")
                    elif t == "ai_giveaway":
                        print(f"    {icon} [{sev}] AI phrase: '{issue['phrase']}'")
                    elif t == "monotone_rhythm":
                        print(f"    {icon} [{sev}] {issue['message']}")
                    elif t == "missing_contractions":
                        print(f"    {icon} [{sev}] Use '{issue['preferred']}' not '{issue['formal']}' ({issue['count']}×)")
                    elif t == "robotic_transition":
                        print(f"    {icon} [{sev}] Robotic phrase: '{issue['phrase']}' × {issue['count']}")
                    elif t == "repetitive_opener":
                        print(f"    {icon} [{sev}] Repeated para opener: '{issue['opener']}' × {issue['count']}")
                    elif t == "word_overuse":
                        print(f"    {icon} [{sev}] Word '{issue['word']}' at {issue['frequency_pct']}% frequency ({issue['count']}×)")
        else:
            print("    ✓  No issues detected")
        print()

        # Auto-fix
        if args.fix and result["issues"]:
            html = page.read_text(encoding="utf-8", errors="ignore")
            fixed_html, fix_count = auto_fix_html(html)
            if fix_count > 0:
                page.write_text(fixed_html, encoding="utf-8")
                print(f"    🔧  Auto-fixed {fix_count} pattern(s) in {result['path']}")

    # Summary
    if results:
        avg_score = sum(r["score"] for r in results) / len(results)
        critical = [r for r in results if r["score"] < 50]
        warning  = [r for r in results if 50 <= r["score"] < 70]
        good     = [r for r in results if r["score"] >= 85]

        print(f"\n{'=' * 60}")
        print(f"  HUMANIZATION SUMMARY — {datetime.date.today()}")
        print(f"  Pages checked : {len(results)}")
        print(f"  Average score : {avg_score:.0f}/100")
        print(f"  ✅ Human-like  : {len(good)}")
        print(f"  ⚠️  Needs work  : {len(warning)}")
        print(f"  🔴 AI-detect   : {len(critical)}")
        print(f"{'=' * 60}\n")

        if args.report:
            report = {
                "generated": datetime.date.today().isoformat(),
                "summary": {
                    "pages_checked": len(results),
                    "avg_score": round(avg_score, 1),
                    "human_like": len(good),
                    "needs_work": len(warning),
                    "ai_detectable": len(critical),
                },
                "pages": sorted(results, key=lambda r: r["score"])
            }
            out = BASE / "humanization-report.json"
            out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
            print(f"  📄  Report saved: {out}")
