#!/usr/bin/env python3
"""
Generates only the remaining pages — skips index.html and the 8 reviews.
Run this when index + reviews are already done.

Usage:
    export ANTHROPIC_API_KEY='sk-ant-...'
    export GITHUB_TOKEN='github_pat_...'
    python3 generate_remaining.py
"""

import sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from generate_au import (
    SITE, DESIGN, KEYWORDS, casinos, GITHUB_REPO,
    call_claude, save_local, push_files_to_github,
    generate_sitemap, generate_robots,
    build_about_prompt, build_privacy_prompt, build_terms_prompt,
    build_guide_payid_prompt, build_guide_crypto_prompt,
    build_guide_best_pokies_prompt, build_guide_fast_payout_prompt,
    build_guide_no_deposit_prompt, build_guide_ewallet_prompt,
    build_guide_pokies_prompt, build_banking_payid_prompt,
    build_banking_crypto_prompt, build_banking_ewallet_prompt,
    build_guide_best_online_pokies_prompt, build_guide_aristocrat_prompt,
    build_guide_jili_prompt, build_guide_booongo_prompt,
)

tasks = [
    (build_about_prompt(SITE, casinos, DESIGN, KEYWORDS),    "about.html",              12000),
    (build_privacy_prompt(SITE, DESIGN),                     "privacy-policy.html",     10000),
    (build_terms_prompt(SITE, DESIGN),                       "terms-conditions.html",   10000),
    (build_guide_payid_prompt(SITE, casinos, DESIGN, KEYWORDS),              "guides/best-payid-casinos.html",             64000),
    (build_guide_crypto_prompt(SITE, casinos, DESIGN, KEYWORDS),             "guides/best-crypto-casinos.html",            64000),
    (build_guide_best_pokies_prompt(SITE, casinos, DESIGN, KEYWORDS),        "guides/best-pokies-australia.html",          64000),
    (build_guide_fast_payout_prompt(SITE, casinos, DESIGN, KEYWORDS),        "guides/fast-payout-casinos.html",            64000),
    (build_guide_no_deposit_prompt(SITE, casinos, DESIGN, KEYWORDS),         "guides/no-deposit-bonus.html",               64000),
    (build_guide_ewallet_prompt(SITE, casinos, DESIGN, KEYWORDS),            "guides/best-e-wallet-pokies-australia.html", 64000),
    (build_guide_pokies_prompt(SITE, casinos, DESIGN, KEYWORDS),             "guides/how-to-play-pokies.html",             64000),
    (build_banking_payid_prompt(SITE, casinos, DESIGN, KEYWORDS),            "banking/payid-casino-deposits.html",         64000),
    (build_banking_crypto_prompt(SITE, casinos, DESIGN, KEYWORDS),           "banking/crypto-casino-deposits.html",        64000),
    (build_banking_ewallet_prompt(SITE, casinos, DESIGN, KEYWORDS),          "banking/ewallet-casino-deposits.html",       64000),
    (build_guide_best_online_pokies_prompt(SITE, casinos, DESIGN, KEYWORDS), "guides/best-online-pokies-australia.html",   64000),
    (build_guide_aristocrat_prompt(SITE, casinos, DESIGN, KEYWORDS),         "guides/how-to-play-aristocrat-pokies.html",  64000),
    (build_guide_jili_prompt(SITE, casinos, DESIGN, KEYWORDS),               "guides/how-to-play-jili-pokies.html",        64000),
    (build_guide_booongo_prompt(SITE, casinos, DESIGN, KEYWORDS),            "guides/how-to-play-booongo-pokies.html",     64000),
]

def generate_one(args):
    prompt, path, max_tok = args
    html = call_claude(prompt, path, max_tokens=max_tok)
    save_local(html, path)
    return path, html

generated_files = {}

print(f"\n⚡  Generating {len(tasks)} pages in parallel (8 workers)...\n")
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = {}
    for t in tasks:
        futures[executor.submit(generate_one, t)] = t[1]
        time.sleep(3)
    for future in as_completed(futures):
        path, html = future.result()
        generated_files[path] = html
        print(f"   ✓  {path}")

# ── Sitemap & Robots ──
print("\n🗺️   Generating sitemap.xml...")
sitemap = generate_sitemap(SITE, casinos)
save_local(sitemap, "sitemap.xml")
generated_files["sitemap.xml"] = sitemap

print("🤖  Generating robots.txt...")
robots = generate_robots(SITE)
save_local(robots, "robots.txt")
generated_files["robots.txt"] = robots

print(f"\n✅  {len(generated_files)} files generated.")
print(f"    Local preview: open generated/about.html in your browser.\n")

push = input("Push all files to GitHub now? (y/n): ").strip().lower()
if push == "y":
    push_files_to_github(generated_files)
else:
    print("⏸️   Skipped. Review generated/ then re-run to push.")
