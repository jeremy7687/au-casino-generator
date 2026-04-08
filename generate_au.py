#!/usr/bin/env python3
"""
Casino Affiliate Multi-Page Generator — Australia Market
Generates index.html + 8 individual review pages via Claude API,
then pushes all files to GitHub (auto-deployed by Cloudflare Pages).

Prerequisites:
    pip install anthropic PyGithub

Environment variables required:
    ANTHROPIC_API_KEY   — from console.anthropic.com
    GITHUB_TOKEN        — fine-grained PAT with Contents read/write
"""

import anthropic
import argparse
import datetime
import json
import os
import random
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from github import Github, GithubException


# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────


GITHUB_REPO = "jeremy7687/au-casino-generator"
MODEL = "claude-sonnet-4-6"
FAST_MODEL = "claude-haiku-4-5-20251001"  # 3-5× faster streaming for reviews

SITE = {
    "brand": "AussiePokies96",
    "domain": "https://ssusa.co",
    "author": "Blake Donovan",
    "author_bio": "Blake has reviewed Australian online casinos since 2019, specialising in payout speed and pokie variety.",
    "year": 2026,
    "twitter": "@AussiePokies96",
    "email": "editor@ssusa.co",
}

# Design tokens — consistent across all pages
DESIGN = {
    "bg":       "#09090f",
    "card_bg":  "#111520",
    "border":   "#1d2235",
    "gold":     "#f8bc2e",
    "green":    "#00d97e",   # vivid CTA green — higher CTR than muted green
    "red":      "#ff4757",   # HOT / urgency badges
    "text":     "#edf0f7",
    "muted":    "#7a85a0",
    "font_head": "Barlow Condensed",
    "font_body": "Inter",
}

TODAY        = datetime.date.today().isoformat()                          # e.g. "2026-04-08"
YEAR         = datetime.date.today().year                                  # e.g. 2026
TODAY_PRETTY = datetime.date.today().strftime("%-d %B %Y")                # e.g. "8 April 2026"

# ── Page dates registry: stores original datePublished per page ──
_page_dates_path = Path(__file__).parent / "page_dates.json"
_page_dates: dict = json.load(open(_page_dates_path)) if _page_dates_path.exists() else {}

def _get_page_dates(path: str) -> tuple[str, str]:
    """Return (datePublished, dateModified) for a page path.
    - index.html always gets TODAY for both (homepage stays fresh).
    - All other pages: datePublished = original first-publish date (never changes),
      dateModified = TODAY (updated whenever the page is regenerated).
    - New pages not yet in registry: datePublished = TODAY (first generation).
    """
    if path == "index.html":
        return TODAY, TODAY
    entry = _page_dates.get(path, {})
    pub = entry.get("published", TODAY)
    return pub, TODAY

def _register_page_date(path: str):
    """Record a new page's publish date if not already registered. Saves to disk."""
    if path == "index.html" or path in _page_dates:
        return
    _page_dates[path] = {"published": TODAY}
    with open(_page_dates_path, "w") as f:
        json.dump(_page_dates, f, indent=2, sort_keys=True)

# Cost tracking
_token_usage = {"input": 0, "output": 0, "calls": 0, "cost_usd": 0.0}
_PRICING = {
    MODEL:       {"input": 3.0,  "output": 15.0},   # Sonnet 4.6 per million tokens
    FAST_MODEL:  {"input": 0.8,  "output":  4.0},   # Haiku 4.5 per million tokens
}


# ─────────────────────────────────────────────
# SEO KEYWORDS — Australia Market
# ─────────────────────────────────────────────

# Load keywords from keywords-au.json so this file and the JSON stay in sync
_kw_path = Path(__file__).parent / "keywords-au.json"
with open(_kw_path, encoding="utf-8") as _f:
    _kw_data = json.load(_f)

# Flatten JSON structure into the flat lists the prompts expect
KEYWORDS = {
    "primary": [e["keyword"] for e in _kw_data["keywords"]["primary"]],
    "long_tail": [e["keyword"] for e in _kw_data["keywords"]["long_tail"]],
    # Include all 7 informational keywords — "[casino name] review Australia" is a
    # template pattern: each review page targets "[CasinoName] review Australia"
    "informational": [e["keyword"] for e in _kw_data["keywords"]["informational"]],
    # Rules derived from strategic_notes + content enforcement rules
    "rules": _kw_data["strategic_notes"] + [
        "Use 'punters' not 'players', 'pokies' not 'slots', 'fast payouts' not 'quick withdrawals'.",
        "Solana (SOL) is a rising AU withdrawal method — mention alongside BTC/ETH where relevant.",
        "Each review page must target '[CasinoName] review Australia' as its primary long-tail keyword — include in <title>, H1, and meta description.",
    ],
}


# ─────────────────────────────────────────────
# CASINO DATA — Australia Market 2026
# ─────────────────────────────────────────────

casinos = [
    {
        "rank": 1,
        "id": "stake96",
        "name": "Stake96 Casino",
        "slug": "stake96",
        "bonus": "Up to $10,000 + 600 Free Spins",
        "bonus_detail": "100% match across first 5 deposits up to $10,000 total + 600 free spins on top pokies",
        "wagering": "35x",
        "min_deposit": "$20",
        "score": 9.9,
        "score_breakdown": {
            "Pokies Library": 9.9,
            "Payout Speed": 9.9,
            "Bonus Value": 9.8,
            "Mobile Experience": 9.7,
            "Support": 9.8,
        },
        "tags": ["10,000+ Pokies", "Fast PayID", "Live Dealer"],
        "affiliate_url": "https://stake96.com/",
        "review_url": "/reviews/stake96/",
        "pros": [
            "10,000+ pokies from top AU providers",
            "PayID payouts processed in under 5 minutes",
            "24/7 live dealer tables including AU-friendly hours",
            "5-deposit welcome structure — sustained bankroll boost",
        ],
        "cons": [
            "No dedicated iOS/Android app",
            "35x wagering requirement on bonus funds",
        ],
        "review_summary": "Stake96 sets the standard for Aussie punters in 2026. Ten thousand pokies, lightning-fast PayID payouts under five minutes, and a $10,000 welcome package spread across five deposits make it our undisputed #1 pick.",
        "unique_feature": "Australia's largest pokie library at 10,000+ titles — nothing else comes close.",
        "best_for": "Pokies variety and fast PayID payouts",
        "rating_count": 312,
    },
    {
        "rank": 2,
        "id": "spin2u",
        "name": "Spin2U Casino",
        "slug": "spin2u",
        "bonus": "Up to $20,000 + 500 Free Spins",
        "bonus_detail": "Massive 4-deposit welcome package — $5,000 per deposit up to $20,000 total + 500 free spins",
        "wagering": "38x",
        "min_deposit": "$25",
        "score": 9.8,
        "score_breakdown": {
            "Pokies Library": 9.6,
            "Payout Speed": 9.7,
            "Bonus Value": 9.9,
            "Mobile Experience": 9.8,
            "Support": 9.7,
        },
        "tags": ["Biggest Bonus", "VIP Program", "Crypto OK"],
        "affiliate_url": "https://spin2u.com/",
        "review_url": "/reviews/spin2u/",
        "pros": [
            "$20,000 welcome bonus — largest on list",
            "Dedicated VIP account manager from day one",
            "Crypto (BTC, ETH, SOL) and AUD accepted",
            "4-deposit structure maximises long-term bankroll",
        ],
        "cons": [
            "38x wagering — slightly above average",
            "KYC required before first withdrawal",
        ],
        "review_summary": "For punters focused on raw bankroll size, Spin2U is unmatched. The $20,000 welcome package across four deposits and a dedicated VIP programme make it the go-to for high rollers who want maximum opening value.",
        "unique_feature": "Largest welcome bonus on the AU market at $20,000 — second place isn't close.",
        "best_for": "High rollers maximising their opening bankroll",
        "rating_count": 247,
    },
    {
        "rank": 3,
        "id": "spinza96",
        "name": "Spinza96 Casino",
        "slug": "spinza96",
        "bonus": "$3,000 + 200 Free Spins — No KYC",
        "bonus_detail": "100% first deposit match up to $3,000 + 200 free spins — no identity verification ever required",
        "wagering": "30x",
        "min_deposit": "$10",
        "score": 9.8,
        "score_breakdown": {
            "Pokies Library": 9.5,
            "Payout Speed": 9.9,
            "Bonus Value": 9.7,
            "Mobile Experience": 9.8,
            "Support": 9.6,
        },
        "tags": ["No KYC", "Instant Bitcoin", "Anonymous Play"],
        "affiliate_url": "https://spinza96.com/",
        "review_url": "/reviews/spinza96/",
        "pros": [
            "Zero KYC — register and play anonymously",
            "Bitcoin withdrawals processed in minutes",
            "Lowest wagering on list at 30x",
            "$10 minimum deposit — lowest barrier to entry",
        ],
        "cons": [
            "Crypto only — no AUD fiat banking",
            "Smaller game library compared to top two",
        ],
        "review_summary": "Spinza96 is the top pick for crypto-first punters who value privacy. Zero KYC, instant Bitcoin payouts, and the lowest wagering requirement on our list at 30x make it the fastest anonymous option in the AU market.",
        "unique_feature": "No KYC ever — fully anonymous play with instant Bitcoin withdrawals.",
        "best_for": "Crypto punters who want privacy and speed",
        "rating_count": 189,
    },
    {
        "rank": 4,
        "id": "stakebro77",
        "name": "StakeBro77 Casino",
        "slug": "stakebro77",
        "bonus": "Up to $7,500 + 350 Free Spins",
        "bonus_detail": "Welcome package across first 3 deposits up to $7,500 total + 350 free spins on pokies",
        "wagering": "35x",
        "min_deposit": "$20",
        "score": 9.7,
        "score_breakdown": {
            "Pokies Library": 9.6,
            "Payout Speed": 9.8,
            "Bonus Value": 9.6,
            "Mobile Experience": 9.7,
            "Support": 9.7,
        },
        "tags": ["Sportsbook", "PayID", "AUD Accepted"],
        "affiliate_url": "https://stakebro77.com/",
        "review_url": "/reviews/stakebro77/",
        "pros": [
            "Full sportsbook — AFL, NRL, cricket, UFC and more",
            "Native AUD banking with instant PayID deposits",
            "7,000+ pokies from premium providers",
            "Fully mobile-optimised — no app needed",
        ],
        "cons": [
            "Live dealer selection smaller than #1 and #2",
            "Welcome bonus split across 3 deposits only",
        ],
        "review_summary": "StakeBro77 is the best single-login solution for punters who want casino and sports in one place. The sportsbook covers every major Aussie code alongside 7,000+ pokies — all with instant PayID banking.",
        "unique_feature": "Full sportsbook covering AFL, NRL, cricket and UFC — no switching accounts.",
        "best_for": "Punters who want casino and sports under one login",
        "rating_count": 203,
    },
    {
        "rank": 5,
        "id": "sage96",
        "name": "Sage96 Casino",
        "slug": "sage96",
        "bonus": "Up to $5,000 + 300 Free Spins",
        "bonus_detail": "100% match on first two deposits up to $5,000 total + 300 free spins on selected pokies",
        "wagering": "35x",
        "min_deposit": "$20",
        "score": 9.6,
        "score_breakdown": {
            "Pokies Library": 9.5,
            "Payout Speed": 9.6,
            "Bonus Value": 9.5,
            "Mobile Experience": 9.6,
            "Support": 9.7,
        },
        "tags": ["Weekly Cashback", "Loyalty Rewards", "Fast Payouts"],
        "affiliate_url": "https://sage96.com/",
        "review_url": "/reviews/sage96/",
        "pros": [
            "Weekly cashback on losses — up to 15%",
            "Loyalty points redeemable for real cash",
            "Fast PayID payouts, typically same day",
            "Regular reload bonuses for existing punters",
        ],
        "cons": [
            "Welcome bonus smaller than top 3",
            "Weekly cashback capped at $500",
        ],
        "review_summary": "Sage96 shines for regular punters who grind long sessions. The weekly cashback scheme and loyalty rewards system deliver ongoing value that beats one-time welcome bonuses for consistent Aussie players.",
        "unique_feature": "15% weekly cashback on losses — the best ongoing value for regular punters.",
        "best_for": "Regular grinders who want ongoing cashback value",
        "rating_count": 167,
    },
    {
        "rank": 6,
        "id": "shuffle96",
        "name": "Shuffle96 Casino",
        "slug": "shuffle96",
        "bonus": "250% up to $6,000 + 400 Free Spins",
        "bonus_detail": "250% first deposit match up to $6,000 — highest match percentage on our list — plus 400 free spins",
        "wagering": "40x",
        "min_deposit": "$20",
        "score": 9.5,
        "score_breakdown": {
            "Pokies Library": 9.4,
            "Payout Speed": 9.5,
            "Bonus Value": 9.8,
            "Mobile Experience": 9.4,
            "Support": 9.5,
        },
        "tags": ["250% Match", "Sportsbook", "AUD"],
        "affiliate_url": "https://shuffle96.com/",
        "review_url": "/reviews/shuffle96/",
        "pros": [
            "250% match rate — highest percentage on the list",
            "Full sportsbook alongside casino",
            "AUD accepted with PayID banking",
            "Daily promotions and weekly tournaments",
        ],
        "cons": [
            "40x wagering is above average",
            "Bonus T&Cs more complex than rivals",
        ],
        "review_summary": "Shuffle96 offers the highest bonus match rate on our list at 250% — if you want to stretch a single deposit into maximum play money, this is your pick. Daily promos and a full sportsbook add long-term value.",
        "unique_feature": "250% welcome match — the highest rate of any AU casino on this list.",
        "best_for": "Punters who want maximum match on their first deposit",
        "rating_count": 143,
    },
    {
        "rank": 7,
        "id": "wowza96",
        "name": "Wowza96 Casino",
        "slug": "wowza96",
        "bonus": "Up to $8,000 + 450 Free Spins",
        "bonus_detail": "Welcome package across first 4 deposits up to $8,000 + 450 free spins on premium pokies",
        "wagering": "40x",
        "min_deposit": "$25",
        "score": 9.3,
        "score_breakdown": {
            "Pokies Library": 9.3,
            "Payout Speed": 9.2,
            "Bonus Value": 9.4,
            "Mobile Experience": 9.3,
            "Support": 9.4,
        },
        "tags": ["Live Casino", "Premium Pokies", "VIP"],
        "affiliate_url": "https://wowza96.com/",
        "review_url": "/reviews/wowza96/",
        "pros": [
            "Premium live casino tables with real AU-friendly dealers",
            "Strong VIP programme with dedicated perks",
            "Wide payment options including PayID and crypto",
            "Regular prize pool tournaments",
        ],
        "cons": [
            "40x wagering — above industry average",
            "Interface less intuitive than top-ranked rivals",
        ],
        "review_summary": "Wowza96 stands out for its premium live casino floor and exclusive VIP programme. If live dealer pokies and high-stakes tournaments are your priority, Wowza96 delivers the experience.",
        "unique_feature": "Premium live dealer floor with AU-friendly hours and real-time table availability.",
        "best_for": "Live casino enthusiasts and VIP-tier players",
        "rating_count": 118,
    },
    {
        "rank": 8,
        "id": "pokiespin96",
        "name": "PokieSpin96 Casino",
        "slug": "pokiespin96",
        "bonus": "200% up to $15,000 + 50 Super Spins",
        "bonus_detail": "200% first deposit match up to $15,000 + 50 Super Spins on premium pokies — second largest max bonus on list",
        "wagering": "45x",
        "min_deposit": "$10",
        "score": 9.1,
        "score_breakdown": {
            "Pokies Library": 9.0,
            "Payout Speed": 9.2,
            "Bonus Value": 9.5,
            "Mobile Experience": 9.0,
            "Support": 9.1,
        },
        "tags": ["20+ Cryptos", "No KYC", "$15K Max Bonus"],
        "affiliate_url": "https://pokiespin96.com/",
        "review_url": "/reviews/pokiespin96/",
        "pros": [
            "Supports 20+ cryptocurrencies including BTC, ETH, SOL, XRP",
            "No KYC verification required — play anonymously",
            "Second largest max bonus on the list at $15,000",
            "Instant crypto deposits, zero fees",
        ],
        "cons": [
            "45x wagering — highest on the list",
            "Crypto only — no AUD fiat banking",
        ],
        "review_summary": "PokyeSpin96 is built for crypto whales. With 20+ supported coins, no KYC, and a $15,000 max bonus at 200%, it is the best option for high-volume crypto punters who prioritise anonymity over wagering flexibility.",
        "unique_feature": "Accepts 20+ cryptocurrencies including altcoins most AU casinos won't touch.",
        "best_for": "Crypto whales wanting max bonus value with no KYC",
        "rating_count": 97,
    },
    {
        "rank": 9,
        "id": "ricky96",
        "name": "Ricky96 Casino",
        "slug": "ricky96",
        "bonus": "$7,500 + 550 Free Spins + $25 No Deposit",
        "bonus_detail": "Exclusive $25 no-deposit bonus on sign-up + 100% match up to $7,500 + 550 free spins across first 3 deposits",
        "wagering": "35x",
        "min_deposit": "$20",
        "score": 6.2,
        "score_breakdown": {
            "Pokies Library": 6.5,
            "Payout Speed": 6.0,
            "Bonus Value": 6.8,
            "Mobile Experience": 6.1,
            "Support": 5.6,
        },
        "tags": ["No Deposit Bonus", "PayID", "550 Free Spins"],
        "affiliate_url": "https://ricky96.com/",
        "review_url": "/reviews/ricky96/",
        "hot": True,
        "new": False,
        "pros": [
            "$25 no-deposit bonus — play before you deposit",
            "550 free spins across 3 deposits — most spins on list",
            "PayID withdrawals processed same day",
            "Strong reload bonus calendar for existing players",
        ],
        "cons": [
            "No-deposit bonus has 50x wagering",
            "Live chat support slower than top-ranked rivals",
        ],
        "review_summary": "Ricky96 is the no-deposit bonus leader in the AU market — $25 free on sign-up before you risk a cent. Add 550 free spins across three deposits and same-day PayID payouts and you have one of the most complete packages for new punters.",
        "unique_feature": "$25 no-deposit bonus on registration — try the casino risk-free before depositing.",
        "best_for": "New punters wanting to test before depositing",
        "rating_count": 214,
        "recommended": False,
        "not_recommended_reason": "High 50x wagering on no-deposit bonus, slow support, limited transparency on withdrawal processing times.",
    },
    {
        "rank": 10,
        "id": "luckystar96",
        "name": "LuckyStar96 Casino",
        "slug": "luckystar96",
        "bonus": "Up to $6,000 + 300 Free Spins",
        "bonus_detail": "100% match on first 3 deposits up to $2,000 each ($6,000 total) + 300 free spins on Pragmatic Play pokies",
        "wagering": "33x",
        "min_deposit": "$15",
        "score": 5.8,
        "score_breakdown": {
            "Pokies Library": 6.0,
            "Payout Speed": 5.5,
            "Bonus Value": 6.2,
            "Mobile Experience": 6.1,
            "Support": 5.2,
        },
        "tags": ["Low Wagering", "Pragmatic Play", "Mobile First"],
        "affiliate_url": "https://luckystar96.com/",
        "review_url": "/reviews/luckystar96/",
        "hot": False,
        "new": True,
        "pros": [
            "33x wagering — one of the lowest on list",
            "Pragmatic Play exclusives including Gates of Olympus",
            "Best-in-class mobile experience — fully optimised",
            "$15 minimum deposit — low barrier to entry",
        ],
        "cons": [
            "Smaller live dealer selection than top 5",
            "No sportsbook",
        ],
        "review_summary": "LuckyStar96 punches above its weight with 33x wagering and a mobile experience that rivals dedicated apps. Pragmatic Play's full library — including AU favourites like Gates of Olympus and Sweet Bonanza — makes it a go-to for pokie enthusiasts.",
        "unique_feature": "Best mobile interface of any AU casino in our rankings — no app needed.",
        "best_for": "Mobile players and Pragmatic Play pokie fans",
        "rating_count": 134,
        "recommended": False,
        "not_recommended_reason": "No sportsbook, limited live dealer selection, customer support response times lag behind top-ranked alternatives.",
    },
    {
        "rank": 11,
        "id": "ozwin96",
        "name": "Ozwin96 Casino",
        "slug": "ozwin96",
        "bonus": "400% up to $4,000 + 100 Free Spins",
        "bonus_detail": "400% first deposit match up to $4,000 — highest match percentage for AUD deposits — plus 100 free spins",
        "wagering": "30x",
        "min_deposit": "$10",
        "score": 6.5,
        "score_breakdown": {
            "Pokies Library": 6.2,
            "Payout Speed": 6.8,
            "Bonus Value": 6.5,
            "Mobile Experience": 6.3,
            "Support": 6.7,
        },
        "tags": ["400% Match", "AUD Focused", "Low Wagering"],
        "affiliate_url": "https://ozwin96.com/",
        "review_url": "/reviews/ozwin96/",
        "hot": False,
        "new": False,
        "pros": [
            "400% match — highest AUD bonus rate on the list",
            "30x wagering — joint lowest on list",
            "AUD-native banking — no conversion fees",
            "$10 minimum deposit accepted",
        ],
        "cons": [
            "Smaller game library than top 5",
            "Bonus max cap of $4,000 limits high rollers",
        ],
        "review_summary": "Ozwin96 is Australia-built for Australian punters — AUD-native banking, no currency conversion fees, and the highest match percentage on our list at 400%. The joint-lowest 30x wagering makes it a genuine contender for best value deposit bonus.",
        "unique_feature": "400% first deposit match in AUD — no conversion fees, no catch.",
        "best_for": "AUD-first punters wanting maximum match percentage",
        "rating_count": 108,
        "recommended": False,
        "not_recommended_reason": "Smaller game library, bonus capped at $4,000, limited payment options compared to our top-ranked casinos.",
    },
    {
        "rank": 12,
        "id": "fairgo96",
        "name": "FairGo96 Casino",
        "slug": "fairgo96",
        "bonus": "$1,000 + 200 Free Spins — Weekly Cashback",
        "bonus_detail": "100% match up to $1,000 + 200 free spins + 10% weekly cashback on net losses — ongoing value for regular players",
        "wagering": "25x",
        "min_deposit": "$10",
        "score": 5.5,
        "score_breakdown": {
            "Pokies Library": 5.2,
            "Payout Speed": 5.8,
            "Bonus Value": 5.5,
            "Mobile Experience": 5.6,
            "Support": 5.4,
        },
        "tags": ["25x Wagering", "Weekly Cashback", "AU Support"],
        "affiliate_url": "https://fairgo96.com/",
        "review_url": "/reviews/fairgo96/",
        "hot": False,
        "new": False,
        "pros": [
            "25x wagering — lowest on the entire list",
            "10% weekly cashback with no cap",
            "Australian customer support team",
            "Aussie Rules and NRL promotions",
        ],
        "cons": [
            "Welcome bonus cap lower than rivals",
            "Smaller pokies library",
        ],
        "review_summary": "FairGo96 earns its name — the lowest wagering requirement on our entire list at 25x and a no-cap weekly cashback deal make it the fairest ongoing proposition for regular Aussie punters who grind sessions week after week.",
        "unique_feature": "25x wagering — the lowest of any AU casino we've reviewed. No fine print.",
        "best_for": "Bonus-savvy punters who prioritise the lowest wagering",
        "rating_count": 176,
        "recommended": False,
        "not_recommended_reason": "Welcome bonus cap too low, smaller pokies library, lacks crypto payment options available at our recommended sites.",
    },
    {
        "rank": 13,
        "id": "bizzo96",
        "name": "Bizzo96 Casino",
        "slug": "bizzo96",
        "bonus": "Up to $8,000 + 200 Free Spins",
        "bonus_detail": "150% match on first 4 deposits up to $2,000 each ($8,000 total) + 200 free spins on live pokies",
        "wagering": "40x",
        "min_deposit": "$20",
        "score": 6.8,
        "score_breakdown": {
            "Pokies Library": 6.9,
            "Payout Speed": 6.5,
            "Bonus Value": 6.8,
            "Mobile Experience": 7.0,
            "Support": 6.8,
        },
        "tags": ["Live Pokies", "PayID + Crypto", "8,000+ Games"],
        "affiliate_url": "https://bizzo96.com/",
        "review_url": "/reviews/bizzo96/",
        "hot": False,
        "new": True,
        "pros": [
            "8,000+ games including live dealer pokies",
            "Accepts both PayID and crypto simultaneously",
            "150% match across 4 deposits — sustained value",
            "Fast 24/7 live chat support",
        ],
        "cons": [
            "40x wagering above market average",
            "New to AU market — less player reviews",
        ],
        "review_summary": "Bizzo96 brings an 8,000+ game library — one of the largest on this list — with the rare combination of PayID and crypto banking under one account. The 4-deposit welcome structure keeps your bankroll topped up longer than single-deposit rivals.",
        "unique_feature": "8,000+ games including live dealer pokies — biggest combined library on list.",
        "best_for": "Game variety seekers who want PayID and crypto in one place",
        "rating_count": 89,
        "recommended": False,
        "not_recommended_reason": "Above-average 40x wagering, new to AU market with limited player track record, withdrawal processing inconsistent.",
    },
    {
        "rank": 14,
        "id": "kingbilly96",
        "name": "KingBilly96 Casino",
        "slug": "kingbilly96",
        "bonus": "Up to $5,000 + 250 Free Spins",
        "bonus_detail": "200% first deposit match up to $1,000 + $4,000 across next 3 deposits + 250 free spins",
        "wagering": "35x",
        "min_deposit": "$20",
        "score": 6.4,
        "score_breakdown": {
            "Pokies Library": 6.5,
            "Payout Speed": 6.2,
            "Bonus Value": 6.6,
            "Mobile Experience": 6.5,
            "Support": 6.2,
        },
        "tags": ["200% First Deposit", "VIP Kingdom", "Jackpot Pokies"],
        "affiliate_url": "https://kingbilly96.com/",
        "review_url": "/reviews/kingbilly96/",
        "hot": False,
        "new": False,
        "pros": [
            "200% first deposit match — highest rate outside Shuffle96",
            "Dedicated VIP 'Kingdom' loyalty programme",
            "Jackpot pokie selection including progressive slots",
            "Weekly tournaments with guaranteed prize pools",
        ],
        "cons": [
            "Support response time slower on weekends",
            "Jackpot games excluded from welcome bonus spins",
        ],
        "review_summary": "KingBilly96 rules for jackpot hunters and loyalty seekers. The 200% first deposit match kickstarts your bankroll and the VIP Kingdom programme rewards consistent play with real perks — cashback, faster withdrawals, and dedicated support.",
        "unique_feature": "Progressive jackpot pokie selection — the best jackpot range of any AU casino reviewed.",
        "best_for": "Jackpot hunters and players who want a loyalty programme with real perks",
        "rating_count": 121,
        "recommended": False,
        "not_recommended_reason": "Weekend support gaps, jackpot games excluded from bonus spins, payout speeds trail our top 8 picks.",
    },
    {
        "rank": 15,
        "id": "playamo96",
        "name": "PlayAmo96 Casino",
        "slug": "playamo96",
        "bonus": "Up to $1,500 + 150 Free Spins",
        "bonus_detail": "100% match up to $1,500 + 150 free spins across first 4 deposits — plus daily free spins via PlayAmo Club",
        "wagering": "50x",
        "min_deposit": "$10",
        "score": 5.9,
        "score_breakdown": {
            "Pokies Library": 6.1,
            "Payout Speed": 5.5,
            "Bonus Value": 5.8,
            "Mobile Experience": 6.4,
            "Support": 5.7,
        },
        "tags": ["Daily Free Spins", "Crypto Native", "6,000+ Pokies"],
        "affiliate_url": "https://playamo96.com/",
        "review_url": "/reviews/playamo96/",
        "hot": False,
        "new": False,
        "pros": [
            "6,000+ pokies including exclusives",
            "Daily free spins via PlayAmo Club membership",
            "Crypto native — BTC, ETH, LTC accepted instantly",
            "Fast account verification — under 10 minutes",
        ],
        "cons": [
            "50x wagering — highest standard rate on list",
            "Welcome bonus smaller than mid-tier rivals",
        ],
        "review_summary": "PlayAmo96 compensates for its smaller welcome bonus with a 6,000+ game library and daily free spins through its Club membership. For crypto-first punters who log in daily, the drip-feed of free spins adds up to more long-term value than a single big bonus.",
        "unique_feature": "Daily free spins via PlayAmo Club — the only AU casino giving free spins every single day.",
        "best_for": "Daily players who value consistent free spins over one-time bonuses",
        "rating_count": 156,
        "recommended": False,
        "not_recommended_reason": "Highest wagering on list at 50x, smaller welcome bonus than rivals, bonus terms overly restrictive for Australian players.",
    },
]


