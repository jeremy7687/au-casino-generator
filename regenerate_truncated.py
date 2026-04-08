#!/usr/bin/env python3
"""
Regenerates the 8 truncated pages at max token limit with parallel workers.

Usage:
    python3 regenerate_truncated.py
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from generate_au import (
    SITE, DESIGN, KEYWORDS, casinos,
    call_claude, save_local,
    build_guide_crypto_prompt,
    build_guide_best_pokies_prompt,
    build_guide_no_deposit_prompt,
    build_guide_ewallet_prompt,
    build_banking_payid_prompt,
    build_banking_crypto_prompt,
    build_guide_best_online_pokies_prompt,
    build_guide_jili_prompt,
)

# Max tokens — Sonnet 4.6 supports 64k output
MAX_TOKENS = 64000

TRUNCATED_TASKS = [
    (build_guide_best_online_pokies_prompt(SITE, casinos, DESIGN, KEYWORDS), "guides/best-online-pokies-australia.html"),
    (build_guide_best_pokies_prompt(SITE, casinos, DESIGN, KEYWORDS),        "guides/best-pokies-australia.html"),
    (build_guide_crypto_prompt(SITE, casinos, DESIGN, KEYWORDS),             "guides/best-crypto-casinos.html"),
    (build_guide_ewallet_prompt(SITE, casinos, DESIGN, KEYWORDS),            "guides/best-e-wallet-pokies-australia.html"),
    (build_guide_no_deposit_prompt(SITE, casinos, DESIGN, KEYWORDS),         "guides/no-deposit-bonus.html"),
    (build_guide_jili_prompt(SITE, casinos, DESIGN, KEYWORDS),               "guides/how-to-play-jili-pokies.html"),
    (build_banking_crypto_prompt(SITE, casinos, DESIGN, KEYWORDS),           "banking/crypto-casino-deposits.html"),
    (build_banking_payid_prompt(SITE, casinos, DESIGN, KEYWORDS),            "banking/payid-casino-deposits.html"),
]


def generate_one(args):
    prompt, path = args
    start = time.time()
    html = call_claude(prompt, path, max_tokens=MAX_TOKENS)
    elapsed = time.time() - start
    save_local(html, path)
    closed = "</html>" in html.lower()
    print(f"   {'✅' if closed else '⚠️ '} {path} — {len(html):,} chars in {elapsed:.0f}s {'(complete)' if closed else '(still truncated?)'}")
    return path, html


print(f"\n⚡  Regenerating {len(TRUNCATED_TASKS)} truncated pages")
print(f"   max_tokens: {MAX_TOKENS:,} | workers: {len(TRUNCATED_TASKS)} parallel\n")

generated = {}
start_all = time.time()

with ThreadPoolExecutor(max_workers=8) as executor:
    futures = {executor.submit(generate_one, t): t[1] for t in TRUNCATED_TASKS}
    for future in as_completed(futures):
        try:
            path, html = future.result()
            generated[path] = html
        except Exception as e:
            print(f"   ❌ Failed: {futures[future]} — {e}")

elapsed_total = time.time() - start_all
print(f"\n✅  Done — {len(generated)}/{len(TRUNCATED_TASKS)} pages regenerated in {elapsed_total:.0f}s")
print(f"   Deploy: git add generated/ && git commit -m 'regen truncated pages' && git push")
