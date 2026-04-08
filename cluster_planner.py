#!/usr/bin/env python3
"""
cluster_planner.py — Topical Cluster Builder for AussiePokies96

Builds a pillar → spoke topic cluster map from the content registry,
identifies gaps in cluster coverage, and generates cross-linking
recommendations between related pages.

Usage:
    python3 cluster_planner.py              # show cluster map + gaps
    python3 cluster_planner.py --inject     # inject missing cross-links into HTML
    python3 cluster_planner.py --report     # export clusters.json
    python3 cluster_planner.py --queue      # add gap topics to content-queue.json
"""

import json
import re
import sys
import datetime
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
BASE        = Path(__file__).parent
REGISTRY    = BASE / "content-registry.json"
QUEUE       = BASE / "content-queue.json"
GENERATED   = BASE / "generated"
CLUSTERS_OUT = BASE / "clusters.json"

TODAY = datetime.date.today().isoformat()

# ── Cluster Definitions ────────────────────────────────────────────────────
# Each cluster has a pillar page + spokes + expected keywords per spoke.
# "missing_spokes" are planned pages not yet created.

CLUSTERS = [
    {
        "id": "payid",
        "name": "PayID Casinos",
        "pillar": "guides/best-payid-casinos.html",
        "pillar_url": "/guides/best-payid-casinos/",
        "spokes": [
            "banking/payid-casino-deposits.html",
            "blog/payid-vs-crypto-casino-deposits.html",
            "index.html",
        ],
        "missing_spokes": [
            {"topic": "PayID Casino Withdrawal Speed Comparison Australia 2026",
             "slug": "payid-casino-withdrawal-speed",
             "category": "guide",
             "keywords": ["payid casino withdrawal", "fastest payid withdrawal", "payid payout speed australia"]},
            {"topic": "PayID Casino Minimum Deposit Australia — All Sites Under $10",
             "slug": "payid-casino-minimum-deposit",
             "category": "guide",
             "keywords": ["payid casino minimum deposit", "minimum deposit payid casino au", "$10 payid casino"]},
            {"topic": "Are PayID Casinos Safe? Licences, Encryption & Player Protection",
             "slug": "are-payid-casinos-safe",
             "category": "guide",
             "keywords": ["are payid casinos safe", "payid casino safety", "payid casino licence australia"]},
        ],
        "internal_link_anchors": {
            "guides/best-payid-casinos.html":       ["best PayID casinos", "PayID casino guide", "top PayID casinos Australia"],
            "banking/payid-casino-deposits.html":   ["how PayID deposits work", "PayID casino deposits", "deposit with PayID"],
            "blog/payid-vs-crypto-casino-deposits.html": ["PayID vs crypto", "compare PayID and crypto deposits"],
        },
    },
    {
        "id": "pokies",
        "name": "Online Pokies",
        "pillar": "guides/best-pokies-australia.html",
        "pillar_url": "/guides/best-pokies-australia/",
        "spokes": [
            "guides/best-online-pokies-australia.html",
            "guides/how-to-play-pokies.html",
            "guides/how-to-play-aristocrat-pokies.html",
            "guides/how-to-play-jili-pokies.html",
            "guides/how-to-play-booongo-pokies.html",
        ],
        "missing_spokes": [
            {"topic": "Best Megaways Pokies Australia 2026 — Top Sites & Titles",
             "slug": "best-megaways-pokies-australia",
             "category": "guide",
             "keywords": ["megaways pokies australia", "best megaways slots au", "megaways online pokies"]},
            {"topic": "Pokies RTP Explained — How Return to Player Works in Australia",
             "slug": "pokies-rtp-explained",
             "category": "guide",
             "keywords": ["pokies rtp australia", "return to player pokies", "best rtp pokies au"]},
            {"topic": "Free Pokies No Download Australia — Play Instantly in Browser",
             "slug": "free-pokies-no-download",
             "category": "guide",
             "keywords": ["free pokies no download", "free online pokies australia", "play pokies free browser"]},
        ],
        "internal_link_anchors": {
            "guides/best-pokies-australia.html":          ["best pokies Australia", "top pokies sites"],
            "guides/best-online-pokies-australia.html":   ["best online pokies", "online pokies Australia"],
            "guides/how-to-play-pokies.html":             ["how to play pokies", "pokies guide"],
            "guides/how-to-play-aristocrat-pokies.html":  ["Aristocrat pokies", "how to play Aristocrat"],
            "guides/how-to-play-jili-pokies.html":        ["JILI pokies", "JILI games Australia"],
            "guides/how-to-play-booongo-pokies.html":     ["Booongo pokies", "Booongo games"],
        },
    },
    {
        "id": "crypto",
        "name": "Crypto Casinos",
        "pillar": "guides/best-crypto-casinos.html",
        "pillar_url": "/guides/best-crypto-casinos/",
        "spokes": [
            "banking/crypto-casino-deposits.html",
            "blog/payid-vs-crypto-casino-deposits.html",
        ],
        "missing_spokes": [
            {"topic": "No KYC Crypto Casino Australia 2026 — Anonymous Play Guide",
             "slug": "no-kyc-crypto-casino-australia",
             "category": "guide",
             "keywords": ["no kyc casino australia", "anonymous crypto casino au", "no verification casino australia"]},
            {"topic": "Solana Casino Australia 2026 — Fastest Crypto Withdrawals",
             "slug": "solana-casino-australia",
             "category": "guide",
             "keywords": ["solana casino australia", "sol casino au", "fastest crypto casino withdrawal"]},
            {"topic": "Bitcoin Casino Australia 2026 — BTC Deposit & Withdrawal Guide",
             "slug": "bitcoin-casino-australia",
             "category": "guide",
             "keywords": ["bitcoin casino australia", "btc casino au", "bitcoin pokies australia"]},
        ],
        "internal_link_anchors": {
            "guides/best-crypto-casinos.html":       ["best crypto casinos", "crypto casino Australia"],
            "banking/crypto-casino-deposits.html":   ["crypto casino deposits", "how to deposit crypto"],
        },
    },
    {
        "id": "bonuses",
        "name": "Casino Bonuses",
        "pillar": "guides/no-deposit-bonus.html",
        "pillar_url": "/guides/no-deposit-bonus/",
        "spokes": [
            "guides/fast-payout-casinos.html",
        ],
        "missing_spokes": [
            {"topic": "Best Casino Welcome Bonus Australia 2026 — Top 10 Offers Compared",
             "slug": "best-casino-welcome-bonus-australia",
             "category": "guide",
             "keywords": ["casino welcome bonus australia", "best casino bonus au 2026", "top casino signup bonus"]},
            {"topic": "Low Wagering Casino Australia — Under 30x Requirements",
             "slug": "low-wagering-casino-australia",
             "category": "guide",
             "keywords": ["low wagering casino australia", "casino low wagering requirements", "30x wagering casino au"]},
            {"topic": "Casino Free Spins No Deposit Australia 2026 — Verified Offers",
             "slug": "casino-free-spins-no-deposit-australia",
             "category": "guide",
             "keywords": ["free spins no deposit australia", "casino free spins au", "no deposit free spins 2026"]},
        ],
        "internal_link_anchors": {
            "guides/no-deposit-bonus.html":    ["no deposit bonus", "casino no deposit offer"],
            "guides/fast-payout-casinos.html": ["fast payout casinos", "fastest withdrawal casinos"],
        },
    },
    {
        "id": "ewallet",
        "name": "E-Wallet Casinos",
        "pillar": "guides/best-e-wallet-pokies-australia.html",
        "pillar_url": "/guides/best-e-wallet-pokies-australia/",
        "spokes": [
            "banking/ewallet-casino-deposits.html",
        ],
        "missing_spokes": [
            {"topic": "Skrill Casino Australia 2026 — Deposits, Withdrawals & Best Sites",
             "slug": "skrill-casino-australia",
             "category": "guide",
             "keywords": ["skrill casino australia", "skrill online casino au", "skrill pokies deposit"]},
            {"topic": "Neteller Casino Australia 2026 — Top Pokies Sites Accepting Neteller",
             "slug": "neteller-casino-australia",
             "category": "guide",
             "keywords": ["neteller casino australia", "neteller pokies au", "casino accepting neteller"]},
        ],
        "internal_link_anchors": {
            "guides/best-e-wallet-pokies-australia.html": ["best e-wallet pokies", "e-wallet casino Australia"],
            "banking/ewallet-casino-deposits.html":       ["e-wallet casino deposits", "how to use e-wallet"],
        },
    },
    {
        "id": "reviews",
        "name": "Casino Reviews Hub",
        "pillar": "index.html",
        "pillar_url": "/",
        "spokes": [
            "reviews/stake96.html", "reviews/spin2u.html", "reviews/spinza96.html",
            "reviews/stakebro77.html", "reviews/sage96.html", "reviews/shuffle96.html",
            "reviews/wowza96.html", "reviews/pokiespin96.html",
        ],
        "missing_spokes": [],
        "internal_link_anchors": {
            "index.html": ["best online casinos Australia", "top PayID casinos", "casino comparison"],
        },
    },
]


