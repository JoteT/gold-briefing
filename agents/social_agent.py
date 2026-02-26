#!/usr/bin/env python3
"""
social_agent.py — Africa Gold Intelligence — Tier 2: Social Amplification Agent
================================================================================
Generates platform-tailored social posts from each daily briefing:
  - Twitter/X  (280 chars, price hook + hashtags + CTA)
  - LinkedIn   (professional long-form, with market narrative)
  - WhatsApp   (plain-text broadcast for African markets)

Auto-posting (optional, zero-cost fallback):
  - If TWITTER_API_KEY etc. are set → posts to Twitter/X automatically
  - Otherwise → posts are included in the daily briefing email for manual copying

Log: social_log.jsonl

Usage (standalone test):
    python3 social_agent.py

Called by orchestrator.py after Distribution, before Human Oversight Gate.
Input:  post_type, data (market data dict), today (datetime), seo_data (from seo_agent)
Output: social_data dict with keys: twitter, linkedin, whatsapp, posted_platforms
"""

import os
import json
import datetime
import textwrap
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR    = Path(__file__).parent
SOCIAL_LOG    = SCRIPT_DIR.parent / "logs" / "social_log.jsonl"
SITE_URL      = "https://www.africagoldintelligence.com"
NEWSLETTER_URL = "https://www.africagoldintelligence.com"