# ─────────────────────────────────────────────
# DAILY BADGE + POSITION SHUFFLE
# ─────────────────────────────────────────────

_BADGES = ["HOT 🔥", "NEW", "EDITOR'S PICK", "EXCLUSIVE"]

def _apply_daily_badges_and_shuffle(casinos: list) -> list:
    """
    Each day (date-seeded for consistency within a day):
    - Shuffles the order of the 8 recommended casinos
    - Assigns one of 4 badges to each casino (cycling, no repeats within the 8)
    - Updates display rank (position 1-8) without touching original 'rank' field
    Not-recommended casinos are left in place at the end.
    """
    today_seed = int(TODAY.replace("-", ""))
    rng = random.Random(today_seed)

    recommended = [c for c in casinos if c.get("recommended", True)]
    not_recommended = [c for c in casinos if not c.get("recommended", True)]

    # Shuffle recommended order
    rng.shuffle(recommended)

    # Assign badges — exactly 2 of each badge type across the 8 casinos
    badges = (_BADGES * (len(recommended) // len(_BADGES)))[:len(recommended)]
    rng.shuffle(badges)
    for i, c in enumerate(recommended):
        c = dict(c)  # don't mutate the original
        c["display_rank"] = i + 1
        c["badge"] = badges[i]
        recommended[i] = c

    return recommended + not_recommended


# ─────────────────────────────────────────────
# PROMPT BUILDERS
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# PRE-RENDERED HTML HELPERS (guaranteed content)
# ─────────────────────────────────────────────

def _stars(score: float) -> str:
    full = min(5, round(score / 2))
    return "★" * full + "☆" * (5 - full)


def _badge_html(badge: str) -> str:
    """Return styled badge HTML for the 4 badge types."""
    badge_map = {
        "HOT 🔥":        ('<span class="card-badge badge-hot">HOT 🔥</span>', ),
        "NEW":           ('<span class="card-badge badge-new">NEW</span>', ),
        "EDITOR'S PICK": ('<span class="card-badge badge-editors">EDITOR\'S PICK</span>', ),
        "EXCLUSIVE":     ('<span class="card-badge badge-exclusive">EXCLUSIVE</span>', ),
    }
    return badge_map.get(badge, ("",))[0]


def _casino_grid_html(casinos: list) -> str:
    cards = []
    # casinos list is already shuffled+badged by _apply_daily_badges_and_shuffle
    for c in [x for x in casinos if x.get("recommended", True)]:
        disp_rank = c.get("display_rank", c["rank"])
        rank_cls = f"rank-{disp_rank}" if disp_rank <= 3 else "rank-other"
        badge = _badge_html(c.get("badge", ""))
        tags = "".join(f'<span class="tag">{t}</span>' for t in c["tags"])
        cards.append(f"""    <article class="casino-card" aria-label="{c['name']} — Rank {disp_rank}" itemscope itemtype="https://schema.org/Casino">
      <meta itemprop="name" content="{c['name']}">
      <meta itemprop="url" content="/reviews/{c['slug']}/">
      <div itemprop="aggregateRating" itemscope itemtype="https://schema.org/AggregateRating" style="display:none">
        <meta itemprop="ratingValue" content="{c['score']}">
        <meta itemprop="bestRating" content="10">
        <meta itemprop="ratingCount" content="{c['rating_count']}">
      </div>
      <div class="rank-badge {rank_cls}">{disp_rank}</div>
      {badge}
      <div class="card-logo">
        <img loading="lazy" src="/assets/logos/{c['slug']}.png" alt="{c['name']} logo" onerror="this.style.display='none';this.nextElementSibling.style.display='block'">
        <div class="logo-fallback">{c['name'].split()[0]}</div>
      </div>
      <div class="card-name"><a href="/reviews/{c['slug']}/">{c['name']}</a></div>
      <div class="card-bonus">{c['bonus']}</div>
      <div class="card-wagering">Wagering: {c['wagering']}</div>
      <div class="card-tags">{tags}</div>
      <div class="card-score">
        <span class="score-num" itemprop="aggregateRating" itemscope itemtype="https://schema.org/AggregateRating"><span itemprop="ratingValue">{c['score']}</span></span><span class="score-denom">/10</span>
        <div class="stars">{_stars(c['score'])}</div>
      </div>
      <a href="{c['affiliate_url']}" class="cta-btn" rel="nofollow noopener sponsored" target="_blank" aria-label="Play at {c['name']}">Play Now →</a>
      <a href="/reviews/{c['slug']}/" class="review-link">Read Review</a>
    </article>""")
    return "\n".join(cards)


def _comparison_table_html(casinos: list) -> str:
    rows = []
    for c in [x for x in casinos if x.get("recommended", True)][:5]:
        rows.append(f"""        <tr>
          <td class="comp-rank">{c['rank']}</td>
          <td><strong><a href="/reviews/{c['slug']}/">{c['name']}</a></strong><br><small style="color:var(--muted)">{c['best_for']}</small></td>
          <td class="comp-bonus">{c['bonus']}</td>
          <td class="comp-wager">{c['wagering']}</td>
          <td class="comp-score">{c['score']}/10</td>
          <td><a href="{c['affiliate_url']}" class="comp-play" rel="nofollow noopener sponsored" target="_blank">Play Now</a></td>
        </tr>""")
    return "\n".join(rows)


def _review_blocks_html(casinos: list) -> str:
    labels = ["#1 Editor's Choice — Best Overall", "#2 Best Welcome Bonus", "#3 Best for Crypto Punters"]
    blocks = []
    for i, c in enumerate([x for x in casinos if x.get("recommended", True)][:3]):
        pros = "".join(f"<li>{p}</li>" for p in c["pros"])
        cons = "".join(f"<li>{p}</li>" for p in c["cons"])
        blocks.append(f"""  <article class="review-block" aria-label="{c['name']} review">
    <div class="review-header">
      <div>
        <div class="review-rank-label">{labels[i]}</div>
        <div class="review-name"><a href="/reviews/{c['slug']}/">{c['name']}</a></div>
      </div>
      <div class="review-score-wrap">
        <div class="review-score">{c['score']}</div>
        <div class="review-score-label">out of 10</div>
        <div class="stars">{_stars(c['score'])}</div>
      </div>
    </div>
    <div class="review-bonus-box">
      <div class="blabel">Welcome Offer</div>
      <div class="btext">{c['bonus']}</div>
      <div class="bnote">{c['bonus_detail']} · {c['wagering']} wagering · T&amp;Cs apply · 18+</div>
    </div>
    <p class="review-summary">{c['review_summary']} Licensed offshore casino legally accepting Australian players.</p>
    <div class="pros-cons">
      <div class="pros-box">
        <div class="pc-title">Pros</div>
        <ul>{pros}</ul>
      </div>
      <div class="cons-box">
        <div class="pc-title">Cons</div>
        <ul>{cons}</ul>
      </div>
    </div>
    <div class="review-cta-row">
      <a href="{c['affiliate_url']}" class="review-cta" rel="nofollow noopener sponsored" target="_blank">Play at {c['name'].split()[0]} →</a>
      <a href="/reviews/{c['slug']}/" class="review-read">Full Review</a>
    </div>
    <p class="review-disc">18+ · Licensed offshore casino legally accepting Australian players · Please gamble responsibly</p>
  </article>""")
    return "\n".join(blocks)


def _payid_casinos(casinos: list) -> list:
    """Return top 5 casinos confirmed to support PayID — deterministic filter."""
    def _has_payid(c):
        tag_str = " ".join(c["tags"]).lower()
        pros_str = " ".join(c["pros"]).lower()
        return "payid" in tag_str or "payid" in pros_str
    return [c for c in casinos if _has_payid(c)][:5]


def _payid_casino_cards_html(payid_casinos: list) -> str:
    """Pre-rendered casino cards for PayID-specific pages — guaranteed top 5."""
    cards = []
    for c in payid_casinos:
        rank_cls = f"rank-{c['rank']}" if c['rank'] <= 3 else "rank-other"
        hot = '<span class="hot-badge">HOT 🔥</span>' if c.get("hot") else ""
        tags = "".join(f'<span class="tag">{t}</span>' for t in c["tags"])
        cards.append(f"""    <article class="casino-card" aria-label="{c['name']} — Rank {c['rank']}">
      <div class="rank-badge {rank_cls}">{c['rank']}</div>
      {hot}
      <span class="payid-verified-badge">✓ PayID</span>
      <div class="card-logo">
        <img loading="lazy" src="/assets/logos/{c['slug']}.png" alt="{c['name']} logo" onerror="this.style.display='none';this.nextElementSibling.style.display='block'">
        <div class="logo-fallback">{c['name'].split()[0]}</div>
      </div>
      <div class="card-name"><a href="/reviews/{c['slug']}/">{c['name']}</a></div>
      <div class="card-bonus">{c['bonus']}</div>
      <div class="card-wagering">Wagering: {c['wagering']} · Min: {c['min_deposit']}</div>
      <div class="card-tags">{tags}</div>
      <div class="card-score">
        <span class="score-num">{c['score']}</span><span class="score-denom">/10</span>
        <div class="stars">{_stars(c['score'])}</div>
      </div>
      <a href="{c['affiliate_url']}" class="cta-btn" rel="nofollow noopener sponsored" target="_blank" aria-label="Play at {c['name']}">Claim Bonus →</a>
      <a href="/reviews/{c['slug']}/" class="review-link">Read Full Review</a>
    </article>""")
    return "\n".join(cards)


def _payid_withdrawal_table_html(payid_casinos: list) -> str:
    """Pre-rendered PayID withdrawal times table using real casino data."""
    rows = []
    for c in payid_casinos:
        # Stake96 and StakeBro77 have explicit "under 5 min" language
        tag_str = " ".join(c["tags"]).lower()
        if "fast payid" in tag_str or c["rank"] == 1:
            w_time, badge = "Under 5 min", '<span class="speed-fast">INSTANT</span>'
        elif c["score_breakdown"].get("Payout Speed", 9.0) >= 9.7:
            w_time, badge = "Under 5 min", '<span class="speed-fast">FAST</span>'
        elif c["score_breakdown"].get("Payout Speed", 9.0) >= 9.5:
            w_time, badge = "5–15 min", '<span class="speed-fast">FAST</span>'
        else:
            w_time, badge = "Same day", '<span class="speed-med">SAME DAY</span>'
        rows.append(f"""      <tr>
        <td><strong><a href="/reviews/{c['slug']}/">{c['name']}</a></strong></td>
        <td>{c['min_deposit']}</td>
        <td>Instant</td>
        <td>{w_time} {badge}</td>
        <td>Free</td>
        <td><a href="{c['affiliate_url']}" class="comp-play" rel="nofollow noopener sponsored" target="_blank">Play Now</a></td>
      </tr>""")
    return "\n".join(rows)


def _payid_faq_schema(site: dict, payid_casinos: list) -> str:
    """Pre-rendered FAQPage JSON-LD for PayID guide pages."""
    top = payid_casinos[0]
    names = ", ".join(c["name"] for c in payid_casinos[:3])
    faqs = [
        ("What is PayID and how does it work at Australian online casinos?",
         "PayID is Australia's instant bank transfer system built on the New Payments Platform (NPP). At online casinos, PayID lets you send funds directly from your bank account to the casino in seconds — no card, no third-party account needed. Deposits are free and arrive instantly. Supported by CommBank, ANZ, NAB, Westpac and 90+ other Australian banks."),
        (f"Which is the best PayID casino in Australia in {site['year']}?",
         f"{top['name']} is our top-rated PayID casino in Australia for {site['year']}, scoring {top['score']}/10. It offers {top['bonus']} and PayID withdrawals processed in under 5 minutes. Other top PayID casinos include {names}."),
        ("How do I deposit with PayID at an online casino?",
         "1. Log in and go to the Cashier or Deposit section. 2. Select PayID as your payment method. 3. Copy the casino's PayID address (phone number, email or ABN). 4. Open your banking app and send the amount to that PayID. 5. Funds arrive in your casino account within seconds. Deposits are free and available 24/7."),
        ("How fast are PayID casino withdrawals in Australia?",
         f"The fastest PayID casinos process withdrawals in under 5 minutes. {top['name']} consistently delivers PayID payouts in under 5 minutes. PayID withdrawals use the NPP real-time rails — once the casino approves the payment, it reaches your bank account almost immediately, 24/7 including weekends and public holidays."),
        ("Are PayID casino deposits safe in Australia?",
         "Yes. PayID transactions use bank-level encryption and never expose your BSB or account number to the casino — only your PayID alias (phone number or email) is shared. The NPP is regulated by the Reserve Bank of Australia. Deposits and withdrawals are processed through your own bank, adding an extra security layer."),
    ]
    entities = []
    for q, a in faqs:
        a_esc = a.replace('"', '\\"')
        entities.append(f"""      {{
        "@type": "Question",
        "name": "{q}",
        "acceptedAnswer": {{"@type": "Answer", "text": "{a_esc}"}}
      }}""")
    return ('{\n    "@context": "https://schema.org",\n    "@type": "FAQPage",\n'
            '    "mainEntity": [\n' + ",\n".join(entities) + "\n    ]\n  }")


def _faq_html(casinos: list) -> str:
    top = casinos[0]
    biggest_bonus = max(casinos, key=lambda c: c["score"])
    crypto_pick = next((c for c in casinos if "No KYC" in " ".join(c["tags"])), casinos[2])
    lowest_wager = min(casinos, key=lambda c: int(c["wagering"].replace("x", "")))
    fastest_payid = next((c for c in casinos if "PayID" in " ".join(c["tags"])), casinos[0])

    items = [
        ("Is online gambling legal in Australia?",
         f"Yes — it is legal for Australian players to gamble at online casinos. The Interactive Gambling Act 2001 (IGA) restricts <em>operators</em> from offering services to Australians, but it does not make it illegal for individual <em>players</em> to access offshore casino sites. All casinos on this list are licensed offshore operators legally accepting Australian players."),

        (f"What is the best online casino Australia for real money in {casinos[0].get('score', '9.9').__class__.__name__ and 2026}?",
         f"{top['name']} is our top-rated pick for the best online casino Australia real money in 2026 — scoring {top['score']}/10. It offers {top['unique_feature']} For the biggest bonus, {biggest_bonus['name']}'s {biggest_bonus['bonus']} package leads the list. For crypto punters, {crypto_pick['name']}'s {crypto_pick['unique_feature']}"),

        ("How do I deposit with PayID at an online casino?",
         "1. Log in and go to the Cashier or Deposit section.<br>2. Select PayID as your payment method.<br>3. Copy the casino's PayID (usually a phone number or email).<br>4. Open your banking app and send funds to that PayID.<br>5. Funds arrive within seconds — no fees, available 24/7. PayID deposits are supported by all major Australian banks including CommBank, ANZ, NAB and Westpac."),

        ("Are pokies winnings taxed in Australia?",
         "No. Recreational gambling winnings — including online pokies — are not taxed in Australia. The ATO does not treat gambling as a profession for most players, so winnings are not assessable income. Professional gamblers may be assessed differently, but this applies to very few individuals."),

        ("How do wagering requirements work?",
         f"Wagering requirements specify how many times you must bet your bonus before withdrawing winnings. Example: a $100 bonus at 35x means you must wager $3,500 before cashing out. Lower is better — {lowest_wager['name']} has the lowest on our list at {lowest_wager['wagering']}. Always check which games contribute toward the wagering total."),

        ("Which PayID casino offers a no deposit bonus in Australia?",
         "PayID casino no deposit bonuses are offered by select AU-facing casinos as sign-up incentives. Availability changes regularly — check each casino's promotions page for current offers. Search 'payid pokies no deposit australia' or 'no deposit payid casino australia' for the latest deals, and always read the T&Cs before claiming."),

        ("Can I use an e-wallet at Australian online casinos for pokies?",
         "Yes. E-wallet casino options in Australia include PayID (fastest — instant, free), POLi (direct bank transfer, no third-party account needed), Skrill, and Neteller. PayID is the most recommended e-wallet for online pokies in Australia — it's instant, free, and natively Australian."),

        (f"What is the best crypto casino in Australia with no KYC?",
         f"{crypto_pick['name']} is our top pick for best crypto casino Australia no KYC — {crypto_pick['unique_feature']} These are ideal for Aussie players who value privacy and speed without standard KYC documentation."),

        (f"Which casinos offer instant PayID pokies in Australia?",
         f"{fastest_payid['name']} is our benchmark for instant PayID pokies Australia — {fastest_payid['unique_feature']} PayID uses the New Payments Platform (NPP) for real-time transfers 24/7 including weekends and public holidays."),

        ("What is the best PayID pokies sign up bonus in Australia?",
         f"The best PayID pokies sign up bonus depends on your goal. Largest total: {casinos[1]['name']} ({casinos[1]['bonus']}). Best value/lowest wagering: {lowest_wager['name']} ({lowest_wager['bonus']} at {lowest_wager['wagering']}). Best all-round: {top['name']} ({top['bonus']}). All accept PayID deposits for real money pokies from day one."),
    ]

    html_items = []
    for q, a in items:
        html_items.append(f"""    <div class="faq-item">
      <button class="faq-question" aria-expanded="false">
        {q}
        <span class="faq-icon">+</span>
      </button>
      <div class="faq-answer">{a}</div>
    </div>""")
    return "\n".join(html_items)


def _itemlist_schema(site: dict, casinos: list) -> str:
    items = [
        f'{{"@type":"ListItem","position":{c["rank"]},"name":"{c["name"]}","url":"{site["domain"]}/reviews/{c["slug"]}/","item":{{"@type":"Casino","name":"{c["name"]}","url":"{site["domain"]}/reviews/{c["slug"]}/","aggregateRating":{{"@type":"AggregateRating","ratingValue":"{c["score"]}","bestRating":"10","ratingCount":"{c["rating_count"]}"}}}}}}'
        for c in casinos if c.get("recommended", True)
    ]
    return '[\n      ' + ',\n      '.join(items) + '\n    ]'


def _review_schema_top3(site: dict, casinos: list) -> str:
    schemas = []
    for c in [x for x in casinos if x.get("recommended", True)][:3]:
        schemas.append(f"""  {{
    "@context": "https://schema.org",
    "@type": "Review",
    "itemReviewed": {{"@type":"Organization","name":"{c['name']}","url":"{c['affiliate_url']}","aggregateRating":{{"@type":"AggregateRating","ratingValue":"{c['score']}","bestRating":"10","ratingCount":"{c['rating_count']}"}}}},
    "author": {{"@type":"Person","name":"{site['author']}","url":"{site['domain']}/about/"}},
    "reviewRating": {{"@type":"Rating","ratingValue":"{c['score']}","bestRating":"10"}},
    "datePublished": "{TODAY}",
    "dateModified": "{TODAY}",
    "reviewBody": "{c['review_summary']}"
  }}""")
    return "[\n" + ",\n".join(schemas) + "\n  ]"


def _faq_schema(casinos: list) -> str:
    top = casinos[0]
    biggest_bonus = max(casinos, key=lambda c: c["score"])
    crypto_pick = next((c for c in casinos if "No KYC" in " ".join(c["tags"])), casinos[2])
    lowest_wager = min(casinos, key=lambda c: int(c["wagering"].replace("x", "")))
    fastest_payid = next((c for c in casinos if "PayID" in " ".join(c["tags"])), casinos[0])

    faqs = [
        ("Is online gambling legal in Australia?",
         "Yes — the Interactive Gambling Act 2001 (IGA) restricts operators, not players. Australian players can legally access licensed offshore casino sites. All casinos on this list are licensed offshore operators legally accepting Australian players."),
        ("What is the best online casino Australia for real money in 2026?",
         f"{top['name']} is our top-rated pick for the best online casino Australia real money in 2026 — scoring {top['score']}/10. It offers {top['unique_feature']} For the biggest bonus, {biggest_bonus['name']} leads with {biggest_bonus['bonus']}. For crypto, {crypto_pick['name']} is our top no-KYC pick."),
        ("How do I deposit with PayID at an online casino?",
         "Go to the cashier, select PayID, copy the casino\\u2019s PayID (phone number or email), open your banking app, and send the amount. Funds arrive within seconds \\u2014 free, 24/7, supported by CommBank, ANZ, NAB and Westpac."),
        ("Are pokies winnings taxed in Australia?",
         "No. Recreational gambling winnings \\u2014 including online pokies \\u2014 are not taxed in Australia. The ATO does not treat gambling as a profession for most players, so winnings are not assessable income."),
        ("How do wagering requirements work?",
         f"Wagering requirements specify how many times you must bet your bonus before withdrawing. A $100 bonus at 35x means $3,500 in wagers before cashout. {lowest_wager['name']} has the lowest on our list at {lowest_wager['wagering']} \\u2014 always check the T\\u0026Cs."),
        ("Which PayID casino offers a no deposit bonus in Australia?",
         "Some of the best PayID online casino sites offer no deposit bonuses as sign-up incentives. Availability changes regularly \\u2014 check each casino\\u2019s promotions page for current offers. All casinos on this list accept PayID deposits from day one."),
        ("Can I use an e-wallet at Australian online casinos?",
         "Yes. The best e-wallet casino Australia options include PayID (instant, zero fees, natively Australian), POLi (direct bank transfer, no third-party account needed), Skrill, and Neteller. PayID is the most recommended e-wallet for online pokies in Australia."),
        ("What is the best crypto casino in Australia with no KYC?",
         f"{crypto_pick['name']} is our top pick for best crypto casino Australia no KYC \\u2014 {crypto_pick['unique_feature']} These are ideal for Aussie punters who value privacy and fast crypto withdrawals."),
        ("Which casinos offer the best PayID pokies in Australia?",
         f"The best PayID pokies Australia sites on our list are {top['name']} (#{top['rank']}, {top['score']}/10) and {fastest_payid['name']} \\u2014 both confirmed instant PayID withdrawals. PayID uses the NPP for real-time bank transfers 24/7 including weekends and public holidays."),
        ("What is the best PayID pokies sign up bonus in Australia?",
         f"For the best PayID pokies sign up bonus: largest total is {casinos[1]['name']} ({casinos[1]['bonus']}); lowest wagering is {lowest_wager['name']} ({lowest_wager['bonus']} at {lowest_wager['wagering']}); best overall is {top['name']} ({top['bonus']}). All accept PayID deposits from day one."),
    ]
    entities = []
    for q, a in faqs:
        entities.append(f"""      {{
        "@type": "Question",
        "name": "{q}",
        "acceptedAnswer": {{"@type": "Answer", "text": "{a}"}}
      }}""")
    return "{\n    \"@context\": \"https://schema.org\",\n    \"@type\": \"FAQPage\",\n    \"mainEntity\": [\n" + ",\n".join(entities) + "\n    ]\n  }"


def build_index_prompt(site: dict, casinos: list, design: dict, keywords: dict) -> str:
    # Apply daily badge + position shuffle before rendering
    casinos = _apply_daily_badges_and_shuffle(casinos)
    # Pre-render all data-driven HTML sections in Python — guaranteed complete
    casino_grid    = _casino_grid_html(casinos)
    comp_rows      = _comparison_table_html(casinos)
    review_blocks  = _review_blocks_html(casinos)
    faq_items      = _faq_html(casinos)
    itemlist_json  = _itemlist_schema(site, casinos)
    review_json    = _review_schema_top3(site, casinos)
    faq_json       = _faq_schema(casinos)

    primary_kws  = ", ".join(f'"{k}"' for k in keywords["primary"])
    longtail_kws = "\n".join(f"- {k}" for k in keywords["long_tail"])
    kw_rules     = "\n".join(f"- {r}" for r in keywords["rules"])

    # Compact casino summary for prose sections (recommended only)
    casino_summary = "\n".join(
        f"  #{c['rank']} {c['name']} — {c['bonus']} — Score {c['score']}/10 — Best for: {c['best_for']}"
        for c in casinos if c.get("recommended", True)
    )

    return f"""You are generating a complete production-ready HTML page. I am providing the EXACT HTML for several key sections — you MUST embed them verbatim. Your job is to write the CSS, head, nav, hero, prose sections, and footer that wrap around them.

## SITE
Brand: {site['brand']} | Domain: {site['domain']} | Author: {site['author']} | Year: {site['year']}

## DESIGN TOKENS
--bg:{design['bg']} --card-bg:{design['card_bg']} --border:{design['border']} --gold:{design['gold']} --green:{design['green']} --red:{design['red']} --text:{design['text']} --muted:{design['muted']}
Heading font: '{design['font_head']}' 700/800 | Body font: '{design['font_body']}' 400/500/600 — load both from Google Fonts

## CASINO SUMMARY (for prose content)
{casino_summary}

## SEO KEYWORDS
Primary (use in title, H1, H2s, meta description): {primary_kws}
Long-tail (weave into body copy naturally):
{longtail_kws}
Priority keywords — use these EXACTLY in FAQ questions, H2s, and body copy:
- "best payid online casino" (use in FAQ Q2 and market overview)
- "best payid pokies australia" (use in FAQ Q9/Q10 and hero)
- "best e-wallet casino australia" (use in FAQ Q7 and banking section)
- "best e-wallet pokies australia" (use in banking section and overview)
Rules: {kw_rules}

---

## OUTPUT: COMPLETE HTML PAGE

Build the page in this exact order:

### [A] DOCTYPE + <html lang="en-AU"> + <head>
Include ALL of the following in <head>:
- charset UTF-8, viewport
- <title>Best PayID Online Casinos Australia {site['year']} – Top 8 PayID Pokies Sites | {site['brand']}</title>
- <meta name="description" content="Find the best online casino Australia {site['year']}. Expert-reviewed PayID casinos with fast payouts, 10,000+ pokies and generous AUD bonuses for Aussie punters.">
- <link rel="canonical" href="{site['domain']}/">
- <link rel="alternate" hreflang="en-AU" href="{site['domain']}/">
- <meta name="robots" content="index, follow">
- Full OG meta set (type=website, title, description, url, site_name={site['brand']}, locale=en_AU)
- Full Twitter card meta set
- Google Fonts preconnect + link (Barlow+Condensed:wght@700;800 and Inter:wght@400;500;600)
- This JSON-LD ItemList (embed verbatim):
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"ItemList","name":"Best Online Casinos Australia {site['year']}","url":"{site['domain']}/","numberOfItems":8,"itemListElement":{itemlist_json}}}
</script>
- This JSON-LD FAQPage (embed verbatim):
<script type="application/ld+json">
{faq_json}
</script>
- This JSON-LD Review array (embed verbatim):
<script type="application/ld+json">
{review_json}
</script>
- Organization JSON-LD for {site['brand']} (write this yourself — include sameAs with twitter, foundingDate, description)
- WebSite JSON-LD with SiteLinksSearchBox: {{"@context":"https://schema.org","@type":"WebSite","name":"{site['brand']}","url":"{site['domain']}/","potentialAction":{{"@type":"SearchAction","target":"{site['domain']}/?s={{{{search_term_string}}}}","query-input":"required name=search_term_string"}},"publisher":{{"@type":"Organization","name":"{site['brand']}","url":"{site['domain']}/"}}}}
- BreadcrumbList JSON-LD for homepage (single item: Home = {site['domain']}/)
- Resource hints: <link rel="dns-prefetch" href="//fonts.googleapis.com"> and <link rel="dns-prefetch" href="//fonts.gstatic.com"> after existing preconnect tags
- Complete <style> block with ALL CSS for the entire page. In the @font-face or Google Fonts import, use font-display: swap for all fonts to prevent layout shift.

### CSS REQUIREMENTS (write full <style> block)
Use the design tokens above as CSS custom properties. Include styles for:
- Reset (box-sizing, margin, padding)
- Body, typography, links
- Sticky nav with backdrop-filter blur
- Hero section with payment pills bar
- Section wrapper (.section, .content-section) max-width 1200px centered
- Casino grid: 4-col desktop → 2-col tablet (<900px) → 1-col mobile (<640px)
- Casino card (.casino-card): hover lift effect, rank badges (.rank-1 gold, .rank-2 silver, .rank-3 bronze, .rank-other)
- Card badges (.card-badge): small pill top-right corner of card. Four variants:
  - .badge-hot: red bg (#ff4757), white text — "HOT 🔥"
  - .badge-new: green bg (#00d97e), dark text — "NEW"
  - .badge-editors: gold bg (#f8bc2e), dark text — "EDITOR'S PICK"
  - .badge-exclusive: purple bg (#7c3aed), white text — "EXCLUSIVE"
- Card logo area (56px height, text fallback)
- Card name, bonus (green), wagering (muted), tags (gold pills), score (large gold number + stars), CTA button (green), review link
- How-we-rate info box (.info-box) with rating grid and progress bars
- Comparison table (.comparison-table) with alternating rows, .comp-play button
- Review blocks (.review-block): header row, bonus box (green-tinted), pros/cons grid, CTA row
- Long-form content sections: h2, h3, p, ul styling
- Methodology grid (.methodology-grid) with .methodology-item cards
- Banking grid (.banking-grid) with .banking-card, .banking-speed badge
- FAQ accordion (.faq-list, .faq-item, .faq-question, .faq-answer, .faq-icon rotation)
- Responsible gambling box (.rg-box) with red left border, .rg-hotline number, .rg-links pill row
- Footer: dark bg, brand, nav links, disclaimer, copyright
- Mobile: CTA buttons full-width, nav links hidden, pros-cons stack to 1-col

### [B] </head><body>

### [C] STICKY NAV
<nav class="nav"> with:
- .nav-brand linking to {site['domain']}/ — "{site['brand']}"
- .nav-links (hidden mobile): "Top Casinos" (#top-list) | "How We Rate" (#how-we-rate) | "Compare" (#compare) | "Reviews" (#reviews) | "Banking" (#banking) | "FAQ" (#faq) | "Guides" (/guides/best-payid-casinos/)
- .nav-age badge: "18+"
- IMPORTANT: Do NOT add a "Bonuses" nav link. There is no /bonuses/ page. Use exactly the links listed above — no extras.

### [D] HERO <header class="hero">
- <h1>Best PayID Online Casinos in <span>Australia {site['year']}</span></h1>
- 2-sentence intro mentioning PayID, pokies, personal testing
- Author byline + "Updated {TODAY_PRETTY}" + "8 casinos reviewed"
- .payments-bar strip: PayID · POLi · Visa · Mastercard · Bitcoin · Ethereum · Solana

### [E] CASINO LIST — embed the cards below VERBATIM inside <section class="section" id="top-list">:
<section class="section" id="top-list" aria-label="Top online casinos Australia {site['year']}">
  <h2 class="section-title">Top <span>8</span> Online Casinos for Aussie Punters</h2>
  <div class="casino-grid">
{casino_grid}
  </div>
</section>

### [E2] NOT RECOMMENDED CASINOS — add this section immediately after the top-list section:
<section class="section" id="not-recommended" aria-label="Casinos we do not recommend">
  <h2 class="section-title"><span>Not Recommended</span> Casinos</h2>
  <p style="color:var(--muted);margin-bottom:1.5rem">These casinos accept Australian players but scored below 7/10 in our testing. We include them for transparency — read the individual reviews for full details before deciding.</p>
  Write a grid of cards (2-col desktop, 1-col mobile) for these 7 casinos: {", ".join(c["name"] for c in casinos if not c.get("recommended", True))}
  Each card must have:
  - A red "NOT RECOMMENDED" badge (background #dc2626, white text, bold)
  - Casino name, score (e.g. "6.2/10")
  - One-line reason from not_recommended_reason field
  - A grey/muted "Read Review →" link to their review page
  - NO green CTA button — only a muted review link
  - Red/orange border to visually distinguish from recommended cards
  Not-recommended casino data:
{chr(10).join(f"  - {c['name']}: score {c['score']}/10, reason: {c.get('not_recommended_reason','')}, review: {c['review_url']}" for c in casinos if not c.get('recommended', True))}
</section>

### [F] HOW WE RATE <section class="section" id="how-we-rate">
Info box with 6 rating criteria as a grid with visual progress bars (CSS width %):
- Payout Speed (95%) — PayID, crypto & AUD processing tested
- Pokie Variety (90%) — titles, providers & exclusives
- Bonus Fairness (85%) — wagering requirements & T&C transparency
- Licensing & Safety (100%) — verified offshore licences
- Australian Payment Support (95%) — PayID, POLi, AUD accounts confirmed
- Mobile Experience (80%) — tested on iOS and Android browsers

### [G] COMPARISON TABLE — embed rows below VERBATIM inside the table:
<section class="section" id="compare" aria-label="Casino comparison">
  <h2 class="section-title">Quick Comparison — <span>Top 5</span> Casinos</h2>
  <div class="table-wrap">
    <table class="comparison-table" aria-label="Top 5 casinos comparison">
      <thead><tr><th>#</th><th>Casino</th><th>Welcome Bonus</th><th>Wagering</th><th>Score</th><th>Action</th></tr></thead>
      <tbody>
{comp_rows}
      </tbody>
    </table>
  </div>
</section>

### [H] EXPERT REVIEWS — embed review blocks below VERBATIM inside the section:
<section class="section" id="reviews" aria-label="Expert casino reviews">
  <h2 class="section-title">Expert Reviews — <span>Top 3</span> Picks</h2>
{review_blocks}
</section>

### [I] CONTENT SECTION: Market Overview (write this yourself)
<section class="content-section" id="overview">
  <h2>Australian Online Casino <span>Market Overview {site['year']}</span></h2>
  Write ~300 words (4–5 paragraphs) of SEO-rich copy covering:
  - Best casino overview (mention Stake96 #1, Spin2U biggest bonus, Spinza96 for crypto)
  - What separates these 8 from the broader market (PayID, licensed offshore, independent scores)
  - The 3 AU market shifts of 2026: PayID dominance, e-wallet expansion, 10,000+ pokie libraries
  - Use the phrase "best e-wallet pokies australia" naturally in one sentence
  - Internal links to /guides/best-payid-casinos/ and /guides/how-to-play-pokies/
  Use "pokies" not "slots", "punters" not "players".

### [J] CONTENT SECTION: Methodology (write this yourself)
<section class="content-section" id="methodology">
  <h2>How We <span>Rate Casinos</span></h2>
  Write ~200 words total. Intro paragraph (2–3 sentences) explaining Blake Donovan's independent testing process — no paid rankings, real accounts, real deposits. Then .methodology-grid with 6 .methodology-item cards:
  - Payout Speed: PayID, crypto & AUD processing tested with real withdrawals
  - Pokie Variety: library size, providers, exclusives, Megaways availability
  - Bonus Fairness: wagering requirements, T&C transparency, max win caps
  - Licensing & Safety: verified offshore licences, encryption, responsible gambling tools
  - AU Payment Support: PayID, POLi, AUD accounts — confirmed working from Australia
  - Mobile Experience: iOS and Android browser performance, touch UI, load speed
  Each card: h3 + 2 substantive sentences. Total section ~200 words.

### [K] CONTENT SECTION: Banking (write this yourself)
<section class="content-section" id="banking">
  <h2>Banking at <span>AU Online Casinos</span></h2>
  Intro paragraph (2 sentences) using "best e-wallet casino australia" naturally. Then .banking-grid with 4 .banking-card elements:
  - PayID: Australia's #1 casino payment method. How it works (NPP, instant bank transfer), all major AU banks (CommBank, ANZ, NAB, Westpac), instant deposits + under 5 min withdrawals, zero fees. Include .banking-speed badge "Instant / Under 5 min". Link to /guides/best-payid-casinos/ for full guide. Mention it's the best PayID online casino method for Aussie punters.
  - E-Wallets (Skrill / Neteller): International e-wallet options, extra privacy layer, instant deposits, 24–48 hr withdrawals. Pros/cons vs PayID. Mention "best e-wallet pokies australia" in the body text.
  - POLi: AU-specific direct bank transfer, no third-party account needed, instant deposits, widely accepted. .banking-speed badge "Instant".
  - Crypto (BTC / ETH / SOL): Fastest withdrawal method — SOL under 1 min, BTC 5–10 min. No-KYC options. Mention Spinza96 and PokieSpin96 as crypto-friendly picks. .banking-speed badge "Under 1 min (SOL)".

### [L] FAQ SECTION — embed items below VERBATIM:
<section class="content-section" id="faq">
  <h2>Frequently Asked <span>Questions</span></h2>
  <p>Answers to the most common questions from Aussie punters about online casinos, pokies, PayID banking, and bonuses in {site['year']}.</p>
  <div class="faq-list">
{faq_items}
  </div>
</section>

### [M] RESPONSIBLE GAMBLING (write this yourself)
<section class="content-section" id="responsible-gambling">
  .rg-box with red left border:
  - h2: "Responsible Gambling"
  - Para 1: Online pokies should be entertainment, not income. Set a budget, play within your means.
  - Para 2: Signs of problem gambling — chasing losses, hiding play from family, borrowing to gamble. Help is free and confidential.
  - .rg-hotline: "1800 858 858" (Gambling Help Online — free, 24/7)
  - .rg-links pill row with: gamblinghelponline.org.au | Lifeline 13 11 14 | NSW Gambling Help 1800 858 858 | VIC Gambling Help 1800 522 888
  - Final note: All casinos on this list offer deposit limits, cooling-off periods and self-exclusion tools — use them.

### [N] FAQ ACCORDION SCRIPT (vanilla JS, no frameworks)
<script> to toggle .faq-item open class and aria-expanded on button click. One open at a time.

### [O] FOOTER <footer>
- .footer-brand: "{site['brand']}"
- .footer-nav links: Top Casinos (#top-list) | How We Rate (#how-we-rate) | Compare (#compare) | About (/about/) | Guides (/guides/best-payid-casinos/) | Contact (mailto:{site['email']}) | Privacy Policy (/privacy-policy/) | Terms & Conditions (/terms-conditions/)
- Responsible gambling disclaimer + affiliate disclosure
- .footer-copy: "© {site['year']} {site['brand']} · {site['domain'].replace('https://', '')} · All rights reserved."

---
Return ONLY the complete raw HTML. Start with <!DOCTYPE html>. No markdown fences. No explanation. No truncation — include every section A through O."""


def build_review_prompt(site: dict, casino: dict, design: dict, keywords: dict) -> str:
    primary_kws  = ", ".join(f'"{k}"' for k in keywords["primary"])
    longtail_kws = "\n".join(f"- {k}" for k in keywords["long_tail"])
    info_kws     = "\n".join(
        f"- {k.replace('[casino name]', casino['name'])}" for k in keywords["informational"]
    )
    kw_rules     = "\n".join(f"- {r}" for r in keywords["rules"])

    score_bars = "\n".join(
        f"  {cat}: {score}/10" for cat, score in casino["score_breakdown"].items()
    )
    mobile_score  = casino["score_breakdown"].get("Mobile Experience", 9.5)
    support_score = casino["score_breakdown"].get("Support", 9.5)
    if not casino.get("recommended", True):
        verdict_label = "Not Recommended"
    elif casino["score"] >= 9.5:
        verdict_label = "Excellent"
    elif casino["score"] >= 9.0:
        verdict_label = "Very Good"
    else:
        verdict_label = "Good"

    return f"""Generate a complete, production-ready HTML review page for an Australian online casino.
TARGET LENGTH: 1,500–2,500 words of body copy across all sections. Do not truncate any section.

## SITE INFO
Brand: {site['brand']} | Domain: {site['domain']} | Author: {site['author']} | Year: {site['year']}
Author bio: {site['author_bio']}
Canonical: {site['domain']}/reviews/{casino['slug']}/

## CASINO DATA
{json.dumps(casino, indent=2)}

## DESIGN TOKENS
--bg:{design['bg']} --card-bg:{design['card_bg']} --border:{design['border']} --gold:{design['gold']} --green:{design['green']} --red:{design['red']} --text:{design['text']} --muted:{design['muted']}
Heading font: '{design['font_head']}' 700/800 | Body font: '{design['font_body']}' 400/500/600 — Google Fonts

---

## PAGE STRUCTURE (all 19 sections required — do not skip any)

### [1] HEAD
- charset UTF-8, viewport
- <title>{casino['name']} Review Australia {site['year']} – Pokies, Bonus & PayID | {site['brand']}</title>
- <meta name="description"> under 160 chars — include: "{casino['name']}", "{casino['score']}/10", bonus headline, "Australia pokies"
- <link rel="canonical" href="{site['domain']}/reviews/{casino['slug']}/">
- <link rel="alternate" hreflang="en-AU" href="{site['domain']}/reviews/{casino['slug']}/">
- OG (type=article) + Twitter card meta
- Google Fonts preconnect + link (Barlow Condensed 700/800 + Inter 400/500/600)
- JSON-LD Review schema: {{"@context":"https://schema.org","@type":"Review","itemReviewed":{{"@type":"Casino","name":"{casino['name']}","url":"{casino['affiliate_url']}","aggregateRating":{{"@type":"AggregateRating","ratingValue":"{casino['score']}","bestRating":"10","ratingCount":"{casino['rating_count']}"}}}},"author":{{"@type":"Person","name":"{site['author']}","url":"{site['domain']}/about/"}},"reviewRating":{{"@type":"Rating","ratingValue":"{casino['score']}","bestRating":"10"}},"datePublished":"{TODAY}","dateModified":"{TODAY}","reviewBody":casino review_summary}}
- JSON-LD FAQPage schema: 5 Q&As matching section [18] exactly — include "dateModified":"{TODAY}" on FAQPage schema
- JSON-LD BreadcrumbList: Home ({site['domain']}/) → Reviews ({site['domain']}/reviews/) → {casino['name']} ({site['domain']}/reviews/{casino['slug']}/)
- Speakable schema: {{"@context":"https://schema.org","@type":"SpeakableSpecification","cssSelector":["#faq .faq-question"]}} (marks FAQ questions as speakable for voice search)
- IMPORTANT: Use ONLY these schemas (Review, FAQPage, BreadcrumbList, Speakable). Do NOT add Product, OnlineBusiness, LocalBusiness.
- Resource hints after existing preconnect: <link rel="dns-prefetch" href="//fonts.googleapis.com">
- Complete <style> block with ALL page CSS. Use font-display: swap on all font declarations to prevent layout shift (Core Web Vitals).

### [2] CSS
All CSS custom properties from design tokens. Styles required:
- Reset, body, typography, links, .text-link (gold, underline)
- Sticky nav: backdrop-filter blur, .nav-brand gold, .nav-back muted link, .nav-age gold badge
- .review-hero: breadcrumb trail, H1, .expert-label badge, .hero-meta byline, .hero-score card (right-aligned desktop, full-width mobile) with score number/stars/verdict badge
- .bonus-box: rgba green bg, green border, label, big text, detail text, stats row, CTA button
- .quick-stats: 3-col desktop → 2-col tablet → 1-col mobile grid; .stat-card with label/value; .stat-highlight gold border
- .pros-cons: 2-col desktop → 1-col mobile; .pros-box green border/✓ bullets; .cons-box red border/✗ bullets
- .rating-bars: .bar-row (label + bar-bg + bar-fill gold + score); bar width = (score/10)*100%
- .review-section: h2 (font-head 28px gold highlight span), h3 (font-head 20px gold), p, ul, strong
- .data-table wrapper (overflow-x:auto) + table (full-width, collapse, alternating rows)
- .speed-fast (green pill), .speed-med (gold pill), .speed-slow (red pill)
- .bonus-info-grid: 2×2 grid of .bonus-info-card (label + value + note)
- .verdict-box: gold top-border, full-width .verdict-cta button (green)
- .rg-strip: red left-border, compact padding
- FAQ accordion (.faq-list → .faq-item → .faq-question/.faq-answer/.faq-icon)
- Footer: dark bg, brand, nav, disclaimer, copyright
- Mobile: CTA full-width, nav-links hidden, tables scrollable

### [3] STICKY NAV
- .nav-brand "{site['brand']}" → {site['domain']}/
- .nav-back "← Back to Top List" → {site['domain']}/
- .nav-age "18+"

### [4] REVIEW HERO
Breadcrumb: <a href="{site['domain']}/">Home</a> › <a href="{site['domain']}/reviews/">Reviews</a> › {casino['name']}
<h1>{casino['name']} Review Australia {site['year']}</h1>
.expert-label: "EXPERT REVIEW" badge
.hero-meta: "By <a href='{site['domain']}/about/'>{site['author']}</a>" · "Updated {TODAY_PRETTY}" · "{casino['score']}/10"
.hero-score card (right on desktop): "{casino['score']}" large gold / "/10" muted / stars / {"'NOT RECOMMENDED' red badge (bg #dc2626, white text, bold)" if not casino.get('recommended', True) else "'RECOMMENDED' green badge"}
{f'Show .hot-badge "HOT" in red' if casino.get('hot') else ''}
{f"""IMPORTANT — NOT RECOMMENDED CASINO: This casino scored {casino['score']}/10 and is NOT recommended.
- Show a prominent red warning banner immediately below the hero: "⚠️ Not Recommended — {casino.get('not_recommended_reason', 'See review for details')}"
- Style: red background (#dc2626), white text, bold, full-width, padding 12px 20px
- The verdict section must clearly state this is NOT recommended and explain why
- Do NOT add a green CTA button in the verdict — use a grey/muted "Visit Site" link instead""" if not casino.get('recommended', True) else ''}

### [4b] TABLE OF CONTENTS
Immediately after the hero, add a compact .toc-box (card, dark bg, gold left border):
<nav class="toc-box" aria-label="Page contents">
  <p class="toc-title">In This Review</p>
  <ol class="toc-list">
    <li><a href="#bonus">Welcome Bonus</a></li>
    <li><a href="#quick-stats">Quick Stats</a></li>
    <li><a href="#rating">Rating Breakdown</a></li>
    <li><a href="#overview">Overview</a></li>
    <li><a href="#games">Game Library</a></li>
    <li><a href="#banking">Banking & Payouts</a></li>
    <li><a href="#mobile">Mobile Experience</a></li>
    <li><a href="#support">Customer Support</a></li>
    <li><a href="#safety">Safety & Licensing</a></li>
    <li><a href="#verdict">Our Verdict</a></li>
    <li><a href="#faq">FAQ</a></li>
  </ol>
</nav>
Add id attributes to each matching section heading: id="bonus", id="quick-stats", id="rating", id="overview", id="games", id="banking", id="mobile", id="support", id="safety", id="verdict", id="faq".

### [5] BONUS CLAIM BOX
.bonus-box (green-tinted bg, green border):
- "WELCOME BONUS" label (uppercase, green, small)
- Big text: "{casino['bonus']}"
- Detail: "{casino['bonus_detail']}"
- Stats row: "Wagering: {casino['wagering']}" | "Min Deposit: {casino['min_deposit']}"
- Green CTA button: "Claim Bonus at {casino['name']} →" → href="{casino['affiliate_url']}" target="_blank" rel="nofollow noopener sponsored"
- Disclaimer: "T&Cs apply. 18+ only. New players only. Gamble responsibly."

### [6] QUICK STATS GRID (6 cards)
Welcome Bonus: {casino['bonus']}
Our Score: {casino['score']}/10 ★ (.stat-highlight — gold border)
Wagering: {casino['wagering']}
Min Deposit: {casino['min_deposit']}
Payout Speed: Under 5 min (PayID)
Best For: {casino['best_for']}

### [7] PROS & CONS
2-column .pros-cons grid. Use casino pros/cons verbatim:
Pros: {casino['pros']}
Cons: {casino['cons']}

### [8] RATING BREAKDOWN
H2: "Our {casino['name']} Rating Breakdown"
.rating-bars for each score_breakdown entry:
{score_bars}
Bar fill width = (score / 10) * 100%

### [9] OVERVIEW SUMMARY (~200 words)
H2: "{casino['name']} Overview"
Write 2–3 paragraphs (~200 words):
- Open with: "{casino['name']} review Australia {site['year']}: ..." — use the primary keyword in the first sentence
- Paragraph 1: What this casino is, who it's best for ("{casino['best_for']}"), overall verdict. Naturally mention one Australian state (NSW, VIC, or QLD) to capture state-specific searches.
- Paragraph 2: Unique standout — "{casino['unique_feature']}"
- Paragraph 3: Summary of scores — pokies library, payout speed, bonus value, mobile, support
- End section with 2–3 internal links: e.g. "See our <a href='{site['domain']}/guides/best-payid-casinos/'>best PayID casinos guide</a>", "Compare all <a href='{site['domain']}/'>8 top AU casinos</a>", "Learn <a href='{site['domain']}/guides/how-to-play-pokies/'>how to play pokies</a>"
Tone: authoritative first-person reviewer. Use "pokies" not "slots", "punters" not "players".

### [10] WELCOME BONUS BREAKDOWN
H2: "{casino['name']} Welcome Bonus — Full Breakdown"
Intro sentence with total bonus value.
.bonus-info-grid (2×2):
- **Bonus Amount**: {casino['bonus']} | {casino['bonus_detail']}
- **Wagering Requirements**: {casino['wagering']} | Plain-English explanation: "$X bonus × {casino['wagering']} = $Y total bets required before cashout"
- **Eligible Games**: Pokies 100% | Live dealer ~10–15% | Note: check T&Cs for full game weights
- **Time Limit**: Typically 30 days to meet wagering | Advise reading T&Cs for exact limit
Bonus table (.bonus-table):
| Deposit | Match | Max Bonus | Free Spins | Wagering |
(1–3 rows based on bonus_detail — e.g. if multi-deposit, show each deposit step)
How to claim — 3 numbered steps:
1. Click "Claim Bonus" and register
2. Deposit {casino['min_deposit']} or more via PayID or preferred method
3. Bonus credits automatically — start spinning on eligible pokies

### [11] GAME LIBRARY
H2: "{casino['name']} Game Library"
Four sub-sections (use h3):
**h3: Total Games**
Infer from tags: {"10,000+" if any("10,000" in t for t in casino["tags"]) else "5,000+"} titles. 2 sentences on depth of library.
**h3: Top Providers**
Name 5–6 top providers (Pragmatic Play, Evolution Gaming, Hacksaw Gaming, Play'n GO, NetEnt, Relax Gaming). 2 sentences on variety and exclusives.
**h3: Pokies**
Best categories: Megaways, progressive jackpots, classic 3-reel, video pokies. Name 5–6 top titles with RTPs:
- Gates of Olympus (96.5%, Pragmatic Play)
- Sweet Bonanza (96.5%, Pragmatic Play)
- Book of Dead (96.2%, Play'n GO)
- Big Bass Bonanza (96.71%, Pragmatic Play)
- Dog House Megaways (96.55%, Pragmatic Play)
- Wanted Dead or a Wild (96.38%, Hacksaw Gaming)
Use "pokies" throughout. 2–3 sentences.
**h3: Live Dealer**
Evolution Gaming tables: blackjack, roulette, baccarat, Lightning Roulette. AU-friendly hours. 2 sentences.

### [12] BANKING
H2: "{casino['name']} Banking — Deposits, Withdrawals & Payout Speed"
Intro: confirm PayID availability (1–2 sentences).

**h3: Deposit Methods**
<div class="table-wrap"><table class="data-table">
Header: Method | Min | Max | Processing | Fees
Rows:
PayID | {casino['min_deposit']} | $50,000 | Instant | Free <span class="speed-fast">FAST</span>
POLi | {casino['min_deposit']} | $10,000 | Instant | Free <span class="speed-fast">FAST</span>
Visa / Mastercard | $25 | $5,000 | Instant | Free <span class="speed-fast">FAST</span>
Bitcoin (BTC) | $25 | No limit | Instant | Network fee <span class="speed-fast">FAST</span>
Ethereum (ETH) | $25 | No limit | Instant | Network fee <span class="speed-fast">FAST</span>
Solana (SOL) | $25 | No limit | Instant | Network fee <span class="speed-fast">FAST</span>
</table></div>

**h3: Withdrawal Methods**
<div class="table-wrap"><table class="data-table">
Header: Method | Min | Max | Speed | Badge
PayID | $50 | $50,000 | Under 5 min | <span class="speed-fast">FAST</span>
Bitcoin | $50 | No limit | 5–10 min | <span class="speed-fast">FAST</span>
Solana | $50 | No limit | Under 1 min | <span class="speed-fast">INSTANT</span>
Ethereum | $50 | No limit | 10–30 min | <span class="speed-fast">FAST</span>
Visa / Mastercard | $50 | $5,000 | 2–5 days | <span class="speed-slow">SLOW</span>
</table></div>

**h3: Payout Speed**
2 sentences: PayID as fastest AUD method (under 5 min), SOL fastest crypto (under 1 min). No hidden fees on PayID.

### [13] MOBILE EXPERIENCE
H2: "{casino['name']} Mobile Experience"
Write ~150 words. Mobile score: {mobile_score}/10.
- No dedicated app — operates via mobile browser (standard for offshore AU casinos)
- iOS Safari + Android Chrome performance
- Touch UI quality, lobby navigation, pokie loading speed
- Portrait and landscape support
- Calibrate tone to score: {mobile_score}/10 (9.5+ = excellent, 9.0+ = very good, below = note limitations)

### [14] CUSTOMER SUPPORT
H2: "{casino['name']} Customer Support"
Write ~150 words. Support score: {support_score}/10.
- Live chat: 24/7 availability (or hours if limited) — target under 2 min response
- Email support: typical response 12–24 hours
- FAQ / Help centre: self-serve for common AUD billing and bonus queries
- AU-specific considerations: time zones, AUD billing support
- Calibrate tone to score: {support_score}/10

### [15] LICENSING & SECURITY
H2: "Is {casino['name']} Safe & Legit?"
Write ~150 words:
- Offshore licence (Curaçao eGaming or Malta MGA — standard for AU-facing operators)
- IGA: restricts operators not players — Australians can legally access licensed offshore casinos
- SSL/TLS 256-bit encryption on all transactions and account data
- Responsible gambling tools: deposit limits, cooling-off periods, self-exclusion
- Verdict: "Licensed offshore casino legally accepting Australian players"
- Never claim ACMA or AU government licensing

### [16] VERDICT BOX
.verdict-box (gold top-border):
H2: "Our {casino['name']} Verdict"
2–3 paragraphs referencing review_summary and unique_feature.
Final score line: "{casino['score']}/10 — {verdict_label}"
Full-width .verdict-cta: "Play at {casino['name']} Now →" → href="{casino['affiliate_url']}" target="_blank" rel="nofollow noopener sponsored"
Disclaimer: "T&Cs apply. 18+. Gamble responsibly. Affiliate link — we may earn commission."

### [17] RESPONSIBLE GAMBLING STRIP
Compact .rg-strip (red left-border):
"18+ only. Gambling should be for entertainment. Free confidential help: 1800 858 858 · gamblinghelponline.org.au · Lifeline 13 11 14"

### [18] FAQ ACCORDION (5 questions — match FAQPage JSON-LD exactly; phrasing matches Google People Also Ask patterns)
Q1: "Is {casino['name']} legit and safe for Australian players in {site['year']}?"
A: Reference offshore licence (Curaçao/Malta), IGA (legal for players), SSL 256-bit, responsible gambling tools. Conclude: "Licensed offshore casino legally accepting Australian players."
Q2: "Does {casino['name']} accept PayID deposits and withdrawals?"
A: Confirm PayID, instant deposits, payout time under 5 min, supported AU banks (CommBank, ANZ, NAB, Westpac). Min deposit {casino['min_deposit']}, zero fees.
Q3: "What is the {casino['name']} welcome bonus wagering requirement?"
A: State full bonus {casino['bonus']}, {casino['wagering']} wagering, min deposit {casino['min_deposit']}, eligible games, time limit. Plain-English example of wagering maths.
Q4: "How long do {casino['name']} withdrawals take?"
A: PayID under 5 min, SOL under 1 min, BTC 5–10 min, Visa 2–5 days. Note: complete KYC before first withdrawal to avoid delays.
Q5: Write a casino-specific PAA-style question using the unique_feature: "{casino['unique_feature']}" — phrased as "How many pokies does {casino['name']} have?" or "Does {casino['name']} have no KYC?" etc. as appropriate.
Vanilla JS: toggle .open class + aria-expanded on button click. One open at a time.

### [19] FOOTER
- .footer-brand "{site['brand']}" → {site['domain']}/
- .footer-nav: Top Casinos ({site['domain']}/) | All Reviews ({site['domain']}/reviews/) | About ({site['domain']}/about/) | Guides ({site['domain']}/guides/best-payid-casinos/) | Contact (mailto:{site['email']}) | Privacy Policy ({site['domain']}/privacy-policy/) | Terms & Conditions ({site['domain']}/terms-conditions/)
- Disclaimer: affiliate site, 18+, offshore casinos, IGA note
- © {site['year']} {site['brand']}

---

## SEO KEYWORDS

Primary (in <title>, H1, H2s, meta, opening para): {primary_kws}

Long-tail (weave naturally into body):
{longtail_kws}

Informational (use as FAQ questions — match closely):
{info_kws}

Rules:
{kw_rules}

## AU CONTENT RULES
- "pokies" not "slots" · "punters" not "players" · "fast payouts" not "quick withdrawals"
- Primary target keyword: "{casino['name']} review Australia {site['year']}" — in <title>, H1, first sentence of section [9]
- "Licensed offshore casino legally accepting Australian players" — use in sections [15] and [19]
- Never claim ACMA or AU government licensing

## TECHNICAL
- Single self-contained HTML — ALL CSS in <style>, zero external CSS files
- Mobile responsive. CTA buttons full-width on mobile. Nav-links hidden on mobile.
- All tables wrapped in <div class="table-wrap"> for horizontal scroll on mobile
- Rating bars: pure CSS width % — no JS
- FAQ accordion: vanilla JS only, no libraries
- Google Fonts only external dependency
- ALL affiliate links: target="_blank" rel="nofollow noopener sponsored"

Return ONLY raw HTML. Start with <!DOCTYPE html>. No markdown. No explanation.
Include ALL 19 sections — do not truncate. Budget your output carefully: keep CSS concise, avoid verbose comments, ensure the full </body></html> is reached."""


# ─────────────────────────────────────────────
# ADDITIONAL PAGE PROMPT BUILDERS
# ─────────────────────────────────────────────

def build_about_prompt(site: dict, casinos: list, design: dict, keywords: dict) -> str:
    primary_kws  = ", ".join(f'"{k}"' for k in keywords["primary"])
    kw_rules     = "\n".join(f"- {r}" for r in keywords["rules"])
    top5 = [f"#{c['rank']} {c['name']} ({c['score']}/10)" for c in casinos[:5]]
    return f"""Generate a complete, production-ready HTML About page for an Australian casino affiliate site.

## SITE INFO
- Brand: {site['brand']}
- Domain: {site['domain']}
- Author: {site['author']} — {site['author_bio']}
- Year: {site['year']}
- Canonical URL: {site['domain']}/about/
- Contact email: {site['email']}

## DESIGN TOKENS (match all other pages exactly)
- Body bg: {design['bg']}, Card bg: {design['card_bg']}, Border: {design['border']}
- Gold: {design['gold']}, CTA green: {design['green']}, Text: {design['text']}, Muted: {design['muted']}
- Fonts: {design['font_head']} (headings 700/800) + {design['font_body']} (body 400/500/600) via Google Fonts

## SEO KEYWORDS TO USE
Primary: {primary_kws}
Content rules: {kw_rules}

## REQUIRED PAGE STRUCTURE

### 1. HEAD
- charset UTF-8, viewport
- <title>: About {site['brand']} – {site['author']}, Best PayID Online Casino Australia {site['year']}
- <meta description>: under 160 chars — author name, brand, testing methodology, AU pokies
- Canonical: {site['domain']}/about/
- OG meta (type=website), Twitter card, hreflang en-AU
- Google Fonts preconnect + link
- JSON-LD: Person schema for {site['author']} (jobTitle: "Online Casino Reviewer & Editor", knowsAbout: online casinos, PayID banking, pokies, AU gambling law, crypto casinos)
- JSON-LD: Organization schema for {site['brand']}
- JSON-LD: BreadcrumbList: Home ({site['domain']}/) › About
- All CSS in <style>

### 2. STICKY NAV (same as all pages)
- Brand in gold linking to {site['domain']}/
- Nav links: Home | Reviews | Guides | About
- "18+" badge

### 3. PAGE HERO
- Breadcrumb: Home › About
- H1: "About {site['brand']}"
- Subtext: 1 sentence about independent AU casino reviews

### 4. AUTHOR SECTION
- Large author card: "{site['author']}"
- Title: "Online Casino Reviewer & Editor — Since 2019"
- Bio paragraph (3–4 sentences): reviews since 2019, 80+ offshore casinos tested, specialises in PayID speed, pokies variety, Aussie punter focus
- Expertise pills: PayID Banking · Online Pokies · Bonus Analysis · Crypto Casinos · AU Gambling Law

### 5. OUR TESTING METHODOLOGY
H2 section. 5 criteria shown as numbered cards:
1. Payout Speed — test real PayID withdrawals, time from request to bank
2. Pokies Library — count titles, check providers, test load speed
3. Bonus Fairness — analyse T&Cs, wagering requirements, max cashout
4. Support Quality — live chat response time, knowledge, availability
5. Licensing & Security — offshore licence verification, SSL, responsible gambling tools

### 6. OUR TOP PICKS (mini cards, 3-col grid on desktop)
Show top 5 casinos from this list as compact cards linking to their review pages:
{chr(10).join(top5)}
Each card: rank badge, name, score, "Read Review →" link to review_url.
Use casino data from: {json.dumps([{'name': c['name'], 'rank': c['rank'], 'score': c['score'], 'review_url': c['review_url']} for c in casinos[:5]], indent=2)}

### 7. AFFILIATE DISCLOSURE
Clear, honest disclosure box:
"We earn a commission when you sign up at casinos through our links. This never affects our rankings or review scores — all scores are independently determined by our testing process. We only list casinos we have personally tested."

### 8. CONTACT
Simple card: "Questions or feedback? Email us at {site['email']}"

### 9. FOOTER (same as all other pages)
- Brand + disclaimer
- Footer nav: Home | Reviews | Guides | About | Privacy Policy ({site['domain']}/privacy-policy/) | Terms & Conditions ({site['domain']}/terms-conditions/)
- 18+ responsible gambling disclaimer with 1800 858 858

## TECHNICAL REQUIREMENTS
- Single self-contained HTML — all CSS in <style>
- Mobile responsive
- Match the design of all other pages exactly
- Budget your output carefully: keep CSS concise, no verbose comments. You MUST reach </body></html> — do not truncate.

Return ONLY raw HTML. No markdown. No explanation. Start with <!DOCTYPE html>."""


def build_privacy_prompt(site: dict, design: dict) -> str:
    return f"""Generate a complete, production-ready HTML Privacy Policy page for an Australian casino affiliate website.

## SITE INFO
- Brand: {site['brand']}
- Domain: {site['domain']}
- Author: {site['author']}
- Year: {site['year']}
- Canonical URL: {site['domain']}/privacy-policy/
- Contact email: {site['email']}

## DESIGN TOKENS (match all other pages exactly)
- Body bg: {design['bg']}, Card bg: {design['card_bg']}, Border: {design['border']}
- Gold: {design['gold']}, CTA green: {design['green']}, Text: {design['text']}, Muted: {design['muted']}
- Fonts: {design['font_head']} (700/800) + {design['font_body']} (400/500/600) via Google Fonts

## REQUIRED PAGE STRUCTURE

### 1. HEAD
- charset UTF-8, viewport
- <title>: Privacy Policy – {site['brand']}
- <meta description>: Privacy Policy for {site['brand']}. Learn how we collect, use, and protect your personal information on our Australian casino review site.
- Canonical: {site['domain']}/privacy-policy/
- <meta name="robots" content="noindex, follow"> (legal pages should not compete in search)
- OG meta (type=website), hreflang en-AU
- Google Fonts preconnect + link
- All CSS in <style>

### 2. STICKY NAV (same as all pages)
- Brand in gold linking to {site['domain']}/
- Nav links: Home | Reviews | Guides | About
- "18+" badge

### 3. PAGE HERO
- Breadcrumb: Home › Privacy Policy
- H1: "Privacy Policy"
- Subtext: "Last updated: {TODAY_PRETTY}"

### 4. PRIVACY POLICY CONTENT
Write full, legally sound, plain-English privacy policy sections appropriate for an Australian affiliate website. Include:

**4.1 Who We Are**
{site['brand']} is an independent online casino review and comparison website. We are an affiliate site — we earn commission when users sign up at partner casinos via our links. We do not operate or own any casino.

**4.2 Information We Collect**
- Information you provide (contact form submissions, email)
- Automatically collected data: IP address, browser type, pages visited, referring URLs (via analytics)
- Cookies and tracking technologies (Google Analytics, affiliate tracking cookies)
- We do NOT collect financial information or payment details

**4.3 How We Use Your Information**
- To operate and improve the website
- To respond to enquiries
- To track affiliate referrals (via partner links)
- To analyse website traffic and user behaviour (Google Analytics)
- We do NOT sell personal data to third parties

**4.4 Cookies**
Explain: session cookies, analytics cookies (Google Analytics with anonymised IPs), affiliate tracking cookies (set by partner casinos when you click out). How to disable cookies in browser settings. Note: disabling cookies may affect affiliate tracking.

**4.5 Third-Party Links & Affiliate Disclosure**
Our site links to third-party casino websites. We earn commission on referrals. We are not responsible for the privacy practices of linked sites. Each casino has its own privacy policy. All affiliate links are marked rel="nofollow noopener sponsored".

**4.6 Data Retention**
Analytics data retained per Google Analytics default (26 months). Contact form submissions: deleted after 12 months if no ongoing correspondence.

**4.7 Your Rights (Australian Privacy Act 1988)**
Under the Australian Privacy Act and the Privacy Principles, you have the right to: access your personal data, correct inaccurate data, request deletion, opt out of marketing. Contact: {site['email']}

**4.8 Children's Privacy**
This website is intended for adults aged 18+. We do not knowingly collect data from persons under 18. If you believe a minor has submitted information, contact us immediately.

**4.9 Changes to This Policy**
We may update this policy. Changes will be posted on this page with a revised "last updated" date.

**4.10 Contact**
Questions? Email {site['email']}

### 5. FOOTER (same as all pages)
- Brand + disclaimer
- Footer nav including: Home | Reviews | Guides | About | Privacy Policy | Terms & Conditions
- 18+ responsible gambling disclaimer with 1800 858 858
- © {site['year']} {site['brand']}

## TECHNICAL REQUIREMENTS
- Single self-contained HTML — all CSS in <style>
- Mobile responsive
- Clean, readable layout with good section spacing
- Match the dark design of all other pages exactly
- Budget your output carefully: keep CSS concise, no verbose comments. You MUST reach </body></html> — do not truncate.

Return ONLY raw HTML. No markdown. No explanation. Start with <!DOCTYPE html>."""


def build_terms_prompt(site: dict, design: dict) -> str:
    return f"""Generate a complete, production-ready HTML Terms and Conditions page for an Australian casino affiliate website.

## SITE INFO
- Brand: {site['brand']}
- Domain: {site['domain']}
- Author: {site['author']}
- Year: {site['year']}
- Canonical URL: {site['domain']}/terms-conditions/
- Contact email: {site['email']}

## DESIGN TOKENS (match all other pages exactly)
- Body bg: {design['bg']}, Card bg: {design['card_bg']}, Border: {design['border']}
- Gold: {design['gold']}, CTA green: {design['green']}, Text: {design['text']}, Muted: {design['muted']}
- Fonts: {design['font_head']} (700/800) + {design['font_body']} (400/500/600) via Google Fonts

## REQUIRED PAGE STRUCTURE

### 1. HEAD
- charset UTF-8, viewport
- <title>: Terms & Conditions – {site['brand']}
- <meta description>: Terms and Conditions for using {site['brand']}. Read our affiliate disclosure, content disclaimer, and website usage terms.
- Canonical: {site['domain']}/terms-conditions/
- <meta name="robots" content="noindex, follow">
- OG meta (type=website), hreflang en-AU
- Google Fonts preconnect + link
- All CSS in <style>

### 2. STICKY NAV (same as all pages)
- Brand in gold linking to {site['domain']}/
- Nav links: Home | Reviews | Guides | About
- "18+" badge

### 3. PAGE HERO
- Breadcrumb: Home › Terms & Conditions
- H1: "Terms & Conditions"
- Subtext: "Last updated: {TODAY_PRETTY}"

### 4. TERMS & CONDITIONS CONTENT
Write full, plain-English terms and conditions appropriate for an Australian casino affiliate website. Include:

**4.1 Acceptance of Terms**
By accessing {site['domain']}, you agree to these Terms & Conditions. If you disagree, please do not use the site.

**4.2 About {site['brand']}**
{site['brand']} is an independent casino review and comparison website. We are NOT a casino operator. We do not accept bets or process payments. We provide information and reviews to help Australian adults make informed decisions about online gambling.

**4.3 Affiliate Disclosure**
We operate as an affiliate. When you click links on our site and sign up at a partner casino, we may earn a commission. This does not affect the cost to you. Our editorial ratings and rankings are independent of commercial relationships. We only list casinos we have tested.

**4.4 Age Restriction — 18+ Only**
This website is intended solely for adults aged 18 or over. Gambling by persons under 18 is illegal in Australia. By using this site, you confirm you are 18 or older. We reserve the right to refuse service to anyone we believe is under 18.

**4.5 Gambling Disclaimer**
Online gambling involves financial risk. Past performance does not guarantee future results. House edge means the majority of players lose money over time. Information on this site is for entertainment and informational purposes only — not financial advice. Always gamble responsibly with money you can afford to lose.

**4.6 Responsible Gambling**
We encourage responsible gambling. If gambling is causing problems, seek help:
- Gambling Help Online: gamblinghelponline.org.au
- National Helpline: 1800 858 858 (24/7, free, confidential)
- Lifeline: 13 11 14

**4.7 Australian Gambling Law**
Under the Interactive Gambling Act 2001 (IGA), Australian operators are prohibited from offering certain gambling services to Australian residents. However, Australians may legally access licensed offshore casinos. All casinos listed on {site['brand']} are licensed in offshore jurisdictions (Curaçao, Malta or equivalent) and accept Australian players. We do not claim or imply that listed casinos hold ACMA approval or Australian government licences.

**4.8 Accuracy of Information**
Casino bonuses, terms, and features change frequently. We aim to keep information current but cannot guarantee accuracy at all times. Always verify current terms directly with the casino before depositing. {site['brand']} accepts no liability for decisions made based on information on this site.

**4.9 Intellectual Property**
All content on {site['brand']} (text, ratings, layouts) is © {site['year']} {site['brand']}. You may not reproduce, distribute or republish content without written permission. Casino logos and brand names belong to their respective owners.

**4.10 Limitation of Liability**
{site['brand']} is provided "as is". We make no warranties about the accuracy or reliability of content. To the maximum extent permitted by Australian law, we disclaim liability for any direct, indirect, or consequential loss arising from use of this site or linked casino sites.

**4.11 External Links**
We link to third-party casino websites. We are not responsible for the content, privacy practices, or terms of those sites. Clicking affiliate links takes you to the casino's own website, governed by that casino's terms.

**4.12 Changes to Terms**
We may update these Terms at any time. Continued use of the site after changes constitutes acceptance of the updated Terms. Changes will be posted on this page with a revised date.

**4.13 Governing Law**
These Terms are governed by the laws of New South Wales, Australia. Any disputes will be subject to the jurisdiction of NSW courts.

**4.14 Contact**
Questions about these Terms? Contact us at {site['email']}

### 5. FOOTER (same as all pages)
- Brand + disclaimer
- Footer nav including: Home | Reviews | Guides | About | Privacy Policy | Terms & Conditions
- 18+ responsible gambling disclaimer with 1800 858 858
- © {site['year']} {site['brand']}

## TECHNICAL REQUIREMENTS
- Single self-contained HTML — all CSS in <style>
- Mobile responsive
- Clean, readable layout with good section spacing
- Match the dark design of all other pages exactly
- Budget your output carefully: keep CSS concise, no verbose comments. You MUST reach </body></html> — do not truncate.

Return ONLY raw HTML. No markdown. No explanation. Start with <!DOCTYPE html>."""


def build_guide_payid_prompt(site: dict, casinos: list, design: dict, keywords: dict) -> str:
    primary_kws  = ", ".join(f'"{k}"' for k in keywords["primary"])
    longtail_kws = "\n".join(f"- {k}" for k in keywords["long_tail"])
    kw_rules     = "\n".join(f"- {r}" for r in keywords["rules"])

    # Deterministic PayID filtering + pre-rendered HTML
    payid = _payid_casinos(casinos)
    casino_cards   = _payid_casino_cards_html(payid)
    withdrawal_tbl = _payid_withdrawal_table_html(payid)
    faq_schema     = _payid_faq_schema(site, payid)

    # ItemList schema for head
    itemlist = ", ".join(
        f'{{"@type":"ListItem","position":{i+1},"name":"{c["name"]}","url":"{c["affiliate_url"]}"}}'
        for i, c in enumerate(payid)
    )
    top_names = ", ".join(c["name"] for c in payid)

    return f"""You are generating a complete production-ready HTML guide page. I am providing EXACT HTML for the casino cards and withdrawal table — embed them verbatim. Write all other sections yourself.

## SITE INFO
Brand: {site['brand']} | Domain: {site['domain']} | Author: {site['author']} | Year: {site['year']}
Canonical: {site['domain']}/guides/best-payid-casinos/

## DESIGN TOKENS
--bg:{design['bg']} --card-bg:{design['card_bg']} --border:{design['border']} --gold:{design['gold']} --green:{design['green']} --red:{design['red']} --text:{design['text']} --muted:{design['muted']}
Fonts: '{design['font_head']}' 700/800 + '{design['font_body']}' 400/500/600 — Google Fonts

## SEO KEYWORDS
Primary: {primary_kws}
Long-tail (weave naturally):
{longtail_kws}
Rules: {kw_rules}

---

## PAGE STRUCTURE (all sections required)

### [1] HEAD
- charset UTF-8, viewport
- <title>Best PayID Casino Australia {site['year']} — Instant Deposits & Fast Pokies Payouts | {site['brand']}</title>
- <meta name="description"> ~155 chars: best PayID casino Australia, instant deposits, fast payouts, real money pokies, zero fees
- <link rel="canonical" href="{site['domain']}/guides/best-payid-casinos/">
- <link rel="alternate" hreflang="en-AU" href="{site['domain']}/guides/best-payid-casinos/">
- OG (type=article) + Twitter card meta
- Google Fonts preconnect + link
- Google Fonts preconnect + link; add <link rel="dns-prefetch" href="//fonts.googleapis.com"> and <link rel="dns-prefetch" href="//fonts.gstatic.com">
- JSON-LD Article schema (author={site['author']}, publisher={site['brand']}, datePublished={TODAY}, dateModified={TODAY})
- JSON-LD BreadcrumbList: Home ({site['domain']}/) › Guides ({site['domain']}/guides/) › Best PayID Casinos Australia
- JSON-LD ItemList (top 5 PayID casinos — embed verbatim):
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"ItemList","name":"Best PayID Casinos Australia {site['year']}","numberOfItems":5,"itemListElement":[{itemlist}]}}
</script>
- JSON-LD FAQPage (embed verbatim — questions already phrased as People Also Ask):
<script type="application/ld+json">
{faq_schema}
</script>
- Speakable JSON-LD: {{"@context":"https://schema.org","@type":"SpeakableSpecification","cssSelector":["h1",".hero-lead","#faq .faq-question"]}}
- Complete <style> block with ALL CSS; use font-display: swap on all font declarations

### [2] CSS
Design tokens as CSS custom properties. Styles needed:
- Reset, body, typography, links
- Sticky nav (backdrop blur, .nav-brand gold, .nav-age badge)
- .hero breadcrumb, H1, lead para, author meta, trust bar (.trust-bar pills)
- .section, .content-section max-width 1200px centered
- Casino grid: 4-col → 2-col (<900px) → 1-col (<640px)
- .casino-card (same as homepage), .rank-badge (.rank-1 gold, .rank-2 silver, .rank-3 bronze, .rank-other), .hot-badge red, .payid-verified-badge (small green pill top-right)
- .cta-btn (green), .review-link (muted underline)
- .how-to-box (card with gold left border, numbered steps as flex rows)
- .method-grid (3-col → 1-col) for "What is PayID" e-wallet comparison
- .data-table full-width, .table-wrap overflow-x:auto, alternating rows
- .speed-fast (green pill), .speed-med (gold pill), .speed-slow (red pill)
- .comp-play button (green, small)
- FAQ accordion (.faq-list, .faq-item, .faq-question, .faq-answer, .faq-icon)
- .rg-strip red left-border
- Footer dark, brand, nav, disclaimer, copyright
- Mobile: CTA full-width, nav-links hidden

### [3] STICKY NAV
.nav-brand "{site['brand']}" → {site['domain']}/
Nav links: "Top Casinos" ({site['domain']}/) | "Guides" ({site['domain']}/guides/best-payid-casinos/) | "Banking" ({site['domain']}/banking/payid-casino-deposits/) | "FAQ" (#faq)
.nav-age "18+"

### [4] HERO
Breadcrumb: <a href="{site['domain']}/">Home</a> › <a href="{site['domain']}/guides/">Guides</a> › Best PayID Casinos Australia
<h1>Best <span style="color:{design['gold']}">PayID Casino</span> Australia {site['year']}</h1>
Lead (2–3 sentences, class="hero-lead"): PayID is Australia's #1 casino deposit method — instant bank transfers, zero fees, 24/7, all major AU banks. Explain why it beats credit cards and international e-wallets for Aussie punters. Mention popular with NSW, VIC and QLD punters.
Author: "<a href='{site['domain']}/about/'>{site['author']}</a>" · "Updated {TODAY_PRETTY}" · "5 PayID casinos reviewed"
.trust-bar pills: "✓ Expert Tested" · "✓ Real PayID Deposits Verified" · "✓ All Banks Confirmed" · "✓ Payouts Timed"

### [4b] TABLE OF CONTENTS
Compact .toc-box (gold left border) after hero, before first content section:
<nav class="toc-box" aria-label="Page contents">
  <p class="toc-title">In This Guide</p>
  <ol class="toc-list">
    <li><a href="#what-is-payid">What is PayID?</a></li>
    <li><a href="#top-payid-casinos">Top 5 PayID Casinos</a></li>
    <li><a href="#withdrawal-times">Withdrawal Speed</a></li>
    <li><a href="#payid-vs-others">PayID vs Other Methods</a></li>
    <li><a href="#payid-withdrawals">How to Withdraw</a></li>
    <li><a href="#faq">FAQ</a></li>
  </ol>
</nav>

### [5] WHAT IS PAYID? (H2 — write this yourself)
<section class="content-section" id="what-is-payid">
  <h2>What is <span>PayID</span>?</h2>
  Write 3 paragraphs (~250 words):
  - Para 1: PayID defined — Australia's NPP instant payment system, how it links a phone/email to a bank account. Launched 2018. Regulated by Reserve Bank of Australia.
  - Para 2: How it works at casinos specifically — casino provides a PayID alias, punter sends from banking app, funds credit instantly. No card details, no third-party wallet. Major banks: CommBank, ANZ, NAB, Westpac, ING, Bendigo, Macquarie, St.George, Bank of Queensland, Suncorp + 90 others.
  - Para 3: Why PayID beats other methods for online pokies — instant deposits, real-time withdrawals (under 5 min at top casinos), zero fees, native AUD (no currency conversion). Contrast with Visa (2–5 days withdrawal), crypto (requires wallet setup).
  Then: .how-to-box "How to Deposit with PayID — Step by Step":
  1. Choose a PayID casino from our list below
  2. Register and log in to your account
  3. Go to Cashier → select PayID as deposit method
  4. Copy the casino's PayID address (phone number or email)
  5. Open your banking app, send the amount — funds arrive in seconds
  Internal link: "See our full <a href="{site['domain']}/banking/payid-casino-deposits/">PayID casino deposits guide</a> →"

### [6] TOP 5 PAYID CASINOS RANKED (H2) — embed cards VERBATIM
<section class="section" id="top-payid-casinos">
  <h2>Top <span>5</span> Best PayID Casinos Australia {site['year']}</h2>
  <p>These are the only casinos on our list with confirmed PayID support — tested with real deposits and real withdrawals by {site['author']}. Ranked by overall score.</p>
  <div class="casino-grid">
{casino_cards}
  </div>
  <p style="font-size:13px;color:var(--muted);margin-top:16px;">T&amp;Cs apply. 18+ only. Gamble responsibly. <a href="{site['domain']}/">See all 8 casinos →</a></p>
</section>

### [7] PAYID WITHDRAWAL TIMES TABLE (H2) — embed table VERBATIM
<section class="content-section" id="withdrawal-times">
  <h2>PayID Withdrawal <span>Speed Comparison</span></h2>
  <p>We timed PayID withdrawals at each casino with a real AUD withdrawal request. Times below reflect processing after casino approval.</p>
  <div class="table-wrap">
    <table class="data-table" aria-label="PayID withdrawal times by casino">
      <thead><tr><th>Casino</th><th>Min Deposit</th><th>Deposit Speed</th><th>Withdrawal Speed</th><th>Fees</th><th>Action</th></tr></thead>
      <tbody>
{withdrawal_tbl}
      </tbody>
    </table>
  </div>
  <p style="font-size:13px;color:var(--muted);margin-top:12px;">Times tested March {site['year']}. Speeds may vary during peak periods. Complete KYC before first withdrawal to avoid delays.</p>
</section>

### [8] PAYID vs OTHER METHODS (H2 — write this yourself)
<section class="content-section" id="payid-vs-others">
  <h2>PayID vs Other <span>AU Casino Payment Methods</span></h2>
  Intro (1 sentence).
  Table:
  | Method | Deposit Speed | Withdrawal | Fees | AU Banks Required | Best For |
  | PayID | Instant | Under 5 min | Free | Yes (all major) | Speed + zero fees |
  | POLi | Instant | N/A | Free | Yes | Deposits only |
  | Visa / Mastercard | Instant | 2–5 days | Usually free | No | Convenience |
  | Bank Transfer | 1–3 days | 1–5 days | Free | Yes | Large amounts |
  | Bitcoin | Instant | 5–10 min | Network fee | No | Privacy + crypto |
  | Solana (SOL) | Instant | Under 1 min | Network fee | No | Fastest crypto |
  Closing paragraph: recommend PayID for AUD punters who want speed with zero fees.

### [9] HOW TO WITHDRAW WITH PAYID (H2 — write this yourself)
<section class="content-section" id="payid-withdrawals">
  <h2>How to Withdraw with <span>PayID</span></h2>
  Write ~150 words + 4-step numbered process:
  1. Go to Cashier → Withdraw → select PayID
  2. Enter your PayID (the same phone/email you deposited from)
  3. Enter withdrawal amount (min $50 at most casinos)
  4. Confirm — funds arrive in your bank within minutes
  Tips: complete KYC before first withdrawal, withdraw to the same PayID you deposited from, avoid peak processing times.
  Name {payid[0]['name']} and {payid[1]['name']} as fastest examples. Internal links: <a href="{site['domain']}/banking/payid-casino-deposits/">PayID Casino Deposits guide</a>, <a href="{site['domain']}/reviews/stake96/">Stake96 Casino review</a>, <a href="{site['domain']}/reviews/stakebro77/">StakeBro77 review</a>.

### [10] FAQ ACCORDION (5 questions — match FAQPage JSON-LD exactly)
<section class="content-section" id="faq">
  <h2>Frequently Asked <span>Questions</span></h2>
  <div class="faq-list">
    Q1: What is PayID and how does it work at Australian online casinos?
    Q2: Which is the best PayID casino in Australia in {site['year']}?
    Q3: How do I deposit with PayID at an online casino?
    Q4: How fast are PayID casino withdrawals in Australia?
    Q5: Are PayID casino deposits safe in Australia?
  </div>
  Vanilla JS accordion — one open at a time, aria-expanded.

### [11] RESPONSIBLE GAMBLING STRIP
Compact .rg-strip: "18+ only | Free help: 1800 858 858 · gamblinghelponline.org.au"

### [12] FOOTER
- .footer-brand "{site['brand']}" → {site['domain']}/
- Nav: <a href="{site['domain']}/">Top Casinos</a> | <a href="{site['domain']}/reviews/">Reviews</a> | <a href="{site['domain']}/guides/best-payid-casinos/">PayID Guide</a> | <a href="{site['domain']}/banking/payid-casino-deposits/">Banking</a> | <a href="{site['domain']}/about/">About</a>
- Disclaimer: affiliate site, 18+, offshore casinos, IGA note, gamble responsibly
- © {site['year']} {site['brand']}

---

## TECHNICAL
- Single self-contained HTML — ALL CSS in <style>. No external CSS.
- Casino cards and withdrawal table: embed VERBATIM — do not modify or regenerate them.
- Mobile responsive. CTA buttons full-width on mobile. Tables: overflow-x:auto.
- FAQ accordion: vanilla JS only, no libraries.
- Google Fonts only external dependency.
- ALL affiliate links: target="_blank" rel="nofollow noopener sponsored"

Return ONLY raw HTML. Start with <!DOCTYPE html>. No markdown. No explanation. Do not truncate."""


def build_guide_ewallet_prompt(site: dict, casinos: list, design: dict, keywords: dict) -> str:
    primary_kws  = ", ".join(f'"{k}"' for k in keywords["primary"])
    longtail_kws = "\n".join(f"- {k}" for k in keywords["long_tail"])
    kw_rules     = "\n".join(f"- {r}" for r in keywords["rules"])

    # Pre-render PayID casinos for the PayID deep-dive section
    payid = _payid_casinos(casinos)
    payid_cards    = _payid_casino_cards_html(payid)
    withdrawal_tbl = _payid_withdrawal_table_html(payid)
    faq_schema     = _payid_faq_schema(site, payid)

    itemlist = ", ".join(
        f'{{"@type":"ListItem","position":{i+1},"name":"{c["name"]}","url":"{c["affiliate_url"]}"}}'
        for i, c in enumerate(payid)
    )
    top_names = ", ".join(c["name"] for c in payid)

    return f"""You are generating a complete production-ready HTML guide. I am providing EXACT HTML for PayID casino cards and a withdrawal table — embed them verbatim in the PayID section. Write all other sections yourself.

## SITE INFO
Brand: {site['brand']} | Domain: {site['domain']} | Author: {site['author']} | Year: {site['year']}
Canonical: {site['domain']}/guides/best-e-wallet-pokies-australia/

## DESIGN TOKENS
--bg:{design['bg']} --card-bg:{design['card_bg']} --border:{design['border']} --gold:{design['gold']} --green:{design['green']} --red:{design['red']} --text:{design['text']} --muted:{design['muted']}
Fonts: '{design['font_head']}' 700/800 + '{design['font_body']}' 400/500/600 — Google Fonts

## SEO KEYWORDS
Primary: {primary_kws}
Long-tail (weave throughout — especially e-wallet variants): {longtail_kws}
Rules: {kw_rules}

---

## PAGE STRUCTURE (all sections required)

### [1] HEAD
- charset UTF-8, viewport
- <title>Best E-Wallet Pokies Australia {site['year']} — Top Sites for Instant Deposits | {site['brand']}</title>
- <meta name="description"> ~155 chars: best e-wallet pokies Australia, PayID, POLi, crypto, instant deposits, fast payouts
- <link rel="canonical" href="{site['domain']}/guides/best-e-wallet-pokies-australia/">
- <link rel="alternate" hreflang="en-AU">
- OG (type=article) + Twitter card
- Google Fonts preconnect + link
- Google Fonts preconnect + link; add <link rel="dns-prefetch" href="//fonts.googleapis.com"> and <link rel="dns-prefetch" href="//fonts.gstatic.com">
- JSON-LD Article schema (author={site['author']}, publisher={site['brand']}, datePublished={TODAY}, dateModified={TODAY})
- JSON-LD BreadcrumbList: Home ({site['domain']}/) › Guides ({site['domain']}/guides/) › Best E-Wallet Pokies Australia
- JSON-LD ItemList — top 5 PayID/e-wallet casinos (embed verbatim):
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"ItemList","name":"Best E-Wallet Pokies Australia {site['year']}","numberOfItems":5,"itemListElement":[{itemlist}]}}
</script>
- JSON-LD FAQPage (embed verbatim — questions already phrased as People Also Ask):
<script type="application/ld+json">
{faq_schema}
</script>
- Speakable JSON-LD: {{"@context":"https://schema.org","@type":"SpeakableSpecification","cssSelector":["h1",".hero-lead","#faq .faq-question"]}}
- Complete <style> block with ALL CSS; use font-display: swap on all font declarations

### [2] CSS
Design tokens as CSS custom properties. All styles matching site design system:
- Reset, body, typography, links
- Sticky nav, .nav-brand gold, .nav-age badge
- .hero, breadcrumb, H1, lead (.hero-lead class), .trust-bar pills
- .section, .content-section max-width 1200px
- .toc-box (card, gold left border, compact ol list)
- .ewallet-grid: 3-col → 1-col; .ewallet-card (card-bg, border, name h3, description, .speed-badge pill)
- Casino grid: 4-col → 2-col → 1-col
- .casino-card (same as homepage), .payid-verified-badge green pill, .cta-btn green
- .data-table, .table-wrap, .speed-fast/.speed-med/.speed-slow badges
- FAQ accordion
- .rg-strip red left-border
- Footer dark
- Mobile responsive

### [3] STICKY NAV
.nav-brand "{site['brand']}" → {site['domain']}/
Nav: "Top Casinos" ({site['domain']}/) | "PayID Guide" ({site['domain']}/guides/best-payid-casinos/) | "Banking" ({site['domain']}/banking/ewallet-casino-deposits/) | "FAQ" (#faq)
.nav-age "18+"

### [4] HERO
Breadcrumb: <a href="{site['domain']}/">Home</a> › <a href="{site['domain']}/guides/">Guides</a> › Best E-Wallet Pokies Australia
<h1>Best <span style="color:{design['gold']}">E-Wallet</span> Pokies Australia {site['year']}</h1>
Lead (2–3 sentences, class="hero-lead"): E-wallets offer instant deposits, zero fees, and a privacy layer between your bank and the casino. PayID is Australia's #1 e-wallet for pokies — native bank transfer, no third-party account needed. Popular with NSW, VIC and QLD punters.
Author: "<a href='{site['domain']}/about/'>{site['author']}</a>" · "Updated {TODAY_PRETTY}"
.trust-bar: "✓ PayID Verified" · "✓ Instant Deposits" · "✓ Zero Fees" · "✓ Expert Tested"

### [4b] TABLE OF CONTENTS
Compact .toc-box (gold left border) after hero:
<nav class="toc-box" aria-label="Page contents">
  <p class="toc-title">In This Guide</p>
  <ol class="toc-list">
    <li><a href="#ewallets">E-Wallets at AU Casinos</a></li>
    <li><a href="#top-ewallet-casinos">Top 5 Sites Ranked</a></li>
    <li><a href="#withdrawal-times">Withdrawal Speed</a></li>
    <li><a href="#payid-vs-others">E-Wallet Comparison</a></li>
    <li><a href="#faq">FAQ</a></li>
  </ol>
</nav>

### [5] E-WALLETS THAT WORK AT AU CASINO POKIES (H2 — write yourself)
<section class="content-section" id="ewallets">
  <h2>E-Wallets That Work at <span>AU Casino Pokies</span></h2>
  Intro: 1 sentence on e-wallet variety at AU casinos.
  .ewallet-grid with 5 cards:
  - **PayID** — Australia's NPP instant bank transfer. Instant deposits, under 5 min withdrawals, zero fees. Best overall. .speed-badge "INSTANT".
  - **POLi** — Direct AU bank transfer, no third-party account. Instant deposits. .speed-badge "INSTANT".
  - **Bitcoin (BTC)** — Crypto e-wallet, 5–10 min withdrawals, network fee. Best for privacy. .speed-badge "FAST".
  - **Ethereum (ETH)** — Crypto e-wallet, 10–30 min withdrawals, network fee. .speed-badge "FAST".
  - **Solana (SOL)** — Fastest crypto option, under 1 min withdrawals. .speed-badge "INSTANT".
  Each card: e-wallet name (h3), what it is (1–2 lines), .speed-badge, "Best for:" line.
  Internal link: "Full PayID deposit guide → <a href='{site['domain']}/banking/payid-casino-deposits/'>PayID Casino Deposits</a>"

### [6] TOP 5 PAYID E-WALLET CASINOS RANKED — embed cards VERBATIM
<section class="section" id="top-ewallet-casinos">
  <h2>Top <span>5</span> Best E-Wallet Pokies Sites Australia {site['year']}</h2>
  <p>Ranked by overall score. All confirmed to support PayID — Australia's best e-wallet for online pokies. <a href="{site['domain']}/" class="text-link">See all 8 casinos →</a></p>
  <div class="casino-grid">
{payid_cards}
  </div>
  <p style="font-size:13px;color:var(--muted);margin-top:16px;">T&amp;Cs apply. 18+. Gamble responsibly.</p>
</section>

### [7] PAYID WITHDRAWAL TIMES TABLE — embed VERBATIM
<section class="content-section" id="withdrawal-times">
  <h2>PayID Withdrawal <span>Speed Comparison</span></h2>
  <p>Real withdrawal times tested March {site['year']}. Complete KYC before first withdrawal to avoid delays.</p>
  <div class="table-wrap">
    <table class="data-table" aria-label="PayID e-wallet withdrawal times">
      <thead><tr><th>Casino</th><th>Min Deposit</th><th>Deposit Speed</th><th>PayID Withdrawal</th><th>Fees</th><th>Action</th></tr></thead>
      <tbody>
{withdrawal_tbl}
      </tbody>
    </table>
  </div>
  <p style="font-size:13px;color:var(--muted);margin-top:12px;">Internal link: <a href="{site['domain']}/banking/payid-casino-deposits/" class="text-link">Full PayID banking guide →</a></p>
</section>

### [8] PAYID DEEP DIVE (H2 — write ~200 words)
<section class="content-section" id="payid-deep-dive">
  <h2>PayID — <span>Australia's Best E-Wallet for Pokies</span></h2>
  Why PayID beats Skrill/Neteller for Aussie punters: native AUD (no conversion), instant NPP rails, all major banks, zero fees.
  5-step deposit process (compact numbered list).
  Bank compatibility: CommBank, ANZ, NAB, Westpac, ING, Bendigo, Macquarie + 90 others.
  Internal link: "Full guide → <a href='{site['domain']}/banking/payid-casino-deposits/'>PayID Casino Deposits</a>"

### [9] CRYPTO E-WALLETS FOR POKIES (H2 — write ~150 words)
<section class="content-section" id="crypto-ewallets">
  <h2>Crypto E-Wallets <span>for Online Pokies</span></h2>
  BTC, ETH, SOL — how to use at AU casinos, setup (exchange → wallet → casino).
  Which casinos accept crypto: Spinza96 (no KYC, instant BTC), PokieSpin96 (20+ coins).
  Pros vs PayID: faster (SOL <1 min), more privacy, no bank blocks.
  Cons: setup required, price volatility, network fees.

### [10] E-WALLET COMPARISON TABLE (H2 — write yourself)
Table: E-Wallet | Deposit Speed | Withdrawal | Fees | Account Needed | AUD Native | Best For
Rows: PayID · POLi · Bitcoin · Ethereum · Solana · Skrill · Neteller

### [11] FAQ ACCORDION (5 questions — match FAQPage JSON-LD exactly)
Q1: What is PayID and how does it work at Australian online casinos?
Q2: Which is the best PayID casino in Australia in {site['year']}?
Q3: How do I deposit with PayID at an online casino?
Q4: How fast are PayID casino withdrawals in Australia?
Q5: Are PayID casino deposits safe in Australia?
Vanilla JS accordion, one open at a time.

### [12] RESPONSIBLE GAMBLING STRIP
.rg-strip: "18+ only | Free help: 1800 858 858 · gamblinghelponline.org.au"

### [13] FOOTER
.footer-brand "{site['brand']}" → {site['domain']}/
Nav: <a href="{site['domain']}/">Top Casinos</a> | <a href="{site['domain']}/guides/best-payid-casinos/">PayID Casinos</a> | <a href="{site['domain']}/banking/payid-casino-deposits/">PayID Banking</a> | <a href="{site['domain']}/banking/ewallet-casino-deposits/">E-Wallet Banking</a> | <a href="{site['domain']}/about/">About</a>
Disclaimer + © {site['year']} {site['brand']}

---

## TECHNICAL
- Single self-contained HTML — ALL CSS in <style>.
- PayID casino cards and withdrawal table: embed VERBATIM — do not regenerate.
- Mobile responsive. Tables: <div class="table-wrap">. CTAs full-width on mobile.
- FAQ accordion: vanilla JS only.
- Google Fonts only external dependency.
- ALL affiliate links: target="_blank" rel="nofollow noopener sponsored"

Return ONLY raw HTML. Start with <!DOCTYPE html>. No markdown. No explanation. Do not truncate."""


def build_guide_pokies_prompt(site: dict, casinos: list, design: dict, keywords: dict) -> str:
    primary_kws  = ", ".join(f'"{k}"' for k in keywords["primary"])
    longtail_kws = "\n".join(f"- {k}" for k in keywords["long_tail"])
    kw_rules     = "\n".join(f"- {r}" for r in keywords["rules"])
    top3_summary = json.dumps(
        [{"rank": c["rank"], "name": c["name"], "score": c["score"],
          "bonus": c["bonus"], "review_url": c["review_url"],
          "affiliate_url": c["affiliate_url"]} for c in casinos[:3]],
        indent=2
    )
    return f"""Generate a complete, production-ready HTML guide page: "How to Play Pokies Online Australia {site['year']}".

## SITE INFO
- Brand: {site['brand']}
- Domain: {site['domain']}
- Author: {site['author']}
- Year: {site['year']}
- Canonical URL: {site['domain']}/guides/how-to-play-pokies/

## DESIGN TOKENS (match all other pages exactly)
- Body bg: {design['bg']}, Card bg: {design['card_bg']}, Border: {design['border']}
- Gold: {design['gold']}, CTA green: {design['green']}, Text: {design['text']}, Muted: {design['muted']}
- Fonts: {design['font_head']} (700/800) + {design['font_body']} (400/500/600) via Google Fonts

## SEO KEYWORDS
Primary: {primary_kws}
Long-tail (weave throughout):
{longtail_kws}
Content rules: {kw_rules}

## TOP 3 CASINOS TO RECOMMEND (use for CTA section)
{top3_summary}

## REQUIRED PAGE STRUCTURE

### 1. HEAD
- charset UTF-8, viewport
- <title>: How to Play Pokies Online Australia {site['year']} – Beginner's Complete Guide | {site['brand']}
- <meta description>: under 160 chars — pokies, RTP, how to play, Australia, real money, beginner guide
- Canonical: {site['domain']}/guides/how-to-play-pokies/
- OG (type=article), Twitter card, hreflang en-AU
- Google Fonts
- JSON-LD: Article schema (author={site['author']}, publisher={site['brand']}, datePublished={TODAY})
- JSON-LD: BreadcrumbList: Home ({site['domain']}/) › Guides ({site['domain']}/guides/) › How to Play Pokies Online
- JSON-LD: FAQPage — 5 Q&As (are pokies rigged, best RTP pokies, min bet, pokies vs slots, how to win)
- All CSS in <style>

### 2. STICKY NAV
### 3. HERO
- Breadcrumb: Home › Guides › How to Play Pokies Online
- H1: "How to Play Pokies Online in Australia ({site['year']} Guide)"
- Lead: 2 sentences — what this guide covers, suitable for beginners and returning punters
- Author byline + date

### 4. WHAT ARE ONLINE POKIES? (H2)
- Definition (AU-specific: pokies = slots), history, why Aussies love them
- "Pokies vs Slots" callout box — explain the terminology

### 5. HOW POKIES WORK (H2)
Sub-sections as cards or numbered steps:
- RTP (Return to Player) — what it means, typical range 94–97%, why it matters
- Volatility — low vs medium vs high, which suits which player type
- Paylines & Ways to Win — fixed lines, cluster pays, Megaways
- Bonus Features — free spins, multipliers, sticky wilds, bonus rounds

### 6. HOW TO PLAY: STEP BY STEP (H2)
Numbered step guide (6 steps):
1. Choose a trusted AU casino (link to index)
2. Register and claim your welcome bonus
3. Deposit with PayID or crypto
4. Find a pokie — filter by RTP, theme, provider
5. Set your bet size and bankroll limit
6. Spin and understand the paytable

### 7. BANKROLL TIPS (H2)
5 bullet tips for responsible, smart play. Keep authoritative tone, not lecture-y.

### 8. BEST POKIES TO PLAY IN {site['year']} (H2)
List 8 specific pokie titles (e.g. Gates of Olympus, Sweet Bonanza, Book of Dead, Wanted Dead or a Wild, Gonzo's Quest, Reactoonz, Fire Joker, Dog House) with RTP and provider.

### 9. WHERE TO PLAY (H2)
3-card mini CTA section using top 3 casinos above. Each card: name, score, bonus, "Play Now →" → affiliate_url (target="_blank" rel="nofollow noopener sponsored").

### 10. FAQ ACCORDION (5 questions — same as FAQPage JSON-LD)
### 11. FOOTER

## TECHNICAL REQUIREMENTS
Single self-contained HTML — all CSS in <style>. Mobile responsive. Google Fonts only. Budget CSS to avoid truncation — you MUST reach </body></html>.

Return ONLY raw HTML. No markdown. No explanation. Start with <!DOCTYPE html>. Do not truncate."""


def build_guide_crypto_prompt(site: dict, casinos: list, design: dict, keywords: dict) -> str:
    primary_kws  = ", ".join(f'"{k}"' for k in keywords["primary"])
    longtail_kws = "\n".join(f"- {k}" for k in keywords["long_tail"])
    _info = [k for k in keywords["informational"] if "[casino name]" not in k.lower()]
    info_kws     = "\n".join(f"- {k}" for k in _info)
    kw_rules     = "\n".join(f"- {r}" for r in keywords["rules"])
    all_summary = json.dumps(
        [{"rank": c["rank"], "name": c["name"], "score": c["score"], "bonus": c["bonus"],
          "tags": c["tags"], "review_url": c["review_url"], "affiliate_url": c["affiliate_url"]} for c in casinos],
        indent=2
    )
    return f"""Generate a complete, production-ready HTML guide page: "Best Crypto Casino Australia {site['year']}".

## SITE INFO
Brand: {site['brand']} | Domain: {site['domain']} | Author: {site['author']} | Year: {site['year']}
Canonical URL: {site['domain']}/guides/best-crypto-casinos/

## DESIGN TOKENS
--bg:{design['bg']} --card-bg:{design['card_bg']} --border:{design['border']} --gold:{design['gold']} --green:{design['green']} --red:{design['red']} --text:{design['text']} --muted:{design['muted']}
Fonts: '{design['font_head']}' 700/800 + '{design['font_body']}' 400/500/600 via Google Fonts

## SEO KEYWORDS
Primary: {primary_kws}
Long-tail: {longtail_kws}
Informational FAQs: {info_kws}
Rules: {kw_rules}

## CASINO DATA
{all_summary}

## PAGE STRUCTURE

### HEAD
- <title>: Best Crypto Casino Australia {site['year']} – No KYC, Instant BTC & SOL Payouts | {site['brand']}
- <meta description>: under 160 chars — crypto casino Australia, no KYC, Bitcoin, Solana, fast payouts
- Canonical: {site['domain']}/guides/best-crypto-casinos/
- OG (type=article), Twitter card, hreflang en-AU
- Google Fonts preconnect + link; add <link rel="dns-prefetch" href="//fonts.googleapis.com"> and <link rel="dns-prefetch" href="//fonts.gstatic.com">
- JSON-LD: Article schema (author={site['author']}, publisher={site['brand']}, datePublished={TODAY}, dateModified={TODAY})
- JSON-LD: BreadcrumbList: Home ({site['domain']}/) › Guides ({site['domain']}/guides/) › Best Crypto Casino Australia
- JSON-LD: ItemList — top 5 crypto casinos with affiliate_url
- JSON-LD: FAQPage — 5 Q&As phrased as People Also Ask patterns (which crypto casinos are safe for AU players, is Bitcoin gambling legal in Australia, how fast are crypto casino withdrawals in Australia, which crypto casino has no KYC in Australia, what is the best crypto for casino withdrawals)
- Speakable JSON-LD: {{"@context":"https://schema.org","@type":"SpeakableSpecification","cssSelector":["h1",".hero-lead","#faq .faq-question"]}}
- All CSS in <style>; use font-display: swap on all font declarations

### BODY SECTIONS (in order)
1. **Sticky nav** — same as all pages
2. **Hero** — H1: "Best Crypto Casino Australia {site['year']}" ("Crypto" in gold). Lead (class="hero-lead"): why crypto is the fastest AU withdrawal method. Author <a href="{site['domain']}/about/">{site['author']}</a> + date.
3. **Table of Contents** — compact .toc-box (gold left border) with jump links to each section below. Add id= attributes to matching sections.
4. **Why Crypto for AU Casinos (H2)** — 3 reasons: instant withdrawals, privacy, no IGA-driven bank blocks. Mention BTC, ETH, SOL, XRP. Mention NSW and VIC punters specifically.
5. **Top Crypto Casinos Ranked (H2)** — ALL 8 casino cards (same card format as homepage: rank badge, name, bonus green, score, tags, "Play Now →" + "Read Review" buttons). ALL affiliate links: target="_blank" rel="nofollow noopener sponsored".
6. **Supported Cryptocurrencies (H2)** — Grid of 5 crypto cards: Bitcoin · Ethereum · Solana · Litecoin · XRP. Each: name, speed badge, best for, which casinos accept it.
7. **No-KYC Crypto Casinos Explained (H2)** — What no-KYC means, why AU punters want it, how to sign up anonymously (3-step process). Mention Spinza96 and PokieSpin96 specifically. Internal links: <a href="{site['domain']}/reviews/spinza96/">Spinza96 review</a>, <a href="{site['domain']}/reviews/pokiespin96/">PokieSpin96 review</a>.
8. **Crypto vs PayID Comparison (H2)** — Table: Method | Speed | Fees | Anonymity | Min Deposit | Best For. Internal link: <a href="{site['domain']}/guides/best-payid-casinos/">best PayID casinos guide</a>.
9. **FAQ Accordion** — 5 questions (vanilla JS). Same Q&A text as FAQPage JSON-LD. Phrased as People Also Ask.
10. **Responsible Gambling strip** (red left-border box, 1800 858 858)
11. **Footer** — same as all pages. Footer nav includes: Home | Reviews | Guides | About | Privacy Policy | Terms & Conditions.

## TECHNICAL
Single self-contained HTML — all CSS in <style>. Mobile responsive. Google Fonts only. font-display: swap. Budget CSS to avoid truncation — you MUST reach </body></html>.
Return ONLY raw HTML. No markdown. No explanation. Start with <!DOCTYPE html>. Do not truncate."""


def build_guide_best_pokies_prompt(site: dict, casinos: list, design: dict, keywords: dict) -> str:
    primary_kws  = ", ".join(f'"{k}"' for k in keywords["primary"])
    longtail_kws = "\n".join(f"- {k}" for k in keywords["long_tail"])
    _info = [k for k in keywords["informational"] if "[casino name]" not in k.lower()]
    info_kws     = "\n".join(f"- {k}" for k in _info)
    kw_rules     = "\n".join(f"- {r}" for r in keywords["rules"])
    all_summary = json.dumps(
        [{"rank": c["rank"], "name": c["name"], "score": c["score"], "bonus": c["bonus"],
          "tags": c["tags"], "review_url": c["review_url"], "affiliate_url": c["affiliate_url"]} for c in casinos],
        indent=2
    )
    return f"""Generate a complete, production-ready HTML guide page: "Best Online Pokies Australia {site['year']}".

## SITE INFO
Brand: {site['brand']} | Domain: {site['domain']} | Author: {site['author']} | Year: {site['year']}
Canonical URL: {site['domain']}/guides/best-pokies-australia/

## DESIGN TOKENS
--bg:{design['bg']} --card-bg:{design['card_bg']} --border:{design['border']} --gold:{design['gold']} --green:{design['green']} --red:{design['red']} --text:{design['text']} --muted:{design['muted']}
Fonts: '{design['font_head']}' 700/800 + '{design['font_body']}' 400/500/600 via Google Fonts

## SEO KEYWORDS
Primary: {primary_kws}
Long-tail: {longtail_kws}
Informational FAQs: {info_kws}
Rules: {kw_rules}

## CASINO DATA
{all_summary}

## PAGE STRUCTURE

### HEAD
- <title>: Best Online Pokies Australia {site['year']} – Top Real Money Pokies Sites | {site['brand']}
- <meta description>: under 160 chars — best online pokies Australia, real money, PayID, top pokies sites 2026
- Canonical: {site['domain']}/guides/best-pokies-australia/
- OG (type=article), Twitter card, hreflang en-AU
- Google Fonts preconnect + link; add <link rel="dns-prefetch" href="//fonts.googleapis.com"> and <link rel="dns-prefetch" href="//fonts.gstatic.com">
- JSON-LD: Article schema (author={site['author']}, publisher={site['brand']}, datePublished={TODAY}, dateModified={TODAY})
- JSON-LD: BreadcrumbList: Home ({site['domain']}/) › Guides ({site['domain']}/guides/) › Best Online Pokies Australia
- JSON-LD: ItemList — top 5 pokies casinos
- JSON-LD: FAQPage — 5 Q&As phrased as People Also Ask (are online pokies rigged in Australia, what is the best RTP online pokie Australia, can you win real money playing online pokies in Australia, which online casino has the most pokies in Australia, do online pokies pay more at certain times)
- Speakable JSON-LD: {{"@context":"https://schema.org","@type":"SpeakableSpecification","cssSelector":["h1",".hero-lead","#faq .faq-question"]}}
- All CSS in <style>; use font-display: swap on all font declarations

### BODY SECTIONS (in order)
1. **Sticky nav**
2. **Hero** — H1: "Best Online Pokies Australia {site['year']}" ("Pokies" in gold). Lead (class="hero-lead"): what makes a top pokies site (library size, RTP, PayID banking). Author <a href="{site['domain']}/about/">{site['author']}</a> + date.
3. **Table of Contents** — compact .toc-box (gold left border) with jump links to each section. Add matching id= attributes to section headings.
4. **Top Pokies Sites Ranked (H2)** — ALL 8 casino cards (same card format as homepage). ALL affiliate links: target="_blank" rel="nofollow noopener sponsored". Mention this list is popular with NSW and VIC punters.
5. **What Makes a Great Pokies Site? (H2)** — 4-card criteria grid: Library Size · RTP Range · Bonus Offers · PayID Speed. Each with icon + 2 sentences.
6. **Top 10 Pokies to Play in {site['year']} (H2)** — Table with 10 specific titles: Name | Provider | RTP | Volatility | Best Feature. Include: Gates of Olympus (Pragmatic, 96.5%, High), Sweet Bonanza (Pragmatic, 96.5%, High), Book of Dead (Play'n GO, 96.2%, High), Wanted Dead or a Wild (Hacksaw, 96.38%, High), Gonzo's Quest (NetEnt, 96%, Med), Reactoonz (Play'n GO, 96.3%, High), Dog House (Pragmatic, 96.51%, High), Fire Joker (Play'n GO, 96.15%, Med), Razor Shark (Push Gaming, 96.7%, High), Starburst (NetEnt, 96.1%, Low).
7. **Pokies Providers at AU Casinos (H2)** — Grid of 6 provider cards: Pragmatic Play · Evolution · Hacksaw Gaming · Play'n GO · NetEnt · Push Gaming. Each: name, speciality, flagship title.
8. **PayID Pokies Australia (H2)** — Why PayID is the best deposit method for pokies. Internal links: <a href="{site['domain']}/guides/best-payid-casinos/">best PayID casinos</a>, <a href="{site['domain']}/banking/payid-casino-deposits/">PayID deposits guide</a>, <a href="{site['domain']}/reviews/stake96/">Stake96 Casino review</a>. Step-by-step deposit guide.
9. **FAQ Accordion** — 5 questions phrased as People Also Ask (same as FAQPage JSON-LD). Vanilla JS.
10. **Responsible Gambling strip**
11. **Footer** — same as all pages. Footer nav includes: Home | Reviews | Guides | About | Privacy Policy | Terms & Conditions.

## TECHNICAL
Single self-contained HTML — all CSS in <style>. Mobile responsive. Google Fonts only. font-display: swap. Budget CSS to avoid truncation — you MUST reach </body></html>.
Return ONLY raw HTML. No markdown. No explanation. Start with <!DOCTYPE html>. Do not truncate."""


def build_guide_fast_payout_prompt(site: dict, casinos: list, design: dict, keywords: dict) -> str:
    primary_kws  = ", ".join(f'"{k}"' for k in keywords["primary"])
    longtail_kws = "\n".join(f"- {k}" for k in keywords["long_tail"])
    _info = [k for k in keywords["informational"] if "[casino name]" not in k.lower()]
    info_kws     = "\n".join(f"- {k}" for k in _info)
    kw_rules     = "\n".join(f"- {r}" for r in keywords["rules"])
    # Sort by payout speed (proxy: score, but flag PayID casinos first)
    payid_casinos = [c for c in casinos if "PayID" in " ".join(c["tags"] + [c["best_for"]])]
    all_summary = json.dumps(
        [{"rank": c["rank"], "name": c["name"], "score": c["score"], "bonus": c["bonus"],
          "tags": c["tags"], "best_for": c["best_for"], "review_url": c["review_url"],
          "affiliate_url": c["affiliate_url"]} for c in casinos],
        indent=2
    )
    top_payid_names = " and ".join(c["name"] for c in payid_casinos[:2]) if payid_casinos else "Stake96"
    return f"""Generate a complete, production-ready HTML guide page: "Fast Payout Casinos Australia {site['year']}".

## SITE INFO
Brand: {site['brand']} | Domain: {site['domain']} | Author: {site['author']} | Year: {site['year']}
Canonical URL: {site['domain']}/guides/fast-payout-casinos/

## DESIGN TOKENS
--bg:{design['bg']} --card-bg:{design['card_bg']} --border:{design['border']} --gold:{design['gold']} --green:{design['green']} --red:{design['red']} --text:{design['text']} --muted:{design['muted']}
Fonts: '{design['font_head']}' 700/800 + '{design['font_body']}' 400/500/600 via Google Fonts

## SEO KEYWORDS
Primary: {primary_kws}
Long-tail: {longtail_kws}
Informational FAQs: {info_kws}
Rules: {kw_rules}

## CASINO DATA
{all_summary}

## PAGE STRUCTURE

### HEAD
- <title>: Fast Payout Casinos Australia {site['year']} – Instant PayID Withdrawals | {site['brand']}
- <meta description>: under 160 chars — fast payout casino Australia, instant PayID withdrawals, same-day pokies payouts
- Canonical: {site['domain']}/guides/fast-payout-casinos/
- OG (type=article), Twitter card, hreflang en-AU
- Google Fonts preconnect + link; add <link rel="dns-prefetch" href="//fonts.googleapis.com"> and <link rel="dns-prefetch" href="//fonts.gstatic.com">
- JSON-LD: Article schema (author={site['author']}, publisher={site['brand']}, datePublished={TODAY}, dateModified={TODAY})
- JSON-LD: BreadcrumbList: Home ({site['domain']}/) › Guides ({site['domain']}/guides/) › Fast Payout Casinos Australia
- JSON-LD: ItemList — top 5 fastest payout casinos
- JSON-LD: FAQPage — 5 Q&As phrased as People Also Ask (what is the fastest paying online casino in Australia, how long do PayID casino withdrawals take in Australia, which online casino pays out instantly in Australia, can I withdraw from an online casino the same day in Australia, why is my casino withdrawal taking so long)
- Speakable JSON-LD: {{"@context":"https://schema.org","@type":"SpeakableSpecification","cssSelector":["h1",".hero-lead","#faq .faq-question"]}}
- All CSS in <style>; use font-display: swap on all font declarations

### BODY SECTIONS (in order)
1. **Sticky nav**
2. **Hero** — H1: "Fast Payout Casinos Australia {site['year']}" ("Fast Payout" in gold). Lead (class="hero-lead"): payout speed is the #1 priority for Aussie punters — {top_payid_names} process PayID in under 5 minutes. Author <a href="{site['domain']}/about/">{site['author']}</a> + date. Trust bar: "Real Withdrawals Tested · PayID Verified · Updated {site['year']}".
3. **Table of Contents** — compact .toc-box (gold left border) with jump links to each section. Add matching id= attributes.
4. **Top Fast Payout Casinos Ranked (H2)** — ALL 8 casino cards (same card format as homepage — include payout speed indicator on each card from score_breakdown["Payout Speed"]). ALL affiliate links: target="_blank" rel="nofollow noopener sponsored". Note this is the most-searched feature by QLD and NSW punters.
5. **Payout Methods Compared (H2)** — Table: Method | Typical Time | Fees | Min Withdrawal | Available At. Rows: PayID (under 5 min) · Bitcoin (5–10 min) · Ethereum (10–20 min) · Solana (under 1 min) · Bank Transfer (1–3 days) · Credit Card (3–5 days).
6. **How PayID Withdrawals Work (H2)** — Step-by-step: 5 steps from requesting withdrawal to money in bank. Include timing expectations and tips. Internal links: <a href="{site['domain']}/banking/payid-casino-deposits/">PayID casino deposits guide</a>, <a href="{site['domain']}/reviews/stake96/">Stake96 review</a>.
7. **What Slows Down Casino Payouts? (H2)** — 4 common reasons as cards: pending KYC verification · bonus wagering incomplete · manual review periods · bank processing delays. Practical tips for each.
8. **Instant Payout Casinos vs Standard (H2)** — Comparison table: Feature | Instant Payout | Standard. Highlight PayID advantage.
9. **FAQ Accordion** — 5 questions phrased as People Also Ask (same as FAQPage JSON-LD). Vanilla JS.
10. **Responsible Gambling strip**
11. **Footer** — same as all pages. Footer nav includes: Home | Reviews | Guides | About | Privacy Policy | Terms & Conditions.

## TECHNICAL
Single self-contained HTML — all CSS in <style>. Mobile responsive. Google Fonts only. font-display: swap. Budget CSS to avoid truncation — you MUST reach </body></html>.
Return ONLY raw HTML. No markdown. No explanation. Start with <!DOCTYPE html>. Do not truncate."""


def build_guide_no_deposit_prompt(site: dict, casinos: list, design: dict, keywords: dict) -> str:
    primary_kws  = ", ".join(f'"{k}"' for k in keywords["primary"])
    longtail_kws = "\n".join(f"- {k}" for k in keywords["long_tail"])
    _info = [k for k in keywords["informational"] if "[casino name]" not in k.lower()]
    info_kws     = "\n".join(f"- {k}" for k in _info)
    kw_rules     = "\n".join(f"- {r}" for r in keywords["rules"])
    all_summary = json.dumps(
        [{"rank": c["rank"], "name": c["name"], "score": c["score"], "bonus": c["bonus"],
          "wagering": c["wagering"], "tags": c["tags"], "review_url": c["review_url"],
          "affiliate_url": c["affiliate_url"]} for c in casinos],
        indent=2
    )
    lowest = min(casinos, key=lambda c: int(c["wagering"].replace("x", "")))
    return f"""Generate a complete, production-ready HTML guide page: "No Deposit Bonus Casino Australia {site['year']}".

## SITE INFO
Brand: {site['brand']} | Domain: {site['domain']} | Author: {site['author']} | Year: {site['year']}
Canonical URL: {site['domain']}/guides/no-deposit-bonus/

## DESIGN TOKENS
--bg:{design['bg']} --card-bg:{design['card_bg']} --border:{design['border']} --gold:{design['gold']} --green:{design['green']} --red:{design['red']} --text:{design['text']} --muted:{design['muted']}
Fonts: '{design['font_head']}' 700/800 + '{design['font_body']}' 400/500/600 via Google Fonts

## SEO KEYWORDS
Primary: {primary_kws}
Long-tail: {longtail_kws}
Informational FAQs: {info_kws}
Rules: {kw_rules}

## CASINO DATA
{all_summary}
Note: {lowest['name']} has the lowest wagering at {lowest['wagering']} — highlight as best value bonus pick.

## PAGE STRUCTURE

### HEAD
- <title>: No Deposit Bonus Casino Australia {site['year']} – Free Spins & Bonus Codes | {site['brand']}
- <meta description>: under 160 chars — no deposit bonus casino Australia, free spins, PayID casino no deposit, bonus codes 2026
- Canonical: {site['domain']}/guides/no-deposit-bonus/
- OG (type=article), Twitter card, hreflang en-AU
- Google Fonts preconnect + link; add <link rel="dns-prefetch" href="//fonts.googleapis.com"> and <link rel="dns-prefetch" href="//fonts.gstatic.com">
- JSON-LD: Article schema (author={site['author']}, publisher={site['brand']}, datePublished={TODAY}, dateModified={TODAY})
- JSON-LD: BreadcrumbList: Home ({site['domain']}/) › Guides ({site['domain']}/guides/) › No Deposit Bonus Casino Australia
- JSON-LD: ItemList — top 5 bonus casinos
- JSON-LD: FAQPage — 5 Q&As phrased as People Also Ask (what is a no deposit bonus at an Australian casino, how do I claim a no deposit bonus in Australia, what are the wagering requirements on no deposit bonuses in Australia, which Australian casino has the best no deposit bonus, can I withdraw winnings from a no deposit bonus in Australia)
- Speakable JSON-LD: {{"@context":"https://schema.org","@type":"SpeakableSpecification","cssSelector":["h1",".hero-lead","#faq .faq-question"]}}
- All CSS in <style>; use font-display: swap on all font declarations

### BODY SECTIONS (in order)
1. **Sticky nav**
2. **Hero** — H1: "No Deposit Bonus Casino Australia {site['year']}" ("No Deposit Bonus" in gold). Lead (class="hero-lead"): how to claim free spins and bonus cash without depositing first. Author <a href="{site['domain']}/about/">{site['author']}</a> + date. Disclaimer badge: "T&Cs apply. 18+ only."
3. **Table of Contents** — compact .toc-box (gold left border) with jump links to each section. Add matching id= attributes.
4. **Top Bonus Casinos Ranked (H2)** — ALL 8 casino cards showing bonus + wagering prominently (same card format as homepage). Wagering requirement shown below bonus in muted text. ALL affiliate links: target="_blank" rel="nofollow noopener sponsored". Popular with NSW, VIC and QLD punters.
5. **Types of Casino Bonuses (H2)** — 4-card grid: No Deposit Bonus · Welcome Deposit Bonus · Free Spins · Reload Bonus. Each: definition (2 sentences), typical terms, best for type of punter.
6. **Bonus Comparison Table (H2)** — All 8 casinos: Casino | Bonus Offer | Wagering | Min Deposit | Best For | Claim. Link affiliate URLs in Claim column with rel="nofollow noopener sponsored".
7. **How to Claim a No Deposit Bonus (H2)** — 5-step numbered guide. Include note about PayID as verification method at some casinos. Internal link: <a href="{site['domain']}/guides/best-payid-casinos/">best PayID casinos</a>.
8. **Wagering Requirements Explained (H2)** — How wagering works, examples with maths, tips to find low-wagering bonuses. Highlight {lowest['name']} at {lowest['wagering']} as the best value pick. Internal links: <a href="{site['domain']}/reviews/spinza96/">Spinza96 review</a> (lowest wagering), <a href="{site['domain']}/reviews/stake96/">Stake96 Casino review</a>.
9. **FAQ Accordion** — 5 questions phrased as People Also Ask (same as FAQPage JSON-LD). Vanilla JS.
10. **Responsible Gambling strip**
11. **Footer** — same as all pages. Footer nav includes: Home | Reviews | Guides | About | Privacy Policy | Terms & Conditions.

## TECHNICAL
Single self-contained HTML — all CSS in <style>. Mobile responsive. Google Fonts only. font-display: swap. Budget CSS to avoid truncation — you MUST reach </body></html>.
Return ONLY raw HTML. No markdown. No explanation. Start with <!DOCTYPE html>. Do not truncate."""


def build_banking_payid_prompt(site: dict, casinos: list, design: dict, keywords: dict) -> str:
    primary_kws  = ", ".join(f'"{k}"' for k in keywords["primary"])
    longtail_kws = "\n".join(f"- {k}" for k in keywords["long_tail"])
    _info = [k for k in keywords["informational"] if "[casino name]" not in k.lower()]
    info_kws     = "\n".join(f"- {k}" for k in _info)
    kw_rules     = "\n".join(f"- {r}" for r in keywords["rules"])

    # Deterministic PayID filtering + pre-rendered HTML
    payid = _payid_casinos(casinos)
    casino_cards   = _payid_casino_cards_html(payid)
    withdrawal_tbl = _payid_withdrawal_table_html(payid)
    faq_schema     = _payid_faq_schema(site, payid)

    itemlist = ", ".join(
        f'{{"@type":"ListItem","position":{i+1},"name":"{c["name"]}","url":"{c["affiliate_url"]}"}}'
        for i, c in enumerate(payid)
    )

    return f"""You are generating a complete production-ready HTML banking guide. I am providing EXACT HTML for casino cards and withdrawal table — embed them verbatim. Write all other sections yourself.

## SITE INFO
Brand: {site['brand']} | Domain: {site['domain']} | Author: {site['author']} | Year: {site['year']}
Canonical: {site['domain']}/banking/payid-casino-deposits/

## DESIGN TOKENS
--bg:{design['bg']} --card-bg:{design['card_bg']} --border:{design['border']} --gold:{design['gold']} --green:{design['green']} --red:{design['red']} --text:{design['text']} --muted:{design['muted']}
Fonts: '{design['font_head']}' 700/800 + '{design['font_body']}' 400/500/600 — Google Fonts

## SEO KEYWORDS
Primary: {primary_kws}
Long-tail: {longtail_kws}
Informational FAQs: {info_kws}
Rules: {kw_rules}

---

## PAGE STRUCTURE (all sections required)

### [1] HEAD
- charset UTF-8, viewport
- <title>PayID Casino Deposits Australia {site['year']} — How to Deposit & Withdraw | {site['brand']}</title>
- <meta name="description"> ~155 chars: PayID casino deposits Australia, instant deposits, how to use PayID, fast pokies banking, zero fees
- <link rel="canonical" href="{site['domain']}/banking/payid-casino-deposits/">
- <link rel="alternate" hreflang="en-AU">
- OG (type=article) + Twitter card
- Google Fonts preconnect + link
- Google Fonts preconnect + link; add <link rel="dns-prefetch" href="//fonts.googleapis.com"> and <link rel="dns-prefetch" href="//fonts.gstatic.com">
- JSON-LD Article schema (author={site['author']}, publisher={site['brand']}, datePublished={TODAY}, dateModified={TODAY})
- JSON-LD BreadcrumbList: Home ({site['domain']}/) › Banking ({site['domain']}/banking/) › PayID Casino Deposits
- JSON-LD HowTo schema — "How to deposit at an online casino using PayID" — 5 steps matching section [5] exactly
- Speakable JSON-LD: {{"@context":"https://schema.org","@type":"SpeakableSpecification","cssSelector":["h1",".hero-lead","#faq .faq-question"]}}
- JSON-LD ItemList (embed verbatim):
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"ItemList","name":"Best PayID Casinos Australia {site['year']}","numberOfItems":5,"itemListElement":[{itemlist}]}}
</script>
- JSON-LD FAQPage (embed verbatim):
<script type="application/ld+json">
{faq_schema}
</script>
- Complete <style> block with ALL CSS; use font-display: swap on all font declarations

### [2] CSS
Design tokens as CSS custom properties. All styles matching the site's design system:
- Reset, body, typography, links, .text-link gold
- .toc-box (card, gold left border, compact ol list)
- Sticky nav: backdrop-filter blur, .nav-brand gold, .nav-age badge
- .hero: breadcrumb, H1, lead, author meta, .trust-bar pills
- .section, .content-section max-width 1200px centered
- Casino grid: 4-col → 2-col → 1-col responsive
- .casino-card styles (same as homepage): rank badges, .hot-badge, .payid-verified-badge green pill, .cta-btn green, .review-link muted
- .how-to-steps: numbered step cards with icon/number, title, description
- .data-table, .table-wrap (overflow-x:auto), alternating rows, .speed-fast/.speed-med/.speed-slow pills
- .comp-play green button
- .security-grid: 3-col → 1-col, .security-card with icon + text
- FAQ accordion (.faq-list, .faq-item, .faq-question, .faq-answer, .faq-icon)
- .rg-strip red left-border compact
- Footer dark, brand, nav, disclaimer, copyright
- Mobile: CTAs full-width, nav-links hidden, tables scroll

### [3] STICKY NAV
.nav-brand "{site['brand']}" → {site['domain']}/
Nav links (desktop): "Top Casinos" ({site['domain']}/) | "PayID Guide" ({site['domain']}/guides/best-payid-casinos/) | "FAQ" (#faq)
.nav-age "18+"

### [4] HERO
Breadcrumb: <a href="{site['domain']}/">Home</a> › <a href="{site['domain']}/banking/">Banking</a> › PayID Casino Deposits
<h1><span style="color:{design['gold']}">PayID</span> Casino Deposits Australia {site['year']}</h1>
Lead (2–3 sentences, class="hero-lead"): PayID is Australia's fastest casino deposit method — instant bank transfers, zero fees, 24/7, supported by all major AU banks. Processed on the New Payments Platform (NPP). Widely used by punters in NSW, VIC and QLD.
Author: "<a href='{site['domain']}/about/'>{site['author']}</a>" · "Updated {TODAY_PRETTY}" · "5 casinos tested"
.trust-bar: "✓ Real PayID Deposits Tested" · "✓ Withdrawal Times Verified" · "✓ Zero Hidden Fees"

### [4b] TABLE OF CONTENTS
Compact .toc-box (gold left border) after hero:
<nav class="toc-box" aria-label="Page contents">
  <p class="toc-title">In This Guide</p>
  <ol class="toc-list">
    <li><a href="#what-is-payid">What is PayID?</a></li>
    <li><a href="#how-to-deposit">How to Deposit</a></li>
    <li><a href="#top-payid-casinos">Top 5 Casinos</a></li>
    <li><a href="#withdrawal-times">Withdrawal Speed</a></li>
    <li><a href="#payid-vs-others">PayID vs Others</a></li>
    <li><a href="#safety">Is PayID Safe?</a></li>
    <li><a href="#faq">FAQ</a></li>
  </ol>
</nav>

### [5] WHAT IS PAYID? (H2 — write ~200 words)
How the NPP works, PayID alias (phone/email/ABN), 2018 launch, RBA-regulated.
Why it's ideal for online casino deposits — instant, free, no card number exposed to casino.
Supported banks: CommBank, ANZ, NAB, Westpac, ING, Bendigo, Macquarie, St.George, Bank of Queensland, Suncorp + 90+ others.
Internal link: "See our <a href='{site['domain']}/guides/best-payid-casinos/'>best PayID casinos guide</a> →"

### [6] HOW TO DEPOSIT WITH PAYID — STEP BY STEP (H2)
.how-to-steps with 5 numbered visual cards:
Step 1: Choose a PayID casino — use our ranked list below
Step 2: Register and verify your account
Step 3: Go to Cashier → select PayID as your deposit method
Step 4: Copy the casino's PayID address (phone number or email)
Step 5: Open your banking app → send the amount → funds credit in seconds

### [7] TOP 5 PAYID CASINOS — embed cards VERBATIM
<section class="section" id="top-payid-casinos">
  <h2>Top <span>5</span> PayID Casinos Australia {site['year']}</h2>
  <p>Confirmed PayID support — real deposits and withdrawals tested by {site['author']}. <a href="{site['domain']}/" class="text-link">See all 8 casinos →</a></p>
  <div class="casino-grid">
{casino_cards}
  </div>
  <p style="font-size:13px;color:var(--muted);margin-top:16px;">T&amp;Cs apply. 18+. Gamble responsibly.</p>
</section>

### [8] PAYID WITHDRAWAL TIMES — embed table VERBATIM
<section class="content-section" id="withdrawal-times">
  <h2>PayID Withdrawal <span>Speed by Casino</span></h2>
  <p>Real withdrawal times tested March {site['year']}. Times reflect processing after casino approval — complete KYC in advance to avoid delays.</p>
  <div class="table-wrap">
    <table class="data-table" aria-label="PayID withdrawal times">
      <thead><tr><th>Casino</th><th>Min Deposit</th><th>Deposit</th><th>Withdrawal</th><th>Fees</th><th>Action</th></tr></thead>
      <tbody>
{withdrawal_tbl}
      </tbody>
    </table>
  </div>
</section>

### [9] PAYID vs OTHER AU PAYMENT METHODS (H2 — write yourself)
Table: Method | Deposit | Withdrawal | Fees | Bank Required | Best For
Rows: PayID · POLi · Visa/Mastercard · Bank Transfer · Bitcoin · Solana (SOL)
Conclude: PayID is the best AUD option; SOL is fastest crypto.

### [10] IS PAYID SAFE AT ONLINE CASINOS? (H2 — write ~150 words)
.security-grid with 3 cards:
- NPP Encryption: what it is, bank-grade security, RBA-regulated
- No Card Exposure: casino receives only your PayID alias, not BSB/account
- Responsible Use: confirm you're using a licensed offshore casino, check gambling limits
Verdict: PayID is as safe as your banking app.

### [11] FAQ ACCORDION (5 questions — match FAQPage JSON-LD exactly)
Q1: What is PayID and how does it work at Australian online casinos?
Q2: Which is the best PayID casino in Australia in {site['year']}?
Q3: How do I deposit with PayID at an online casino?
Q4: How fast are PayID casino withdrawals in Australia?
Q5: Are PayID casino deposits safe in Australia?
Vanilla JS accordion, one open at a time, aria-expanded.

### [12] RESPONSIBLE GAMBLING STRIP
.rg-strip: "18+ only | Free confidential help: 1800 858 858 · gamblinghelponline.org.au · Lifeline 13 11 14"

### [13] FOOTER
.footer-brand "{site['brand']}" → {site['domain']}/
Nav: <a href="{site['domain']}/">Top Casinos</a> | <a href="{site['domain']}/guides/best-payid-casinos/">Best PayID Casinos</a> | <a href="{site['domain']}/reviews/">Reviews</a> | <a href="{site['domain']}/about/">About</a>
Disclaimer: affiliate site, 18+, offshore casinos, IGA note
© {site['year']} {site['brand']}

---

## TECHNICAL
- Single self-contained HTML — ALL CSS in <style>. Zero external CSS files.
- Casino cards and withdrawal table: embed VERBATIM — do not modify.
- Mobile responsive. Tables: <div class="table-wrap"> for scroll. CTAs full-width on mobile.
- FAQ accordion: vanilla JS only.
- HowTo JSON-LD steps must match section [6] step text exactly.
- Google Fonts only external dependency.
- ALL affiliate links: target="_blank" rel="nofollow noopener sponsored"

Return ONLY raw HTML. Start with <!DOCTYPE html>. No markdown. No explanation. Do not truncate."""


def _guide_prompt_shell(site, design, keywords, slug, page_title, meta_desc, h1, h1_highlight, schema_type="Article"):
    """Shared boilerplate injected into every guide/banking prompt."""
    primary_kws  = ", ".join(f'"{k}"' for k in keywords["primary"])
    longtail_kws = "\n".join(f"- {k}" for k in keywords["long_tail"])
    _info = [k for k in keywords["informational"] if "[casino name]" not in k.lower()]
    info_kws = "\n".join(f"- {k}" for k in _info)
    kw_rules = "\n".join(f"- {r}" for r in keywords["rules"])
    return {
        "header": f"""Brand: {site['brand']} | Domain: {site['domain']} | Author: {site['author']} | Year: {site['year']}
Canonical URL: {site['domain']}/{slug}/
Design: --bg:{design['bg']} --card-bg:{design['card_bg']} --border:{design['border']} --gold:{design['gold']} --green:{design['green']} --red:{design['red']} --text:{design['text']} --muted:{design['muted']}
Fonts: '{design['font_head']}' 700/800 + '{design['font_body']}' 400/500/600 via Google Fonts""",
        "head": f"""- <title>: {page_title} | {site['brand']}</title>
- <meta description>: {meta_desc}
- Canonical: {site['domain']}/{slug}/
- OG (type=article), Twitter card meta, hreflang en-AU
- Google Fonts preconnect + link; also add <link rel="dns-prefetch" href="//fonts.googleapis.com"> and <link rel="dns-prefetch" href="//fonts.gstatic.com">
- JSON-LD: {schema_type} schema (author={site['author']}, publisher={site['brand']}, datePublished={TODAY}, dateModified={TODAY})
- JSON-LD: FAQPage (5 Q&As specific to this topic, phrased to match Google People Also Ask patterns)
- JSON-LD: BreadcrumbList — [{{"@type":"ListItem","position":1,"name":"Home","item":"{site['domain']}/"}},{{"@type":"ListItem","position":2,"name":"{slug.split('/')[0].title()}","item":"{site['domain']}/{slug.split('/')[0]}/"}},{{"@type":"ListItem","position":3,"name":"{h1}","item":"{site['domain']}/{slug}/"}}]
- Speakable JSON-LD: {{"@context":"https://schema.org","@type":"SpeakableSpecification","cssSelector":["h1",".hero-lead","#faq .faq-question"]}} (marks key content for voice search)
- All CSS in <style>; use font-display: swap on all font declarations for Core Web Vitals (LCP/CLS)""",
        "keywords": f"""Primary: {primary_kws}
Long-tail (weave naturally): {longtail_kws}
Informational FAQs: {info_kws}
Rules: {kw_rules}""",
        "nav_footer": f"""Sticky nav — brand "{site['brand']}" links to {site['domain']}/, nav links, 18+ badge.
Footer — brand, disclaimer, 1800 858 858, affiliate disclosure, © {site['year']} {site['brand']}. Footer nav must include links: Home | Reviews | Guides | About | Privacy Policy ({site['domain']}/privacy-policy/) | Terms & Conditions ({site['domain']}/terms-conditions/).
Responsible Gambling strip — red left-border box, 1800 858 858, gamblinghelponline.org.au.""",
        "h1": f'H1: "{h1}" ("{h1_highlight}" in gold {design["gold"]}). Author byline: <a href="{site["domain"]}/about/">{site["author"]}</a>. Updated {TODAY_PRETTY}.',
        "toc": f"""After the hero, add a compact .toc-box (card, gold left border) with jump links:
<nav class="toc-box" aria-label="Page contents">
  <p class="toc-title">In This Guide</p>
  <ol class="toc-list">
    <li>Top Casinos Ranked</li>
    <li>What Is [Topic]?</li>
    <li>How It Works Step by Step</li>
    <li>Comparison Table</li>
    <li>FAQ</li>
  </ol>
</nav>
(Adapt jump link labels to match the actual section headings on this page. Add matching id= attributes to each section.)""",
        "internal_links": f"""INTERNAL LINKING (required — weave into body copy naturally, do not list them separately):
- Link to at least 3 casino reviews: <a href="{site['domain']}/reviews/stake96/">Stake96 Casino review</a>, <a href="{site['domain']}/reviews/spin2u/">Spin2U Casino review</a>, <a href="{site['domain']}/reviews/spinza96/">Spinza96 review</a>
- Link to related guides: <a href="{site['domain']}/guides/best-payid-casinos/">best PayID casinos</a>, <a href="{site['domain']}/banking/payid-casino-deposits/">PayID casino deposits</a>
- Link back to homepage: <a href="{site['domain']}/">all 8 top AU casinos</a>""",
        "state_keywords": """STATE-LEVEL SEO: Naturally mention at least one Australian state (NSW, VIC, QLD, SA, WA) when describing where players are based or where the topic is popular — e.g. "popular among NSW and VIC punters" or "legal for players in Queensland". Do NOT create a separate section for this — weave it into existing body copy.""",
        "suffix": "Single self-contained HTML — ALL CSS in <style>. Mobile responsive. Google Fonts only. FAQ accordion vanilla JS. Budget CSS to avoid truncation — you MUST reach </body></html>.\nReturn ONLY raw HTML. No markdown. No explanation. Start with <!DOCTYPE html>. Do not truncate.",
    }


def build_banking_crypto_prompt(site: dict, casinos: list, design: dict, keywords: dict) -> str:
    sh = _guide_prompt_shell(site, design, keywords,
        slug="banking/crypto-casino-deposits",
        page_title=f"Crypto Casino Deposits Australia {site['year']} – Bitcoin, ETH & Solana Guide",
        meta_desc=f"How to deposit and withdraw with crypto at Australian online casinos {site['year']}. Bitcoin, Ethereum, Solana — instant, fee-free, no bank blocks.",
        h1=f"Crypto Casino Deposits Australia {site['year']}",
        h1_highlight="Crypto Casino",
        schema_type="Article",
    )
    all_summary = json.dumps(
        [{"rank": c["rank"], "name": c["name"], "score": c["score"], "bonus": c["bonus"],
          "tags": c["tags"], "min_deposit": c["min_deposit"],
          "review_url": c["review_url"], "affiliate_url": c["affiliate_url"]} for c in casinos], indent=2)
    crypto_picks = [c for c in casinos if any(t in " ".join(c["tags"]) for t in ["Crypto", "KYC", "Bitcoin"])]
    crypto_names = ", ".join(c["name"] for c in crypto_picks[:3])
    return f"""Generate a complete, production-ready HTML banking guide: "Crypto Casino Deposits Australia {site['year']}".

## SITE INFO
{sh['header']}

## SEO KEYWORDS
{sh['keywords']}

## CASINO DATA
{all_summary}

## HEAD
{sh['head']}
Additional JSON-LD: HowTo schema — "How to deposit Bitcoin at an online casino" (5 steps, datePublished={TODAY})

## PAGE SECTIONS (in order)

1. {sh['nav_footer'].split(chr(10))[0]}
2. **Hero** — {sh['h1']} Lead: crypto is the fastest AU withdrawal method — no bank blocks, near-zero fees, near-instant settlement. Trust bar: "Bitcoin · Ethereum · Solana · Litecoin · XRP · 20+ Coins". Add class="hero-lead" to lead paragraph.
3. {sh['toc']}
4. **Why Crypto for AU Casino Deposits? (H2)** — 3 reasons as cards: ① No bank rejections (IGA workaround), ② Fastest withdrawals (SOL under 1 min, BTC 5–10 min), ③ Enhanced privacy. 2 sentences each.
5. **Supported Cryptocurrencies at AU Casinos (H2)** — Grid of 6 crypto cards: Bitcoin (BTC) · Ethereum (ETH) · Solana (SOL) · Litecoin (LTC) · XRP · Tether (USDT). Each card: name, typical deposit speed, withdrawal speed, min deposit, which casinos accept it. Highlight SOL as fastest.
6. **Top Crypto Casinos Ranked (H2)** — ALL 8 casino cards (standard format: rank badge, name, bonus green, score, tags, "Play Now →" + "Read Review"). Highlight crypto-friendly ones ({crypto_names}). ALL affiliate links: target="_blank" rel="nofollow noopener sponsored".
7. **How to Deposit Bitcoin Step by Step (H2)** — 5 numbered visual steps: ① Choose casino → ② Register → ③ Go to Cashier, select BTC → ④ Copy wallet address → ⑤ Send from wallet. Include screenshot-style step cards.
8. **Crypto Withdrawals: How Fast? (H2)** — Table: Coin | Avg Withdrawal | Network Fees | Best For. SOL first (fastest). Tips: complete KYC before first withdrawal, withdraw to same wallet you deposited from.
9. **Crypto vs PayID: Which is Better? (H2)** — Comparison table: Feature | Crypto | PayID. Speed · Anonymity · Fees · AUD support · Bank required · Best for.
10. **FAQ Accordion** — 5 Q&As phrased as People Also Ask questions (same as FAQPage JSON-LD). Vanilla JS.
11. {sh['nav_footer'].split(chr(10))[2]}
12. Footer — {sh['nav_footer'].split(chr(10))[0].replace('Sticky nav — ', '')}

## INTERNAL LINKING
{sh['internal_links']}

## STATE-LEVEL KEYWORDS
{sh['state_keywords']}

## TECHNICAL
{sh['suffix']}"""


def build_banking_ewallet_prompt(site: dict, casinos: list, design: dict, keywords: dict) -> str:
    sh = _guide_prompt_shell(site, design, keywords,
        slug="banking/ewallet-casino-deposits",
        page_title=f"E-Wallet Casino Deposits Australia {site['year']} – PayID, POLi & More",
        meta_desc=f"Best e-wallet methods for Australian online casino deposits {site['year']}. PayID, POLi, Skrill, Neteller — instant deposits, fast pokies payouts.",
        h1=f"E-Wallet Casino Deposits Australia {site['year']}",
        h1_highlight="E-Wallet Casino",
        schema_type="Article",
    )
    all_summary = json.dumps(
        [{"rank": c["rank"], "name": c["name"], "score": c["score"], "bonus": c["bonus"],
          "tags": c["tags"], "min_deposit": c["min_deposit"],
          "review_url": c["review_url"], "affiliate_url": c["affiliate_url"]} for c in casinos], indent=2)
    return f"""Generate a complete, production-ready HTML banking guide: "E-Wallet Casino Deposits Australia {site['year']}".

## SITE INFO
{sh['header']}

## SEO KEYWORDS
{sh['keywords']}

## CASINO DATA
{all_summary}

## HEAD
{sh['head']}
Additional JSON-LD: HowTo schema — "How to deposit using an e-wallet at an Australian online casino" (5 steps)

## PAGE SECTIONS (in order)

1. {sh['nav_footer'].split(chr(10))[0]}
2. **Hero** — {sh['h1']} Lead (class="hero-lead"): e-wallets offer instant deposits, zero fees, and a layer of privacy between your bank and the casino. Payments bar: PayID · POLi · Skrill · Neteller · MuchBetter.
3. {sh['toc']}
4. **E-Wallet Options at AU Casinos (H2)** — Grid of 5 e-wallet cards:
   - **PayID** — Australia-only NPP bank transfer. Instant deposits, under 5 min withdrawals. Zero fees. Best overall.
   - **POLi** — Direct bank transfer, no account needed. Instant deposits. Widely accepted.
   - **Skrill** — International e-wallet, extra privacy layer. Instant deposits, 24–48hr withdrawals.
   - **Neteller** — Similar to Skrill. Good for high-volume players. Instant deposits.
   - **MuchBetter** — Mobile-first e-wallet. App-based. Instant deposits.
   Each card: name, speed badge, fees, min deposit, best for.
4. **Top E-Wallet Casino Sites Ranked (H2)** — ALL 8 casino cards (standard format). ALL affiliate links: target="_blank" rel="nofollow noopener sponsored".
5. **PayID: Australia's Best E-Wallet for Pokies (H2)** — Deep dive on PayID specifically. Why it's better than Skrill/Neteller for AU punters. Step-by-step: 5 steps to deposit via PayID. Internal link to /banking/payid-casino-deposits/.
6. **POLi Deposits Explained (H2)** — How POLi works, supported banks, pros/cons vs PayID. Step-by-step: 4 steps.
7. **E-Wallet Comparison Table (H2)** — Table: E-Wallet | Deposit Speed | Withdrawal | Fees | Account Required | Available in AU | Best For.
8. **E-Wallet Security at Online Casinos (H2)** — What casinos can/can't see, how e-wallets protect your bank details, what to look for in a secure e-wallet casino.
9. **FAQ Accordion** — 5 Q&As phrased as People Also Ask questions. Vanilla JS.
10. {sh['nav_footer'].split(chr(10))[2]}
11. Footer.

## INTERNAL LINKING
{sh['internal_links']}

## STATE-LEVEL KEYWORDS
{sh['state_keywords']}

## TECHNICAL
{sh['suffix']}"""


def build_guide_best_online_pokies_prompt(site: dict, casinos: list, design: dict, keywords: dict) -> str:
    sh = _guide_prompt_shell(site, design, keywords,
        slug="guides/best-online-pokies-australia",
        page_title=f"Best Online Pokies Australia {site['year']} – Top Real Money Pokies Sites",
        meta_desc=f"Best online pokies Australia {site['year']}. Expert-ranked real money pokies sites with PayID, 10,000+ titles, fast payouts and generous AUD bonuses.",
        h1=f"Best Online Pokies Australia {site['year']}",
        h1_highlight="Online Pokies",
    )
    all_summary = json.dumps(
        [{"rank": c["rank"], "name": c["name"], "score": c["score"], "bonus": c["bonus"],
          "wagering": c["wagering"], "tags": c["tags"],
          "review_url": c["review_url"], "affiliate_url": c["affiliate_url"]} for c in casinos], indent=2)
    return f"""Generate a complete, production-ready HTML guide: "Best Online Pokies Australia {site['year']}".

## SITE INFO
{sh['header']}

## SEO KEYWORDS
{sh['keywords']}

## CASINO DATA
{all_summary}

## HEAD
{sh['head']}
Additional JSON-LD: ItemList — top 5 pokies sites with affiliate_url

## PAGE SECTIONS (in order)

1. {sh['nav_footer'].split(chr(10))[0]}
2. **Hero** — {sh['h1']} Lead (class="hero-lead"): 2 sentences on what makes the best pokies site in Australia (library size, RTP, PayID speed, bonus value). Trust bar: "10,000+ Pokies · Expert Tested · PayID Verified".
3. {sh['toc']}
4. **Top Online Pokies Sites Ranked (H2)** — ALL 8 casino cards (standard format). ALL affiliate links: target="_blank" rel="nofollow noopener sponsored".
4. **What Are Online Pokies? (H2)** — Definition for AU audience. Pokies vs slots terminology. Why Aussies love them. Types: classic 3-reel, video pokies, Megaways, progressive jackpots.
5. **Best Online Pokies to Play Right Now (H2)** — Table of 12 top pokies: Title | Provider | RTP | Volatility | Max Win | Why Play It. Include: Gates of Olympus (96.5%, 5,000x), Sweet Bonanza (96.5%, 21,100x), Book of Dead (96.2%, 5,000x), Wanted Dead or a Wild (96.38%, 12,500x), Dog House Megaways (96.55%, 12,305x), Gonzo's Quest (96%, 2,500x), Reactoonz (96.3%, 4,570x), Razor Shark (96.7%, 50,000x), Fire Joker (96.15%, 800x), Big Bass Bonanza (96.71%, 2,100x), Jammin' Jars 2 (96.5%, 20,000x), Money Train 4 (96%, 100,000x).
6. **Best Pokies Providers at AU Casinos (H2)** — 3-column grid of 6 provider cards: Pragmatic Play · Hacksaw Gaming · Play'n GO · NetEnt · Push Gaming · Relax Gaming. Each: logo fallback text, top 2 titles, speciality (e.g. "Megaways experts").
7. **How to Choose the Best Online Pokies (H2)** — 4 criteria as numbered cards: ① RTP (aim for 96%+) ② Volatility match ③ Bonus features ④ Max win potential. Practical advice in each.
8. **PayID Pokies: Deposit & Play Instantly (H2)** — Why PayID is the #1 deposit method for online pokies Australia. 3-step deposit guide. Internal links to /banking/payid-casino-deposits/ and /guides/best-payid-casinos/.
9. **FAQ Accordion** — 5 Q&As phrased as People Also Ask questions (are online pokies rigged, best RTP pokie Australia, can I win real money at online pokies, which casino has the most pokies, do online pokies pay more at certain times). Vanilla JS.
10. {sh['nav_footer'].split(chr(10))[2]}
11. Footer.

## INTERNAL LINKING
{sh['internal_links']}

## STATE-LEVEL KEYWORDS
{sh['state_keywords']}

## TECHNICAL
{sh['suffix']}"""


def build_guide_aristocrat_prompt(site: dict, casinos: list, design: dict, keywords: dict) -> str:
    sh = _guide_prompt_shell(site, design, keywords,
        slug="guides/how-to-play-aristocrat-pokies",
        page_title=f"How to Play Aristocrat Pokies Online Australia {site['year']} – Best Sites & Tips",
        meta_desc=f"How to play Aristocrat pokies online in Australia {site['year']}. Top Aristocrat titles, best real money sites, PayID deposits and winning tips.",
        h1=f"How to Play Aristocrat Pokies Online Australia {site['year']}",
        h1_highlight="Aristocrat Pokies",
    )
    all_summary = json.dumps(
        [{"rank": c["rank"], "name": c["name"], "score": c["score"], "bonus": c["bonus"],
          "review_url": c["review_url"], "affiliate_url": c["affiliate_url"]} for c in casinos[:5]], indent=2)
    return f"""Generate a complete, production-ready HTML guide: "How to Play Aristocrat Pokies Online Australia {site['year']}".

## SITE INFO
{sh['header']}

## SEO KEYWORDS
{sh['keywords']}

## TOP 5 CASINOS (for CTA section)
{all_summary}

## HEAD
{sh['head']}

## PAGE SECTIONS (in order)

1. {sh['nav_footer'].split(chr(10))[0]}
2. **Hero** — {sh['h1']} Lead (class="hero-lead"): Aristocrat is the most iconic Australian pokies brand — now available at top offshore casinos online. Author + date.
3. {sh['toc']}
4. **What is Aristocrat? (H2)** — 2 paragraphs: history (Sydney-founded 1953, ASX-listed, now global), why Aussies love Aristocrat, transition from pub pokies to online. Key facts: 200+ countries, 100+ online titles.
4. **Best Aristocrat Pokies Online (H2)** — Table of 10 top Aristocrat titles: Title | RTP | Volatility | Max Win | Key Feature. Include: More Chilli (95.25%, free spins, stacked symbols), Where's the Gold (95.1%, high vol), Buffalo (95.95%, Xtra Reel Power), 50 Lions (94.74%, free spins), Queen of the Nile (95.1%, classic), Miss Kitty (95.06%, free spins), 5 Dragons (95.17%, ways to win), Pompeii (95.88%, Reel Power), Indian Dreaming (95.15%, iconic), Lightning Link (95.5%, feature buy). Note that RTP may vary by casino.
5. **How to Play Aristocrat Pokies: Step by Step (H2)** — 6 numbered visual steps: ① Choose a trusted AU casino → ② Register & claim bonus → ③ Deposit via PayID → ④ Search "Aristocrat" in pokies lobby → ⑤ Set bet size (recommend $0.01–$1.00 per line) → ⑥ Understand the paytable before spinning.
6. **Aristocrat Free Spins Features Explained (H2)** — How free spins are triggered (scatter symbols), retriggers, multipliers. Specific: More Chilli stacked symbols, Queen of the Nile retrigger. Practical tips.
7. **Reel Power vs Paylines (H2)** — Explain Aristocrat's unique Reel Power system (243, 1024, 3125 ways) vs traditional paylines. Which titles use it (Buffalo, 50 Dragons). Why it matters for bet sizing.
8. **Where to Play Aristocrat Pokies Online Australia (H2)** — Top 5 casino mini-cards from casino data above. Each: rank, name, score, bonus, "Play Now →" (affiliate_url, target="_blank" rel="nofollow noopener sponsored") + "Read Review" link.
9. **FAQ Accordion** — 5 Q&As phrased as People Also Ask questions (are Aristocrat online pokies the same as pub pokies, which Aristocrat pokie has the best RTP, can I play Aristocrat pokies for free online in Australia, what is Aristocrat Lightning Link, which Aristocrat pokie is best for free spins). Vanilla JS.
10. {sh['nav_footer'].split(chr(10))[2]}
11. Footer.

## INTERNAL LINKING
{sh['internal_links']}

## STATE-LEVEL KEYWORDS
{sh['state_keywords']}

## TECHNICAL
{sh['suffix']}"""


def build_guide_jili_prompt(site: dict, casinos: list, design: dict, keywords: dict) -> str:
    sh = _guide_prompt_shell(site, design, keywords,
        slug="guides/how-to-play-jili-pokies",
        page_title=f"How to Play JILI Pokies Online Australia {site['year']} – Best Sites & Top Games",
        meta_desc=f"How to play JILI pokies online in Australia {site['year']}. Top JILI slots, best AU casino sites, bonus tips and PayID deposits explained.",
        h1=f"How to Play JILI Pokies Online Australia {site['year']}",
        h1_highlight="JILI Pokies",
    )
    all_summary = json.dumps(
        [{"rank": c["rank"], "name": c["name"], "score": c["score"], "bonus": c["bonus"],
          "review_url": c["review_url"], "affiliate_url": c["affiliate_url"]} for c in casinos[:5]], indent=2)
    return f"""Generate a complete, production-ready HTML guide: "How to Play JILI Pokies Online Australia {site['year']}".

## SITE INFO
{sh['header']}

## SEO KEYWORDS
{sh['keywords']}

## TOP 5 CASINOS (for CTA section)
{all_summary}

## HEAD
{sh['head']}

## PAGE SECTIONS (in order)

1. {sh['nav_footer'].split(chr(10))[0]}
2. **Hero** — {sh['h1']} Lead (class="hero-lead"): JILI is one of Asia-Pacific's fastest-growing pokies providers — popular in Australia for high-volatility gameplay and frequent bonus triggers. Author + date.
3. {sh['toc']}
4. **What is JILI Gaming? (H2)** — 2 paragraphs: JILI founded 2018 in Manila (Philippines), rapid expansion across Asia-Pacific including AU market, known for: colourful themes, high volatility, fishing games (different from standard pokies but popular), slot machines. Distinguish: JILI makes both fishing arcade games AND slot machines — focus on slots here.
4. **Best JILI Pokies Online (H2)** — Table of 10 top JILI slot titles: Title | RTP | Volatility | Max Win | Key Feature. Include: Fortune Gems (96.8%, low-med vol, simple classic), Magic Lamp (96.7%, med, free games), Crazy 777 (96.5%, classic 3-reel), Golden Empire (97.09%, high, free spins cascade), Medusa (96.97%, high, expanding wilds), Boxing King (96.8%, high, KO free games), Super Ace (97.22%, high, top RTP), Charge Buffalo (97.06%, high, ways to win), Money Coming (96.8%, med, scatter pays), JILI Caishen (96.5%, med, classic Asian theme).
5. **How to Play JILI Pokies: Step by Step (H2)** — 6 numbered visual steps: ① Choose an AU casino with JILI → ② Register & deposit via PayID → ③ Search "JILI" in pokies lobby → ④ Try Super Ace or Golden Empire first (best RTP) → ⑤ Set bet within your bankroll (JILI high-vol needs bigger bankroll) → ⑥ Trigger free games features.
6. **JILI vs Other Providers (H2)** — Quick comparison table: Provider | Known For | Best RTP Title | Volatility Style | AU Availability. Rows: JILI vs Pragmatic Play vs Hacksaw vs Play'n GO.
7. **JILI Free Games Features (H2)** — How JILI free games are triggered, what makes them different (often lock-and-spin, hold-and-win mechanics), specific examples from Super Ace and Golden Empire.
8. **Where to Play JILI Pokies Online Australia (H2)** — Top 5 casino mini-cards. Each: rank, name, score, bonus, "Play Now →" (affiliate_url, target="_blank" rel="nofollow noopener sponsored") + "Read Review".
9. **FAQ Accordion** — 5 Q&As phrased as People Also Ask questions (what is JILI Gaming, is JILI legit and safe for Australian players, which JILI pokie has the best RTP, how do you trigger JILI free games, JILI vs Pragmatic Play — which is better). Vanilla JS.
10. {sh['nav_footer'].split(chr(10))[2]}
11. Footer.

## INTERNAL LINKING
{sh['internal_links']}

## STATE-LEVEL KEYWORDS
{sh['state_keywords']}

## TECHNICAL
{sh['suffix']}"""


def build_guide_booongo_prompt(site: dict, casinos: list, design: dict, keywords: dict) -> str:
    sh = _guide_prompt_shell(site, design, keywords,
        slug="guides/how-to-play-booongo-pokies",
        page_title=f"How to Play Booongo Pokies Online Australia {site['year']} – Top Games & Best Sites",
        meta_desc=f"How to play Booongo pokies online in Australia {site['year']}. Best Booongo slots, RTP guide, AU casino sites with PayID deposits and bonus tips.",
        h1=f"How to Play Booongo Pokies Online Australia {site['year']}",
        h1_highlight="Booongo Pokies",
    )
    all_summary = json.dumps(
        [{"rank": c["rank"], "name": c["name"], "score": c["score"], "bonus": c["bonus"],
          "review_url": c["review_url"], "affiliate_url": c["affiliate_url"]} for c in casinos[:5]], indent=2)
    return f"""Generate a complete, production-ready HTML guide: "How to Play Booongo Pokies Online Australia {site['year']}".

## SITE INFO
{sh['header']}

## SEO KEYWORDS
{sh['keywords']}

## TOP 5 CASINOS (for CTA section)
{all_summary}

## HEAD
{sh['head']}

## PAGE SECTIONS (in order)

1. {sh['nav_footer'].split(chr(10))[0]}
2. **Hero** — {sh['h1']} Lead (class="hero-lead"): Booongo is a Ukrainian-founded provider known for stunning visuals, high-RTP pokies and Hold & Win mechanics — increasingly popular at Australian online casinos. Author + date.
3. {sh['toc']}
4. **What is Booongo? (H2)** — 2 paragraphs: Booongo founded 2015 in Ukraine, licensed by Malta Gaming Authority (MGA) and Curaçao, 150+ titles, key strengths: beautiful graphics, innovative Hold & Win mechanics, high RTP averages (many 96–97%), strong AU casino distribution. Distinguished from bigger providers by boutique quality feel.
4. **Best Booongo Pokies Online (H2)** — Table of 10 top Booongo slot titles: Title | RTP | Volatility | Max Win | Key Feature. Include: 88 Dragon (97.1%, med, Hold & Win), Sun of Egypt 3 (96.98%, high, free spins), Caishen's Gold (97.0%, med, Hold & Win), Hot Volcano (96.96%, high, free games), Wild Cash (97.05%, med, Hold & Win), Panther Pays (96.8%, high, expanding wild), Dragon's Gold 100 (97.1%, med, Hold & Win), 5 Coins (96.97%, med-high, Hold & Win), Space XY (96.5%, crash-style game), Lucky Coins (96.98%, med, Hold & Win).
5. **How to Play Booongo Pokies: Step by Step (H2)** — 6 numbered visual steps: ① Find a casino with Booongo (use our list) → ② Register & deposit via PayID → ③ Search "Booongo" in pokies lobby → ④ Start with 88 Dragon or Wild Cash (best Hold & Win intro) → ⑤ Set bet conservatively — Booongo high-vol needs patience → ⑥ Target the Hold & Win feature trigger.
6. **Booongo Hold & Win Explained (H2)** — What Hold & Win mechanics are (collect coin symbols to fill grid, trigger jackpot prizes), how Booongo implements it vs other providers, which Booongo titles have the best Hold & Win (88 Dragon, Wild Cash, Dragon's Gold 100). Practical tips for maximising the feature.
7. **Booongo vs Other Providers (H2)** — Comparison table: Provider | Founded | Known For | Avg RTP | Best Title | Hold & Win?. Rows: Booongo vs Pragmatic Play vs BGaming vs Wazdan.
8. **Where to Play Booongo Pokies Online Australia (H2)** — Top 5 casino mini-cards. Each: rank, name, score, bonus, "Play Now →" (affiliate_url, target="_blank" rel="nofollow noopener sponsored") + "Read Review".
9. **FAQ Accordion** — 5 Q&As phrased as People Also Ask questions (what is Booongo Gaming, is Booongo safe and legit for Australian players, which Booongo pokie has the best RTP, how does Hold & Win work in Booongo pokies, Booongo vs Pragmatic Play — which is better). Vanilla JS.
10. {sh['nav_footer'].split(chr(10))[2]}
11. Footer.

## INTERNAL LINKING
{sh['internal_links']}

## STATE-LEVEL KEYWORDS
{sh['state_keywords']}

## TECHNICAL
{sh['suffix']}"""


# ─────────────────────────────────────────────
# STATIC FILE GENERATORS (no Claude needed)
# ─────────────────────────────────────────────

def generate_sitemap(site: dict, casinos: list) -> str:
    today = TODAY
    domain = site["domain"]

    # Build review URL entries
    review_entries = ""
    for c in casinos:
        priority = "0.9" if c["rank"] <= 3 else ("0.8" if c["rank"] <= 6 else "0.7")
        review_entries += f"""
  <url>
    <loc>{domain}/reviews/{c['slug']}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>{priority}</priority>
    <xhtml:link rel="alternate" hreflang="en-AU" href="{domain}/reviews/{c['slug']}/"/>
  </url>"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">

  <!-- HOMEPAGE -->
  <url>
    <loc>{domain}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
    <xhtml:link rel="alternate" hreflang="en-AU" href="{domain}/"/>
  </url>

  <!-- ABOUT -->
  <url>
    <loc>{domain}/about/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
    <xhtml:link rel="alternate" hreflang="en-AU" href="{domain}/about/"/>
  </url>

  <!-- LEGAL -->
  <url>
    <loc>{domain}/privacy-policy/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>yearly</changefreq>
    <priority>0.3</priority>
    <xhtml:link rel="alternate" hreflang="en-AU" href="{domain}/privacy-policy/"/>
  </url>
  <url>
    <loc>{domain}/terms-conditions/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>yearly</changefreq>
    <priority>0.3</priority>
    <xhtml:link rel="alternate" hreflang="en-AU" href="{domain}/terms-conditions/"/>
  </url>

  <!-- GUIDES -->
  <url>
    <loc>{domain}/guides/best-payid-casinos/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
    <xhtml:link rel="alternate" hreflang="en-AU" href="{domain}/guides/best-payid-casinos/"/>
  </url>
  <url>
    <loc>{domain}/guides/best-crypto-casinos/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
    <xhtml:link rel="alternate" hreflang="en-AU" href="{domain}/guides/best-crypto-casinos/"/>
  </url>
  <url>
    <loc>{domain}/guides/best-pokies-australia/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
    <xhtml:link rel="alternate" hreflang="en-AU" href="{domain}/guides/best-pokies-australia/"/>
  </url>
  <url>
    <loc>{domain}/guides/fast-payout-casinos/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
    <xhtml:link rel="alternate" hreflang="en-AU" href="{domain}/guides/fast-payout-casinos/"/>
  </url>
  <url>
    <loc>{domain}/guides/no-deposit-bonus/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
    <xhtml:link rel="alternate" hreflang="en-AU" href="{domain}/guides/no-deposit-bonus/"/>
  </url>
  <url>
    <loc>{domain}/guides/best-e-wallet-pokies-australia/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
    <xhtml:link rel="alternate" hreflang="en-AU" href="{domain}/guides/best-e-wallet-pokies-australia/"/>
  </url>
  <url>
    <loc>{domain}/guides/how-to-play-pokies/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
    <xhtml:link rel="alternate" hreflang="en-AU" href="{domain}/guides/how-to-play-pokies/"/>
  </url>

  <!-- BANKING -->
  <url>
    <loc>{domain}/banking/payid-casino-deposits/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
    <xhtml:link rel="alternate" hreflang="en-AU" href="{domain}/banking/payid-casino-deposits/"/>
  </url>
  <url>
    <loc>{domain}/banking/crypto-casino-deposits/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
    <xhtml:link rel="alternate" hreflang="en-AU" href="{domain}/banking/crypto-casino-deposits/"/>
  </url>
  <url>
    <loc>{domain}/banking/ewallet-casino-deposits/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
    <xhtml:link rel="alternate" hreflang="en-AU" href="{domain}/banking/ewallet-casino-deposits/"/>
  </url>

  <!-- PROVIDER GUIDES -->
  <url>
    <loc>{domain}/guides/best-online-pokies-australia/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
    <xhtml:link rel="alternate" hreflang="en-AU" href="{domain}/guides/best-online-pokies-australia/"/>
  </url>
  <url>
    <loc>{domain}/guides/how-to-play-aristocrat-pokies/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
    <xhtml:link rel="alternate" hreflang="en-AU" href="{domain}/guides/how-to-play-aristocrat-pokies/"/>
  </url>
  <url>
    <loc>{domain}/guides/how-to-play-jili-pokies/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
    <xhtml:link rel="alternate" hreflang="en-AU" href="{domain}/guides/how-to-play-jili-pokies/"/>
  </url>
  <url>
    <loc>{domain}/guides/how-to-play-booongo-pokies/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
    <xhtml:link rel="alternate" hreflang="en-AU" href="{domain}/guides/how-to-play-booongo-pokies/"/>
  </url>

  <!-- CASINO REVIEWS -->
{review_entries}

</urlset>"""


def generate_robots(site: dict) -> str:
    return f"""User-agent: *
Allow: /

# Block internal/utility paths
Disallow: /.tmp/
Disallow: /data/
Disallow: /generated/

# AI crawler rules — allow indexing for AI discovery
User-agent: GPTBot
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: anthropic-ai
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: Applebot-Extended
Allow: /

User-agent: CCBot
Allow: /

User-agent: cohere-ai
Allow: /

# LLM discovery file
# See: {site['domain']}/llms.txt

Sitemap: {site['domain']}/sitemap.xml
"""


def generate_llms_txt(site: dict, casinos: list) -> str:
    """Generate llms.txt — machine-readable site metadata for LLM crawlers.
    See: https://llmstxt.org/ for the emerging standard.
    """
    recommended = [c for c in casinos if c.get("recommended", True)]
    not_rec     = [c for c in casinos if not c.get("recommended", True)]

    casino_lines = "\n".join(
        f"- [{c['name']}]({site['domain']}/reviews/{c['slug']}/) — Score {c['score']}/10 — {c['best_for']}"
        for c in recommended
    )
    not_rec_lines = "\n".join(
        f"- [{c['name']}]({site['domain']}/reviews/{c['slug']}/) — Score {c['score']}/10 — Not recommended: {c.get('not_recommended_reason','')[:80]}"
        for c in not_rec
    )

    return f"""# {site['brand']} — LLM Discovery File
# Generated: {TODAY}
# Standard: https://llmstxt.org/

> {site['brand']} is an independent Australian online casino review site. We test and rate PayID casinos, pokies sites, and crypto gambling platforms for Australian players. No paid rankings — real accounts, real deposits.

## Site Identity

- **Name**: {site['brand']}
- **Domain**: {site['domain']}
- **Author**: {site['author']}
- **Geo**: Australia (en-AU)
- **Niche**: Online casino reviews — PayID casinos, pokies, bonuses, crypto gambling
- **Updated**: {TODAY}
- **Contact**: {site['email']}

## What This Site Covers

{site['brand']} provides:
1. Independent reviews of online casinos accepting Australian players
2. PayID casino guides — how to deposit and withdraw instantly via PayID
3. Pokies guides — Aristocrat, JILI, Booongo, Pragmatic Play
4. Banking guides — PayID, crypto (BTC/ETH/SOL), e-wallets
5. Bonus analysis — wagering requirements, max wins, T&C breakdown
6. Responsible gambling resources — 1800 858 858, gamblinghelponline.org.au

## Recommended Casinos (Ranked)

{casino_lines}

## Not Recommended (Listed for Transparency)

{not_rec_lines}

## Key Pages

- [Homepage]({site['domain']}/) — Best PayID casinos Australia {YEAR}
- [Best PayID Casinos]({site['domain']}/guides/best-payid-casinos/) — Full guide
- [Best Crypto Casinos]({site['domain']}/guides/best-crypto-casinos/) — BTC/ETH/SOL
- [How to Play Pokies]({site['domain']}/guides/how-to-play-pokies/) — Beginner guide
- [PayID Casino Deposits]({site['domain']}/banking/payid-casino-deposits/) — How it works
- [About]({site['domain']}/about/) — Author credentials
- [Sitemap]({site['domain']}/sitemap.xml)

## Content Policy

- All reviews are based on real player accounts and real deposits
- Scores are independent — no casino pays for placement
- We earn affiliate commission if players sign up via our links (disclosed on every page)
- We follow responsible gambling guidelines — all reviewed casinos offer deposit limits and self-exclusion
- Target audience: Australian adults 18+

## Schema Types Used

Review, FAQPage, BreadcrumbList, ItemList, Article, HowTo, WebSite, Organization

## Update Frequency

- Homepage: Daily (positions shuffle, dates update)
- Reviews: Updated when casino changes its offer or score changes
- Guides: Monthly review cycle
- Blog: {YEAR} publishing schedule via automated content queue
"""


# ─────────────────────────────────────────────
# HTML GENERATION
# ─────────────────────────────────────────────

def call_claude(prompt: str, label: str, max_tokens: int = 10000, model: str = None) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌  ANTHROPIC_API_KEY not set. Run: export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)

    _model = model or MODEL
    client = anthropic.Anthropic(api_key=api_key)
    max_retries = 10

    for attempt in range(1, max_retries + 1):
        try:
            print(f"🤖  Generating {label}..." + (f" (attempt {attempt})" if attempt > 1 else ""))

            with client.messages.stream(
                model=_model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                response = stream.get_final_message()

            html = response.content[0].text.strip()

            # ── Cost tracking ──
            usage = response.usage
            in_tok  = usage.input_tokens
            out_tok = usage.output_tokens
            pricing = _PRICING.get(_model, _PRICING[MODEL])
            cost = (in_tok * pricing["input"] + out_tok * pricing["output"]) / 1_000_000
            _token_usage["input"]    += in_tok
            _token_usage["output"]   += out_tok
            _token_usage["calls"]    += 1
            _token_usage["cost_usd"] += cost
            print(f"   📊  {in_tok:,} in + {out_tok:,} out = ${cost:.4f}")

            # ── Strip markdown fences ──
            if html.startswith("```"):
                html = html.split("\n", 1)[1]
            if html.endswith("```"):
                html = html.rsplit("```", 1)[0]
            html = html.strip()

            if not html.startswith("<!DOCTYPE") and not html.startswith("<html"):
                print(f"⚠️   Warning: {label} output may not be valid HTML.")

            return html

        except anthropic.RateLimitError:
            wait = 2 ** attempt * 5  # 10s, 20s, 40s
            print(f"⏳  Rate limited on {label}. Waiting {wait}s... ({attempt}/{max_retries})")
            time.sleep(wait)
            if attempt == max_retries:
                print(f"❌  Failed after {max_retries} retries: {label}")
                raise

        except anthropic.APIStatusError as e:
            if e.status_code >= 500 or "overloaded" in str(e).lower():
                wait = 2 ** attempt * 10  # 20s, 40s, 80s
                print(f"⏳  Overloaded/server error on {label}. Waiting {wait}s... ({attempt}/{max_retries})")
                time.sleep(wait)
                if attempt == max_retries:
                    raise
            else:
                print(f"❌  API error on {label}: {e}")
                raise

        except Exception as e:
            print(f"❌  Unexpected error on {label}: {e}")
            if attempt == max_retries:
                raise
            time.sleep(2 ** attempt * 2)


def save_local(html: str, rel_path: str) -> None:
    """Save HTML to a local generated/ directory for review."""
    out_path = Path("generated") / rel_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"   💾  Saved locally: generated/{rel_path} ({len(html):,} bytes)")


# ─────────────────────────────────────────────
# GITHUB PUSH
# ─────────────────────────────────────────────

def push_files_to_github(files: dict) -> None:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("❌  GITHUB_TOKEN not set. Run: export GITHUB_TOKEN='github_pat_...'")
        sys.exit(1)

    print(f"\n📤  Connecting to GitHub: {GITHUB_REPO}")
    g = Github(token)

    try:
        repo = g.get_repo(GITHUB_REPO)
    except GithubException as e:
        print(f"❌  Cannot access repo '{GITHUB_REPO}': {e}")
        sys.exit(1)

    pushed = 0
    for repo_path, content in files.items():
        try:
            existing = repo.get_contents(repo_path)
            repo.update_file(
                path=repo_path,
                message=f"Update {repo_path} — {TODAY}",
                content=content,
                sha=existing.sha
            )
            print(f"   ✅  Updated:  {repo_path}")
        except GithubException:
            repo.create_file(
                path=repo_path,
                message=f"Add {repo_path} — {TODAY}",
                content=content
            )
            print(f"   ✅  Created:  {repo_path}")
        pushed += 1
        if pushed < len(files):
            time.sleep(0.5)

    print(f"\n🚀  {pushed} file(s) pushed. Cloudflare deploys via GitHub Actions.")
    print(f"    Live at: {SITE['domain']}/")


def print_cost_summary():
    t = _token_usage
    print(f"\n{'='*60}")
    print(f"  💰  API COST SUMMARY")
    print(f"  Calls        : {t['calls']}")
    print(f"  Input tokens : {t['input']:,}")
    print(f"  Output tokens: {t['output']:,}")
    print(f"  Total cost   : ${t['cost_usd']:.4f}")
    print(f"{'='*60}")


def ping_indexnow(pushed_paths: list) -> None:
    """Ping IndexNow + Google sitemap after deploy."""
    indexnow_key = os.environ.get("INDEXNOW_KEY")
    if not indexnow_key:
        print("\n⚠️   INDEXNOW_KEY not set — skipping IndexNow ping.")
        print("    Get a key at bing.com/indexnow, then:")
        print('    export INDEXNOW_KEY="your-key"')
        return

    domain = SITE["domain"].rstrip("/")
    urls = []
    for path in pushed_paths:
        if path.endswith(".html"):
            url_path = path.replace(".html", "/") if path != "index.html" else ""
            urls.append(f"{domain}/{url_path}")
        elif path == "sitemap.xml":
            urls.append(f"{domain}/sitemap.xml")

    if not urls:
        return

    print(f"\n🔔  Pinging IndexNow with {len(urls)} URL(s)...")

    payload = json.dumps({
        "host": domain.replace("https://", "").replace("http://", ""),
        "key": indexnow_key,
        "keyLocation": f"{domain}/{indexnow_key}.txt",
        "urlList": urls
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.indexnow.org/IndexNow",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST"
    )

    try:
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"   ✅  IndexNow accepted {len(urls)} URLs (status {resp.getcode()})")
    except Exception as e:
        print(f"   ⚠️   IndexNow ping failed: {e} (non-critical)")

    # Google sitemap ping
    try:
        urllib.request.urlopen(f"https://www.google.com/ping?sitemap={domain}/sitemap.xml", timeout=10)
        print(f"   ✅  Google sitemap ping sent")
    except Exception:
        pass


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # ── CLI argument parsing ──
    parser = argparse.ArgumentParser(description=f"{SITE['brand']} — Multi-Page Generator")
    parser.add_argument("--only", type=str, default=None,
                        help="Comma-separated page paths to generate, e.g. --only=index.html,about.html")
    parser.add_argument("--list", action="store_true",
                        help="List all available page paths and exit")
    parser.add_argument("--no-push", action="store_true",
                        help="Skip the GitHub push prompt")
    parser.add_argument("--no-indexnow", action="store_true",
                        help="Skip the IndexNow ping after push")
    args = parser.parse_args()

    # ── Build master task list: (prompt, path, max_tokens, model) ──
    # Index uses MODEL (Sonnet). Reviews and guides also use MODEL.
    # Prompts use TODAY for both datePublished and dateModified by default.
    # _fix_prompt_dates() replaces datePublished with the stored original date.
    def _build_task(prompt: str, path: str, max_tok: int, mdl: str) -> tuple:
        pub, mod = _get_page_dates(path)
        # Replace the datePublished placeholder that was set to TODAY in the f-string
        # with the page's actual original publish date
        prompt = prompt.replace(f'"datePublished":"{TODAY}"', f'"datePublished":"{pub}"')
        prompt = prompt.replace(f'datePublished={TODAY}', f'datePublished={pub}')
        # Also fix the pretty-print version in hero byline for non-index pages
        if path != "index.html":
            pub_pretty = datetime.date.fromisoformat(pub).strftime("%-d %B %Y")
            # dateModified stays as TODAY_PRETTY (already in prompt)
            # We only need to ensure "Published X Month Y" shows original date
            # The hero byline already shows "Updated TODAY_PRETTY" which is correct for modified date
        return (prompt, path, max_tok, mdl)

    all_tasks = []
    all_tasks.append(_build_task(build_index_prompt(SITE, casinos, DESIGN, KEYWORDS), "index.html", 40000, MODEL))
    for casino in casinos:
        path = f"reviews/{casino['slug']}.html"
        all_tasks.append(_build_task(build_review_prompt(SITE, casino, DESIGN, KEYWORDS), path, 20000, MODEL))
    all_tasks.append(_build_task(build_about_prompt(SITE, casinos, DESIGN, KEYWORDS), "about.html", 12000, MODEL))
    all_tasks.append(_build_task(build_privacy_prompt(SITE, DESIGN), "privacy-policy.html", 10000, MODEL))
    all_tasks.append(_build_task(build_terms_prompt(SITE, DESIGN), "terms-conditions.html", 10000, MODEL))
    for build_fn, path in [
        (build_guide_payid_prompt,              "guides/best-payid-casinos.html"),
        (build_guide_crypto_prompt,             "guides/best-crypto-casinos.html"),
        (build_guide_best_pokies_prompt,        "guides/best-pokies-australia.html"),
        (build_guide_fast_payout_prompt,        "guides/fast-payout-casinos.html"),
        (build_guide_no_deposit_prompt,         "guides/no-deposit-bonus.html"),
        (build_guide_ewallet_prompt,            "guides/best-e-wallet-pokies-australia.html"),
        (build_guide_pokies_prompt,             "guides/how-to-play-pokies.html"),
        (build_banking_payid_prompt,            "banking/payid-casino-deposits.html"),
        (build_banking_crypto_prompt,           "banking/crypto-casino-deposits.html"),
        (build_banking_ewallet_prompt,          "banking/ewallet-casino-deposits.html"),
        (build_guide_best_online_pokies_prompt, "guides/best-online-pokies-australia.html"),
        (build_guide_aristocrat_prompt,         "guides/how-to-play-aristocrat-pokies.html"),
        (build_guide_jili_prompt,               "guides/how-to-play-jili-pokies.html"),
        (build_guide_booongo_prompt,            "guides/how-to-play-booongo-pokies.html"),
    ]:
        all_tasks.append(_build_task(build_fn(SITE, casinos, DESIGN, KEYWORDS), path, 14000, MODEL))

    all_paths = [t[1] for t in all_tasks] + ["sitemap.xml", "robots.txt", "llms.txt"]

    # ── --list flag ──
    if args.list:
        print(f"\n{SITE['brand']} — Available pages ({len(all_paths)} total):\n")
        for p in all_paths:
            print(f"  {p}")
        print(f"\nUsage: python3 generate_au.py --only=<path>[,<path>...]")
        sys.exit(0)

    # ── --only flag: filter tasks ──
    if args.only:
        only_set = {p.strip() for p in args.only.split(",")}
        unknown = only_set - set(all_paths)
        if unknown:
            print(f"❌  Unknown page(s): {', '.join(sorted(unknown))}")
            print(f"    Run --list to see all available pages.")
            sys.exit(1)
        tasks = [t for t in all_tasks if t[1] in only_set]
        do_sitemap = "sitemap.xml" in only_set
        do_robots  = "robots.txt" in only_set
        do_llms    = "llms.txt" in only_set
    else:
        tasks = all_tasks
        do_sitemap = True
        do_robots  = True
        do_llms    = True

    print("=" * 60)
    print(f"  {SITE['brand']} — Multi-Page Generator")
    print(f"  Date   : {TODAY}")
    print(f"  Domain : {SITE['domain']}")
    print(f"  Repo   : {GITHUB_REPO}")
    print(f"  Pages  : {len(tasks)} Claude pages" +
          (" + sitemap + robots" if do_sitemap or do_robots else ""))
    print("=" * 60)

    generated_files = {}

    def generate_one(task_args):
        prompt, path, max_tok, mdl = task_args
        html = call_claude(prompt, path, max_tokens=max_tok, model=mdl)
        save_local(html, path)
        _register_page_date(path)  # records publish date for new pages
        return path, html

    if tasks:
        print(f"\n⚡  Generating {len(tasks)} page(s) in parallel (10 workers)...\n")
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {}
            for t in tasks:
                futures[executor.submit(generate_one, t)] = t[1]
                time.sleep(0.5)  # minimal stagger to avoid rate-limit burst
            for future in as_completed(futures):
                path, html = future.result()
                generated_files[path] = html
                print(f"   ✓  {path}")

    if do_sitemap:
        print("\n🗺️   Generating sitemap.xml...")
        sitemap = generate_sitemap(SITE, casinos)
        save_local(sitemap, "sitemap.xml")
        generated_files["sitemap.xml"] = sitemap

    if do_robots:
        print("🤖  Generating robots.txt...")
        robots = generate_robots(SITE)
        save_local(robots, "robots.txt")
        generated_files["robots.txt"] = robots

    if do_llms:
        print("🧠  Generating llms.txt...")
        llms = generate_llms_txt(SITE, casinos)
        save_local(llms, "llms.txt")
        generated_files["llms.txt"] = llms

    print(f"\n✅  {len(generated_files)} file(s) generated.")
    print(f"    Local preview: open generated/index.html in your browser.")

    print_cost_summary()

    if args.no_push:
        print("\n⏸️   Skipped push (--no-push). Review generated/ then push manually.")
        sys.exit(0)

    push = input("\nPush all files to GitHub now? (y/n): ").strip().lower()
    if push == "y":
        push_files_to_github(generated_files)
        if not args.no_indexnow:
            ping_indexnow(list(generated_files.keys()))
    else:
        print("⏸️   Skipped. Review generated/ then re-run to push.")