# ── Helpers ────────────────────────────────────────────────────────────────

def load_registry() -> list:
    data = json.loads(REGISTRY.read_text())
    return data if isinstance(data, list) else data.get("pages", [])


def page_exists(path: str) -> bool:
    return (GENERATED / path).exists()


def get_page_html(path: str) -> str | None:
    p = GENERATED / path
    return p.read_text(encoding="utf-8") if p.exists() else None


def find_anchor_for_cluster(html: str, cluster_id: str, target_url: str) -> int:
    """Find the best insertion point for a cross-link in the HTML.
    Returns character index for insertion, or -1 if already linked."""
    if target_url in html:
        return -1  # already linked
    # Prefer: last </p> before FAQ section
    faq_idx = html.find('id="faq"')
    if faq_idx > 0:
        last_p = html.rfind("</p>", 0, faq_idx)
        if last_p > 0:
            return last_p + 4
    # Fallback: last </p> before </main> or </article>
    for tag in ["</main>", "</article>", "</body>"]:
        idx = html.rfind(tag)
        if idx > 0:
            last_p = html.rfind("</p>", 0, idx)
            if last_p > 0:
                return last_p + 4
    return -1


def inject_cross_link(html: str, target_url: str, anchor_text: str, context: str) -> str:
    """Inject a cross-link sentence after the last paragraph before the FAQ."""
    insert_at = find_anchor_for_cluster(html, "", target_url)
    if insert_at == -1:
        return html  # already linked or no good position

    link_sentence = (
        f'\n<p class="cluster-xlink" style="margin-top:0.5rem">'
        f'→ <a href="{target_url}" class="text-link">{anchor_text}</a> — {context}</p>'
    )
    return html[:insert_at] + link_sentence + html[insert_at:]