# Twitter/X API credentials (optional — set for auto-posting)
TWITTER_API_KEY        = os.environ.get("TWITTER_API_KEY", "")
TWITTER_API_SECRET     = os.environ.get("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN   = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET  = os.environ.get("TWITTER_ACCESS_SECRET", "")

# LinkedIn API credentials (optional — set for auto-posting)
LINKEDIN_ACCESS_TOKEN  = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_PERSON_URN    = os.environ.get("LINKEDIN_PERSON_URN", "")  # urn:li:person:XXXXX

# ── Hashtag banks ───────────────────────────────────────────────────────────────
BASE_HASHTAGS = ["#Gold", "#XAU", "#Africa", "#GoldPrice", "#PreciousMetals"]

POST_TYPE_HASHTAGS = {
    "trader_intelligence": ["#Trading", "#GoldTrading", "#XAUUSD", "#TechnicalAnalysis"],
    "africa_regional":     ["#AfricaGold", "#AfricanMarkets", "#GoldInvesting"],
    "aggregator":          ["#GoldNews", "#MarketUpdate", "#Investing"],
    "karat_pricing":       ["#GoldPrice", "#GoldJewellery", "#KaratGold", "#GoldPerGram"],
    "macro_outlook":       ["#Macro", "#GoldOutlook", "#Inflation", "#DXY"],
    "educational":         ["#InvestingAfrica", "#GoldInvesting", "#PersonalFinance"],
    "week_review":         ["#WeeklyReview", "#GoldMarket", "#MarketSummary"],
}

COUNTRY_HASHTAGS = {
    "ZAR": "#SouthAfrica",
    "GHS": "#Ghana",
    "NGN": "#Nigeria",
    "KES": "#Kenya",
    "EGP": "#Egypt",
    "MAD": "#Morocco",
}

# ── Twitter/X post builders ─────────────────────────────────────────────────────

TWITTER_HOOKS = {
    "trader_intelligence": [
        "🟡 Gold ${price} ({sign}{pct}%) — RSI at {rsi}. Here's what traders in Africa need to know today:",
        "⚡ XAU/USD: ${price} ({sign}{pct}%). African gold market briefing 👇",
        "📊 Gold opens at ${price} ({sign}{pct}%). RSI-14: {rsi}. Full trader briefing inside:",
    ],
    "africa_regional": [
        "🌍 Gold at ${price} across Africa today. Local karat prices from Lagos to Johannesburg:",
        "📍 XAU/USD ${price} ({sign}{pct}%). What that means for gold buyers in Africa 👇",
        "🟡 Gold ${price} — priced in ZAR, GHS, NGN, KES, EGP & MAD. Daily Africa briefing:",
    ],
    "aggregator": [
        "📰 Top gold market stories today — XAU/USD at ${price} ({sign}{pct}%):",
        "🗞️ Gold market digest: ${price} | {sign}{pct}% | Africa focus. Read now:",
        "⚡ Gold news roundup — ${price} ({sign}{pct}%). What moved markets today:",
    ],
    "karat_pricing": [
        "💛 Gold per gram today across Africa — 24K, 22K, 18K, 14K & 9K prices:",
        "🔑 Karat gold prices: 24K=${k24_zar}/g (ZAR) | ${price} USD/oz. Full breakdown:",
        "📐 Daily karat pricing — gold at ${price}/oz. Gram prices in 6 African currencies:",
    ],
    "macro_outlook": [
        "🌐 Gold ${price} as {macro_driver}. What it means for African investors:",
        "📈 XAU/USD ${price} ({sign}{pct}%). Macro forces shaping gold this week:",
        "🔭 Gold macro outlook — ${price} | DXY {dxy}. Africa Gold Intelligence analysis:",
    ],
    "educational": [
        "💡 How to buy gold in Africa — a practical guide for 2026:",
        "📚 Gold investing 101 for African markets. Gold at ${price} today.",
        "🟡 Want to invest in gold from Africa? Here's everything you need to know:",
    ],
    "week_review": [
        "📊 Gold weekly wrap: XAU/USD {sign}{pct}% this week. Closed at ${price}. Full review:",
        "🗓️ Week in gold — ${price} close | {sign}{pct}%. Africa Gold Intelligence recap:",
        "⚡ Weekly gold review: from ${open_price} to ${price}. What drove the move:",
    ],
}


def _pick_hook(post_type: str, data: dict, today: datetime.datetime) -> str:
    """Select and format a Twitter hook based on market conditions."""
    import hashlib
    gold    = data.get("gold", {})
    price   = gold.get("price", 0)
    pct     = gold.get("day_chg_pct", 0) or 0
    rsi     = gold.get("rsi")
    dxy     = data.get("dxy", {}).get("price", 0) if data.get("dxy") else 0
    fx      = data.get("fx_rates", {})
    kp      = data.get("karat_prices", {})

    sign    = "+" if pct >= 0 else ""
    k24_zar = f"R{kp.get('ZAR', {}).get('24K', 0):,.0f}" if "ZAR" in kp else "—"

    # Pick hook deterministically based on date (rotates each day)
    hooks    = TWITTER_HOOKS.get(post_type, TWITTER_HOOKS["aggregator"])
    day_seed = int(today.strftime("%j"))  # day of year
    hook_tmpl = hooks[day_seed % len(hooks)]

    # Macro driver based on market conditions
    if abs(pct) >= 1.5:
        macro_driver = f"prices {'surge' if pct > 0 else 'slide'} {abs(pct):.1f}%"
    elif dxy and dxy < 98:
        macro_driver = "a weakening dollar"
    else:
        macro_driver = "global uncertainty"

    return hook_tmpl.format(
        price=f"{price:,.0f}",
        pct=f"{abs(pct):.1f}",
        sign=sign,
        rsi=f"{rsi:.0f}" if rsi else "N/A",
        dxy=f"{dxy:.1f}" if dxy else "—",
        k24_zar=k24_zar,
        open_price=f"{price / (1 + pct/100):,.0f}" if pct else f"{price:,.0f}",
        macro_driver=macro_driver,
    )


def build_twitter_post(post_type: str, data: dict, today: datetime.datetime,
                        slug: str = None, resolved_url: str = None) -> str:
    """Build a tweet ≤280 characters."""
    hook = _pick_hook(post_type, data, today)

    # Pick hashtags: base + post-type-specific (max 4 total to avoid spam)
    type_tags = POST_TYPE_HASHTAGS.get(post_type, [])[:2]
    fx = data.get("fx_rates", {})
    country_tags = [COUNTRY_HASHTAGS[c] for c in list(fx.keys())[:2] if c in COUNTRY_HASHTAGS]
    hashtags = " ".join(type_tags + country_tags[:1] + ["#AfricaGoldIntelligence"])

    # Prefer real post URL > slug-based URL > homepage (never 404)
    if resolved_url:
        link = resolved_url
    elif slug:
        link = f"{SITE_URL}/p/{slug}"
    else:
        link = NEWSLETTER_URL

    # Assemble: hook + link + hashtags, trim to 280
    post = f"{hook}\n\n{link}\n\n{hashtags}"

    if len(post) > 280:
        # Shorten hook to fit
        available = 280 - len(f"\n\n{link}\n\n{hashtags}")
        hook = hook[:available - 3].rsplit(" ", 1)[0] + "..."
        post = f"{hook}\n\n{link}\n\n{hashtags}"

    return post


def build_linkedin_post(post_type: str, data: dict, today: datetime.datetime,
                         slug: str = None, resolved_url: str = None) -> str:
    """Build a LinkedIn post (~600-900 chars, professional tone)."""
    gold  = data.get("gold", {})
    price = gold.get("price", 0)
    pct   = gold.get("day_chg_pct", 0) or 0
    rsi   = gold.get("rsi")
    fx    = data.get("fx_rates", {})
    kp    = data.get("karat_prices", {})
    news  = data.get("news", [])
    sign  = "+" if pct >= 0 else ""
    date_str = today.strftime("%B %d, %Y")
    if resolved_url:
        link = resolved_url
    elif slug:
        link = f"{SITE_URL}/p/{slug}"
    else:
        link = NEWSLETTER_URL

    # Price line
    price_line = f"Gold (XAU/USD): ${price:,.2f} ({sign}{pct:.2f}%)"
    if rsi:
        price_line += f" | RSI-14: {rsi:.0f}"

    # FX snapshot (top 3 currencies)
    fx_lines = []
    for cur, rate in list(fx.items())[:3]:
        k24 = kp.get(cur, {}).get("24K")
        sym = {"ZAR": "R", "GHS": "GH₵", "NGN": "₦", "KES": "KSh", "EGP": "E£", "MAD": "DH"}.get(cur, "")
        if rate and k24:
            fx_lines.append(f"  • {cur}: {sym}{k24:,.0f}/g (24K)")

    # News hook
    news_hook = f'"{news[0]["title"][:80]}..."' if news else "Markets are moving."

    # Post body by type
    if post_type in ("trader_intelligence", "macro_outlook"):
        body = (
            f"🟡 Gold Market Update — {date_str}\n\n"
            f"{price_line}\n\n"
            f"{news_hook}\n\n"
            f"Today's briefing covers:\n"
            f"  • Technical analysis & RSI signals\n"
            f"  • DXY correlation & macro drivers\n"
            f"  • Actionable insights for African traders\n\n"
        )
    elif post_type == "africa_regional":
        fx_block = "\n".join(fx_lines) if fx_lines else ""
        body = (
            f"🌍 Africa Gold Prices — {date_str}\n\n"
            f"{price_line}\n\n"
            f"Local gold prices right now:\n"
            f"{fx_block}\n\n"
            f"What's driving African gold markets today — and what to watch next week.\n\n"
        )
    elif post_type == "karat_pricing":
        fx_block = "\n".join(fx_lines) if fx_lines else ""
        body = (
            f"💛 Karat Gold Prices Across Africa — {date_str}\n\n"
            f"XAU/USD spot: ${price:,.2f} ({sign}{pct:.2f}%)\n\n"
            f"24K gold per gram:\n"
            f"{fx_block}\n\n"
            f"Full 9K–24K breakdown across 6 African currencies in today's briefing.\n\n"
        )
    elif post_type == "educational":
        body = (
            f"📚 Gold Investing in Africa — {date_str}\n\n"
            f"Gold is at ${price:,.2f} today. For many African investors, this raises a "
            f"simple question: how do I actually buy gold?\n\n"
            f"Today's briefing covers the practical options — from bullion and ETFs to "
            f"digital gold platforms available across the continent.\n\n"
        )
    elif post_type == "week_review":
        body = (
            f"📊 Gold Weekly Review — week ending {date_str}\n\n"
            f"Gold closed the week at ${price:,.2f} ({sign}{pct:.2f}%).\n\n"
            f"This week's briefing covers:\n"
            f"  • Key price drivers and catalysts\n"
            f"  • African currency performance vs gold\n"
            f"  • What to watch in the week ahead\n\n"
        )
    else:  # aggregator
        body = (
            f"📰 Gold Market Digest — {date_str}\n\n"
            f"{price_line}\n\n"
            f"Top story: {news_hook}\n\n"
            f"Full curated gold market briefing for African investors — "
            f"prices, news, and analysis in one place.\n\n"
        )

    hashtags = " ".join(
        ["#Gold", "#XAU", "#AfricaGoldIntelligence", "#GoldInvesting", "#AfricanMarkets"]
    )

    return f"{body}Read the full briefing → {link}\n\n{hashtags}"


def build_whatsapp_message(post_type: str, data: dict, today: datetime.datetime,
                            slug: str = None, resolved_url: str = None) -> str:
    """Build a WhatsApp broadcast message — plain text, emoji-friendly."""
    gold  = data.get("gold", {})
    price = gold.get("price", 0)
    pct   = gold.get("day_chg_pct", 0) or 0
    fx    = data.get("fx_rates", {})
    kp    = data.get("karat_prices", {})
    sign  = "+" if pct >= 0 else ""
    arrow = "📈" if pct >= 0 else "📉"
    date_str = today.strftime("%a %d %b %Y")
    if resolved_url:
        link = resolved_url
    elif slug:
        link = f"{SITE_URL}/p/{slug}"
    else:
        link = NEWSLETTER_URL

    lines = [
        f"*Africa Gold Intelligence* | {date_str}",
        "",
        f"{arrow} *Gold: ${price:,.2f}* ({sign}{pct:.2f}%)",
        "",
    ]

    # Top 4 African prices
    for cur, rate in list(fx.items())[:4]:
        k24 = kp.get(cur, {}).get("24K")
        sym = {"ZAR": "R", "GHS": "GH₵", "NGN": "₦", "KES": "KSh", "EGP": "E£", "MAD": "DH"}.get(cur, "")
        if rate and k24:
            lines.append(f"• {cur}: *{sym}{k24:,.0f}/g* (24K)")

    lines += [
        "",
        "📖 Full briefing (free + premium):",
        link,
        "",
        "_Reply STOP to unsubscribe_",
    ]

    return "\n".join(lines)


# ── Auto-posting (optional) ─────────────────────────────────────────────────────

def post_to_twitter(text: str) -> dict:
    """Post to Twitter/X using v2 API. Requires tweepy installed + API keys set."""
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET,
                TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET]):
        return {"success": False, "reason": "Twitter API keys not set"}
    try:
        import tweepy
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_SECRET,
        )
        resp = client.create_tweet(text=text)
        tweet_id = resp.data["id"]
        return {"success": True, "tweet_id": tweet_id,
                "url": f"https://twitter.com/i/web/status/{tweet_id}"}
    except ImportError:
        return {"success": False, "reason": "tweepy not installed — run: pip install tweepy"}
    except Exception as e:
        return {"success": False, "reason": str(e)}


