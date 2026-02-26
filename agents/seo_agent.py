#!/usr/bin/env python3
"""
seo_agent.py — Africa Gold Intelligence — Tier 2: SEO & Discoverability Agent
==============================================================================
Generates dynamic SEO metadata for each daily briefing post:
  - Optimised URL slug
  - Data-driven content tags (post type + live market conditions)
  - Meta description (<160 chars, keyword-rich)
  - JSON-LD structured data (Article + gold price BroadcastEvent)
  - Internal linking suggestions based on recent run history
  - Appends to seo_log.jsonl for keyword tracking over time

Usage (standalone test):
    python3 seo_agent.py

Called by orchestrator.py between Content Synthesis and Distribution.
Input:  post_type (str), data (dict from Market Intelligence), today (datetime), title (str)
Output: seo_data dict with keys: slug, tags, meta_description, json_ld_html, suggestions
"""

import json
import datetime
import re
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent
SEO_LOG      = SCRIPT_DIR.parent / "logs" / "seo_log.jsonl"
SITE_URL     = "https://www.africagoldintelligence.com"
PUBLISHER    = "Africa Gold Intelligence"

# ── Keyword banks by post type ──────────────────────────────────────────────────
BASE_TAGS = {
    "trader_intelligence": [
        "gold trading", "XAU/USD", "gold futures", "gold technical analysis",
        "gold price today", "precious metals trading", "gold RSI",
    ],
    "africa_regional": [
        "gold price Africa", "African gold market", "gold mining Africa",
        "Africa precious metals", "gold investment Africa",
    ],
    "aggregator": [
        "gold news today", "gold market update", "precious metals news",
        "gold price news", "gold market briefing",
    ],
    "karat_pricing": [
        "gold price per gram", "24k gold price", "22k gold price",
        "gold karat prices Africa", "gold gram price today",
        "gold jewellery price", "gold karat calculator",
    ],
    "macro_outlook": [
        "gold inflation hedge", "DXY gold", "gold Federal Reserve",
        "gold macro outlook", "gold dollar correlation",
        "gold interest rates", "gold safe haven",
    ],
    "educational": [
        "how to invest in gold Africa", "gold investing beginner",
        "gold bullion Africa", "gold ETF Africa", "buy gold Africa",
        "gold investment guide", "gold savings Africa",
    ],
    "week_review": [
        "gold weekly review", "gold price this week", "gold market summary",
        "weekly gold report", "gold price week recap",
    ],
}

# Country-specific tags mapped to FX currency codes
COUNTRY_TAGS = {
    "ZAR": ["gold price South Africa", "gold rand", "South Africa gold"],
    "GHS": ["gold price Ghana", "gold cedi", "Ghana gold"],
    "NGN": ["gold price Nigeria", "gold naira", "Nigeria gold"],
    "KES": ["gold price Kenya", "gold shilling", "Kenya gold"],
    "EGP": ["gold price Egypt", "gold pound Egypt", "Egypt gold"],
    "MAD": ["gold price Morocco", "gold dirham", "Morocco gold"],
}

# Post type to human-readable slug segment
SLUG_SEGMENTS = {
    "trader_intelligence": "trader-intelligence",
    "africa_regional":     "africa-regional-report",
    "aggregator":          "market-aggregator",
    "karat_pricing":       "karat-pricing",
    "macro_outlook":       "macro-outlook",
    "educational":         "gold-education",
    "week_review":         "weekly-review",
}

META_TEMPLATES = {
    "trader_intelligence": (
        "Gold at ${price} ({sign}{pct}%) today. RSI-{rsi} signals for XAU/USD traders in Africa. "
        "Full technical briefing inside."
    ),
    "africa_regional": (
        "Gold trading at ${price} across Africa. Local prices in ZAR, GHS, NGN, KES, EGP and MAD. "
        "Africa Gold Intelligence daily report."
    ),
    "aggregator": (
        "Today's top gold market news and analysis. XAU/USD at ${price} ({sign}{pct}%). "
        "Curated for African investors and traders."
    ),
    "karat_pricing": (
        "Live gold prices per gram in 24K, 22K, 18K, 14K and 9K across 6 African currencies. "
        "XAU/USD at ${price} — updated daily."
    ),
    "macro_outlook": (
        "Gold at ${price} as macro forces shape precious metals. DXY, rates, and global drivers "
        "for African gold investors."
    ),
    "educational": (
        "How to invest in gold in Africa — practical guide for beginners. "
        "Gold at ${price} today. Africa Gold Intelligence."
    ),
    "week_review": (
        "Weekly gold market review: XAU/USD closed at ${price} ({sign}{pct}% on the week). "
        "Africa Gold Intelligence round-up."
    ),
}