# ── Analysis ───────────────────────────────────────────────────────────────

def analyse_clusters(registry: list) -> dict:
    """Return cluster coverage stats: which spokes exist, which are missing."""
    existing_paths = {p["path"] for p in registry}
    results = {}

    for cluster in CLUSTERS:
        present  = [s for s in cluster["spokes"] if s in existing_paths]
        absent   = [s for s in cluster["spokes"] if s not in existing_paths]
        coverage = len(present) / max(len(cluster["spokes"]), 1) * 100

        results[cluster["id"]] = {
            "name":           cluster["name"],
            "pillar":         cluster["pillar"],
            "pillar_exists":  cluster["pillar"] in existing_paths,
            "spokes_present": present,
            "spokes_absent":  absent,
            "missing_spokes": cluster["missing_spokes"],
            "coverage_pct":   round(coverage),
            "gap_count":      len(absent) + len(cluster["missing_spokes"]),
        }

    return results


def print_cluster_report(analysis: dict):
    print("\n" + "=" * 70)
    print("  TOPICAL CLUSTER REPORT")
    print(f"  Generated: {TODAY}")
    print("=" * 70)

    total_gaps = 0
    for cid, c in analysis.items():
        status = "✅" if c["coverage_pct"] == 100 and not c["missing_spokes"] else "⚠️"
        print(f"\n{status}  [{c['coverage_pct']}%] {c['name'].upper()}")
        print(f"   Pillar : {c['pillar']} {'✓' if c['pillar_exists'] else '✗ MISSING'}")
        for s in c["spokes_present"]:
            print(f"   Spoke  : ✓ {s}")
        for s in c["spokes_absent"]:
            print(f"   Spoke  : ✗ {s}  ← MISSING FROM REGISTRY")
        for ms in c["missing_spokes"]:
            print(f"   Gap    : ✗ {ms['slug']}  ← NOT YET CREATED")
        total_gaps += c["gap_count"] + len(c["missing_spokes"])

    print(f"\n{'=' * 70}")
    print(f"  Total content gaps: {total_gaps}")
    print("  Run with --queue to add gaps to content-queue.json")
    print("  Run with --inject to add cross-links between existing pages")
    print("=" * 70 + "\n")


# ── Cross-link Injection ───────────────────────────────────────────────────