def post_to_linkedin(text: str) -> dict:
    """Post to LinkedIn using v2 API. Requires LINKEDIN_ACCESS_TOKEN + LINKEDIN_PERSON_URN."""
    if not all([LINKEDIN_ACCESS_TOKEN, LINKEDIN_PERSON_URN]):
        return {"success": False, "reason": "LinkedIn credentials not set"}
    try:
        import requests
        payload = {
            "author": LINKEDIN_PERSON_URN,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        headers = {
            "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }
        resp = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers=headers, json=payload, timeout=15,
        )
        if resp.status_code in (200, 201):
            post_id = resp.headers.get("x-restli-id", "unknown")
            return {"success": True, "post_id": post_id}
        return {"success": False, "reason": f"LinkedIn API {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        return {"success": False, "reason": str(e)}


# ── Logging ─────────────────────────────────────────────────────────────────────

def log_social_run(post_type: str, today: datetime.datetime,
                   twitter_post: str, linkedin_post: str, whatsapp_msg: str,
                   posted: dict):
    record = {
        "ts":            today.isoformat(),
        "post_type":     post_type,
        "twitter_chars": len(twitter_post),
        "linkedin_chars": len(linkedin_post),
        "whatsapp_chars": len(whatsapp_msg),
        "posted":        posted,
    }
    try:
        with open(SOCIAL_LOG, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        print(f"  ⚠️  Social log write failed: {e}")


# ── Main entry point ────────────────────────────────────────────────────────────

def run(post_type: str, data: dict, today: datetime.datetime,
        seo_data: dict = None, post_url: str = "") -> dict:
    """
    Main entry point — called by orchestrator.py.

    post_url: the real Beehiiv web_url if the post was created successfully,
              otherwise "" — falls back to newsletter homepage so links are never 404.

    Returns social_data dict:
        twitter          — tweet text (≤280 chars)
        linkedin         — LinkedIn post text
        whatsapp         — WhatsApp broadcast text
        posted_platforms — dict of {platform: result} for any auto-posted platforms
    """
    slug = seo_data.get("slug") if seo_data else None

    # Use real post URL if available, otherwise homepage (never a dead slug URL)
    resolved_url = post_url.strip() if post_url and post_url.strip() else None
    # Override slug-based link building with the resolved URL
    _slug = slug if resolved_url else None   # suppress slug if no live URL yet

    twitter_post  = build_twitter_post(post_type, data, today, _slug, resolved_url)
    linkedin_post = build_linkedin_post(post_type, data, today, _slug, resolved_url)
    whatsapp_msg  = build_whatsapp_message(post_type, data, today, _slug, resolved_url)

    posted = {}

    # Auto-post to Twitter/X if keys are configured
    if TWITTER_API_KEY:
        print("  🐦 Posting to Twitter/X...")
        result = post_to_twitter(twitter_post)
        posted["twitter"] = result
        if result["success"]:
            print(f"     ✅ Tweeted → {result.get('url', '')}")
        else:
            print(f"     ⚠️  Twitter failed: {result['reason']}")
    else:
        print("  🐦 Twitter/X: keys not set — post included in email for manual copy.")

    # Auto-post to LinkedIn if keys are configured
    if LINKEDIN_ACCESS_TOKEN:
        print("  💼 Posting to LinkedIn...")
        result = post_to_linkedin(linkedin_post)
        posted["linkedin"] = result
        if result["success"]:
            print(f"     ✅ LinkedIn post created → ID: {result.get('post_id', '')}")
        else:
            print(f"     ⚠️  LinkedIn failed: {result['reason']}")
    else:
        print("  💼 LinkedIn: token not set — post included in email for manual copy.")

    print(f"  📱 WhatsApp message ready ({len(whatsapp_msg)} chars) — copy from email.")

    log_social_run(post_type, today, twitter_post, linkedin_post, whatsapp_msg, posted)

    return {
        "twitter":          twitter_post,
        "linkedin":         linkedin_post,
        "whatsapp":         whatsapp_msg,
        "posted_platforms": posted,
    }


# ── Standalone test ─────────────────────────────────────────────────────────────

def _test():
    today = datetime.datetime.now()
    mock_data = {
        "gold":   {"price": 5205.60, "day_chg_pct": 2.89, "rsi": 68.4},
        "silver": {"price": 87.26},
        "dxy":    {"price": 97.81},
        "sp500":  {"price": 6838},
        "fx_rates": {
            "ZAR": 16.01, "GHS": 10.84, "NGN": 1344.40,
            "KES": 129.03, "EGP": 47.71, "MAD": 9.16,
        },
        "karat_prices": {
            "ZAR": {"24K": 2680, "22K": 2457, "18K": 2010},
            "GHS": {"24K": 1814},
            "NGN": {"24K": 225004},
            "KES": {"24K": 21595},
        },
        "news": [
            {"title": "Gold surges to record as dollar weakens on Fed signals", "source": "Reuters"},
        ],
    }
    mock_seo = {"slug": "gold-briefing-trader-intelligence-2026-02-24"}

    for pt in ["trader_intelligence", "africa_regional", "karat_pricing"]:
        result = run(pt, mock_data, today, mock_seo)
        print(f"\n{'═'*60}")
        print(f"  POST TYPE: {pt}")
        print(f"\n── Twitter/X ({len(result['twitter'])} chars) ──")
        print(result["twitter"])
        print(f"\n── LinkedIn ({len(result['linkedin'])} chars) ──")
        print(result["linkedin"][:300] + "...")
        print(f"\n── WhatsApp ({len(result['whatsapp'])} chars) ──")
        print(result["whatsapp"])

    print(f"\n✅ Social Agent test complete. Log: {SOCIAL_LOG}\n")


if __name__ == "__main__":
    _test()