# ── Core functions ─────────────────────────────────────────────────────────────

def build_slug(post_type: str, today: datetime.datetime) -> str:
    """Generate an SEO-friendly URL slug."""
    segment = SLUG_SEGMENTS.get(post_type, "briefing")
    date_str = today.strftime("%Y-%m-%d")
    return f"gold-briefing-{segment}-{date_str}"


def build_tags(post_type: str, data: dict) -> list:
    """Build a dynamic tag list from post type + live market conditions."""
    tags = list(BASE_TAGS.get(post_type, []))

    gold    = data.get("gold", {})
    price   = gold.get("price", 0)
    pct     = gold.get("day_chg_pct", 0) or 0
    rsi     = gold.get("rsi")
    fx      = data.get("fx_rates", {})

    # Always include core brand tags
    tags += ["Africa Gold Intelligence", "gold", "XAU/USD", "Africa"]

    # Market-condition tags
    if pct >= 2:
        tags.append("gold rally")
    elif pct <= -2:
        tags.append("gold dip")

    if rsi is not None:
        if rsi >= 70:
            tags.append("gold overbought")
        elif rsi <= 30:
            tags.append("gold oversold")

    if price >= 3000:
        tags.append("gold all-time high")

    # Country tags: include any currency we have FX data for
    for currency, rate in fx.items():
        if rate and currency in COUNTRY_TAGS:
            # Add one country tag to avoid over-stuffing
            tags.append(COUNTRY_TAGS[currency][0])

    # Deduplicate and cap at 15 tags (Beehiiv best practice)
    seen = set()
    unique = []
    for t in tags:
        if t.lower() not in seen:
            seen.add(t.lower())
            unique.append(t)
        if len(unique) >= 15:
            break

    return unique


def build_meta_description(post_type: str, data: dict) -> str:
    """Build a meta description under 160 characters."""
    gold  = data.get("gold", {})
    price = gold.get("price", 0)
    pct   = gold.get("day_chg_pct", 0) or 0
    rsi   = gold.get("rsi", "N/A")
    sign  = "+" if pct >= 0 else ""

    template = META_TEMPLATES.get(post_type, META_TEMPLATES["aggregator"])
    desc = template.format(
        price=f"{price:,.0f}",
        pct=f"{abs(pct):.1f}",
        sign=sign,
        rsi=rsi if rsi else "N/A",
    )

    # Hard truncate to 160 chars at a word boundary
    if len(desc) > 160:
        desc = desc[:157].rsplit(" ", 1)[0] + "..."

    return desc


def build_json_ld(title: str, meta_description: str, slug: str,
                  today: datetime.datetime, data: dict) -> str:
    """Build JSON-LD structured data as an HTML script tag."""
    gold  = data.get("gold", {})
    price = gold.get("price", 0)
    pct   = gold.get("day_chg_pct", 0) or 0

    url = f"{SITE_URL}/p/{slug}"
    date_str = today.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    article_ld = {
        "@context":        "https://schema.org",
        "@type":           "Article",
        "headline":        title,
        "description":     meta_description,
        "datePublished":   date_str,
        "dateModified":    date_str,
        "url":             url,
        "publisher": {
            "@type": "Organization",
            "name":  PUBLISHER,
            "url":   SITE_URL,
        },
        "author": {
            "@type": "Organization",
            "name":  PUBLISHER,
        },
        "about": {
            "@type":      "Thing",
            "name":       "Gold (XAU/USD)",
            "identifier": "XAU",
        },
        "keywords": "gold price Africa, XAU/USD, African gold market, gold investing",
    }

    # Add gold price event structured data
    price_ld = {
        "@context":    "https://schema.org",
        "@type":       "Dataset",
        "name":        f"Gold Price Update — {today.strftime('%B %d, %Y')}",
        "description": f"XAU/USD spot price: ${price:,.2f} ({'+' if pct >= 0 else ''}{pct:.2f}% today)",
        "publisher": {
            "@type": "Organization",
            "name":  PUBLISHER,
            "url":   SITE_URL,
        },
        "temporalCoverage": today.strftime("%Y-%m-%d"),
        "variableMeasured": {
            "@type":       "PropertyValue",
            "name":        "Gold Spot Price",
            "unitCode":    "USD",
            "value":       round(price, 2),
        },
    }

    combined = [article_ld, price_ld]
    json_str = json.dumps(combined, indent=None, separators=(",", ":"))

    return f'<script type="application/ld+json">{json_str}</script>'