def inject_all_cross_links(registry: list, dry_run: bool = False) -> int:
    """For each cluster, ensure every spoke links back to the pillar
    and the pillar links to each spoke. Returns count of injections."""
    injected = 0
    reg_map  = {p["path"]: p for p in registry}

    for cluster in CLUSTERS:
        pillar_path = cluster["pillar"]
        pillar_url  = cluster["pillar_url"]
        pillar_html = get_page_html(pillar_path)
        if not pillar_html:
            print(f"  ⚠️   Pillar not found: {pillar_path}")
            continue

        # 1. Ensure each spoke links TO the pillar
        for spoke_path in cluster["spokes"]:
            if spoke_path == pillar_path:
                continue
            spoke_html = get_page_html(spoke_path)
            if not spoke_html:
                continue
            anchors = cluster["internal_link_anchors"].get(pillar_path, [cluster["name"]])
            anchor  = anchors[0]
            context = f"Full guide to {cluster['name'].lower()} for Aussie punters."
            if pillar_url not in spoke_html:
                if not dry_run:
                    updated = inject_cross_link(spoke_html, pillar_url, anchor, context)
                    (GENERATED / spoke_path).write_text(updated, encoding="utf-8")
                print(f"  🔗  {spoke_path} → {pillar_url}  [{anchor}]")
                injected += 1

        # 2. Ensure pillar links TO each spoke
        for spoke_path in cluster["spokes"]:
            if spoke_path == pillar_path:
                continue
            spoke_reg = reg_map.get(spoke_path)
            if not spoke_reg:
                continue
            spoke_url = spoke_reg.get("url", f"/{spoke_path.replace('.html', '/')}")
            anchors   = cluster["internal_link_anchors"].get(spoke_path, [spoke_reg.get("title", spoke_path)])
            anchor    = anchors[0]
            context   = spoke_reg.get("title", "")
            if spoke_url not in pillar_html:
                if not dry_run:
                    pillar_html = inject_cross_link(pillar_html, spoke_url, anchor, context)
                    (GENERATED / pillar_path).write_text(pillar_html, encoding="utf-8")
                print(f"  🔗  {pillar_path} → {spoke_url}  [{anchor}]")
                injected += 1

    return injected


# ── Queue Missing Spokes ───────────────────────────────────────────────────

def add_gaps_to_queue(analysis: dict):
    """Add all missing spoke topics to content-queue.json."""
    try:
        q = json.loads(QUEUE.read_text())
    except Exception:
        q = {"queue": []}

    existing_slugs = {item["slug"] for item in q.get("queue", [])}
    added = 0

    # Calculate next available publish date (Mon/Wed/Fri)
    pub_date = datetime.date.today()
    def next_publish_day(d):
        while d.weekday() not in (0, 2, 4):  # Mon=0, Wed=2, Fri=4
            d += datetime.timedelta(days=1)
        return d

    # Find last queued date to append after
    if q.get("queue"):
        dates = [item.get("publish_date","") for item in q["queue"] if item.get("status") == "pending"]
        if dates:
            pub_date = datetime.date.fromisoformat(max(dates)) + datetime.timedelta(days=1)
    pub_date = next_publish_day(pub_date)

    for cid, c in analysis.items():
        cluster = next(cl for cl in CLUSTERS if cl["id"] == cid)
        for ms in cluster["missing_spokes"]:
            if ms["slug"] in existing_slugs:
                continue
            q["queue"].append({
                "slug":         ms["slug"],
                "topic":        ms["topic"],
                "keywords":     ms["keywords"],
                "category":     ms.get("category", "guide"),
                "cluster":      cid,
                "status":       "pending",
                "publish_date": pub_date.isoformat(),
                "source":       "cluster_planner",
            })
            print(f"  ➕  Queued: {ms['slug']} ({pub_date})")
            added += 1
            pub_date = next_publish_day(pub_date + datetime.timedelta(days=1))

    QUEUE.write_text(json.dumps(q, indent=2, ensure_ascii=False))
    print(f"\n  ✅  {added} gap topics added to content-queue.json")


# ── Export clusters.json ───────────────────────────────────────────────────

def export_clusters_json(analysis: dict):
    CLUSTERS_OUT.write_text(json.dumps(analysis, indent=2, ensure_ascii=False))
    print(f"  📄  Exported: {CLUSTERS_OUT}")


# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Topical Cluster Planner")
    parser.add_argument("--inject",  action="store_true", help="Inject cross-links into existing pages")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be injected, don't write")
    parser.add_argument("--report",  action="store_true", help="Export clusters.json")
    parser.add_argument("--queue",   action="store_true", help="Add missing spokes to content-queue.json")
    args = parser.parse_args()

    registry = load_registry()
    analysis = analyse_clusters(registry)
    print_cluster_report(analysis)

    if args.inject or args.dry_run:
        label = "DRY RUN — " if args.dry_run else ""
        print(f"\n{label}Injecting cross-links between cluster pages...\n")
        count = inject_all_cross_links(registry, dry_run=args.dry_run)
        print(f"\n  {'Would inject' if args.dry_run else 'Injected'} {count} cross-links")

    if args.report:
        export_clusters_json(analysis)

    if args.queue:
        print("\nAdding missing spokes to content queue...\n")
        add_gaps_to_queue(analysis)