def build_internal_link_suggestions(post_type: str) -> list:
    """
    Read recent seo_log entries and suggest relevant internal links
    from the last 30 days of posts (different post types for diversity).
    """
    suggestions = []
    if not SEO_LOG.exists():
        return suggestions

    try:
        lines = SEO_LOG.read_text().strip().splitlines()
        cutoff = datetime.datetime.now() - datetime.timedelta(days=30)
        seen_types = set()

        for line in reversed(lines):
            if len(suggestions) >= 3:
                break
            try:
                rec = json.loads(line)
                ts = datetime.datetime.fromisoformat(rec.get("ts", ""))
                rec_type = rec.get("post_type", "")
                if ts < cutoff:
                    break
                # Suggest posts of different types for diversity
                if rec_type != post_type and rec_type not in seen_types:
                    suggestions.append({
                        "title": rec.get("title", ""),
                        "slug":  rec.get("slug", ""),
                        "url":   f"{SITE_URL}/p/{rec.get('slug', '')}",
                        "type":  rec_type,
                    })
                    seen_types.add(rec_type)
            except Exception:
                continue
    except Exception:
        pass

    return suggestions


def log_seo_run(post_type: str, slug: str, title: str, tags: list,
                meta_description: str, today: datetime.datetime):
    """Append SEO run record to seo_log.jsonl."""
    record = {
        "ts":               today.isoformat(),
        "post_type":        post_type,
        "slug":             slug,
        "title":            title,
        "tags":             tags,
        "meta_description": meta_description,
        "tag_count":        len(tags),
    }
    try:
        with open(SEO_LOG, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        print(f"  ⚠️  SEO log write failed: {e}")


def run(post_type: str, data: dict, today: datetime.datetime, title: str) -> dict:
    """
    Main entry point — called by orchestrator.py.

    Returns seo_data dict:
        slug             — URL slug for Beehiiv post
        tags             — list of content tags
        meta_description — <160 char meta description
        json_ld_html     — <script type="application/ld+json"> block
        internal_links   — list of {title, url, type} dicts
    """
    slug             = build_slug(post_type, today)
    tags             = build_tags(post_type, data)
    meta_description = build_meta_description(post_type, data)
    json_ld_html     = build_json_ld(title, meta_description, slug, today, data)
    internal_links   = build_internal_link_suggestions(post_type)

    log_seo_run(post_type, slug, title, tags, meta_description, today)

    return {
        "slug":             slug,
        "tags":             tags,
        "meta_description": meta_description,
        "json_ld_html":     json_ld_html,
        "internal_links":   internal_links,
    }


# ── Standalone test ────────────────────────────────────────────────────────────

def _test():
    today = datetime.datetime.now()

    # Simulate market data
    mock_data = {
        "gold":   {"price": 5205.60, "day_chg_pct": 2.89, "rsi": 68.4},
        "silver": {"price": 87.26},
        "dxy":    {"price": 97.81},
        "sp500":  {"price": 6838},
        "fx_rates": {
            "ZAR": 16.01, "GHS": 10.84, "NGN": 1344.40,
            "KES": 129.03, "EGP": 47.71, "MAD": 9.16,
        },
        "karat_prices": {},
        "news": [{"title": "Gold hits record high", "source": "Reuters"}],
    }

    for pt in ["trader_intelligence", "africa_regional", "karat_pricing",
               "macro_outlook", "educational", "week_review"]:
        title = f"Gold Market Briefing | {today.strftime('%a %b %d, %Y')}"
        result = run(pt, mock_data, today, title)

        print(f"\n{'─'*60}")
        print(f"  Post type:   {pt}")
        print(f"  Slug:        {result['slug']}")
        print(f"  Tags ({len(result['tags'])}):   {', '.join(result['tags'][:5])}...")
        print(f"  Meta ({len(result['meta_description'])} chars): {result['meta_description'][:80]}...")
        if result["internal_links"]:
            print(f"  Links:       {len(result['internal_links'])} suggestions")

    print(f"\n✅ SEO Agent test complete. Log: {SEO_LOG}\n")


if __name__ == "__main__":
    _test()
