#!/usr/bin/env python3
"""
linkedin_post.py — Africa Gold Intelligence LinkedIn Post Generator
===================================================================
Generates a compelling daily LinkedIn post from the pipeline's market data
and saves it to data/linkedin_pending.txt for browser automation to publish.

Called by orchestrator.py after the main pipeline run completes.
"""

import os
import json
import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
PENDING_FILE = PROJECT_ROOT / "data" / "linkedin_pending.txt"

# Day-of-week editorial themes (mirrors the newsletter calendar)
DAY_THEMES = {
    0: ("📊 Trader Monday", "monday_trader"),
    1: ("🌍 Africa Tuesday", "tuesday_regional"),
    2: ("📡 Midweek Pulse", "wednesday_digest"),
    3: ("💎 Karat Thursday", "thursday_karat"),
    4: ("🌐 Macro Friday", "friday_macro"),
    5: ("📚 Weekend Learn", "saturday_edu"),
    6: ("📈 Week in Review", "sunday_review"),
}


def _arrow(pct) -> str:
    if pct is None:
        return "→"
    return "▲" if pct >= 0 else "▼"


def _sign(val, suffix="") -> str:
    if val is None:
        return "N/A"
    return f"+{val:.2f}{suffix}" if val >= 0 else f"{val:.2f}{suffix}"


def _sentiment(gold_pct, rsi) -> str:
    """Return a one-liner market sentiment string."""
    rsi = rsi or 50
    if gold_pct is None:
        gold_pct = 0
    if gold_pct > 0.5 and rsi < 70:
        return "Momentum is building. 🟢"
    elif gold_pct > 0.5 and rsi >= 70:
        return "Rally may be getting stretched — watch for pullback. ⚠️"
    elif gold_pct < -0.5 and rsi > 30:
        return "Selling pressure today. Watch key support. 🔴"
    elif gold_pct < -0.5 and rsi <= 30:
        return "Oversold — potential reversal zone. 👀"
    else:
        return "Gold consolidating in a tight range. Patience rewarded. ⚖️"


def generate_linkedin_post(data: dict, today: datetime.datetime, post_type: str) -> str:
    """
    Build a LinkedIn post from pipeline market data.
    Returns the post as a plain string ready to paste/type.
    """
    gold   = data.get("gold", {})
    silver = data.get("silver", {})
    dxy    = data.get("dxy", {})
    sp500  = data.get("sp500", {})

    g_price  = gold.get("price", 0)
    g_pct    = gold.get("day_chg_pct", 0)
    g_chg    = gold.get("day_chg", 0)
    rsi      = gold.get("rsi")
    week_pct = gold.get("week_chg_pct", 0)

    s_price  = silver.get("price", 0)
    dxy_val  = dxy.get("price", 0)
    dxy_pct  = dxy.get("day_chg_pct", 0)

    date_str  = today.strftime("%A, %B %d %Y")
    day_idx   = today.weekday()
    theme_label, _ = DAY_THEMES.get(day_idx, ("🌟 Daily Briefing", "daily"))
    sentiment = _sentiment(g_pct, rsi)

    gs_ratio  = round(g_price / s_price, 1) if s_price else 0

    # Build post sections
    intro = (
        f"🥇 Gold Market Update — {date_str}\n\n"
        f"XAU/USD: ${g_price:,.2f}  {_arrow(g_pct)} {_sign(g_pct, '%')} today\n"
        f"Weekly: {_sign(week_pct, '%')}  |  RSI-14: {round(rsi) if rsi else 'N/A'}\n\n"
        f"{sentiment}"
    )

    macro = (
        f"\n\n📌 Key Drivers:\n"
        f"• Dollar Index (DXY): {dxy_val:.2f} ({_sign(dxy_pct, '%')}) — "
        f"{'supportive for gold 🟢' if (dxy_pct or 0) < 0 else 'headwind for gold 🔴'}\n"
        f"• Silver: ${s_price:.2f} | Gold/Silver ratio: {gs_ratio}x\n"
        f"• S&P 500: {_sign(sp500.get('day_chg_pct'), '%')} — "
        f"{'risk-on tone' if (sp500.get('day_chg_pct') or 0) > 0 else 'risk-off tone'}"
    )

    africa_note = (
        "\n\n🌍 For African investors:\n"
        "Currency depreciation amplifies every gold move. "
        "Local gold prices in ZAR, GHS, NGN & KES are in today's full briefing."
    )

    cta = (
        "\n\n📬 Full briefing (free + premium) in our newsletter.\n"
        "Subscribe → africagoldintelligence.com\n\n"
        "#Gold #XAU #AfricaInvesting #PreciousMetals #GoldMarket "
        "#AfricaGoldIntelligence #Commodities"
    )

    return intro + macro + africa_note + cta


def save_pending_post(post_text: str) -> Path:
    """Save post text to data/linkedin_pending.txt (overwrites previous)."""
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    PENDING_FILE.write_text(post_text, encoding="utf-8")
    return PENDING_FILE


def run(data: dict, today: datetime.datetime, post_type: str) -> dict:
    """
    Entry point called by orchestrator.
    Returns a result dict compatible with the pipeline log format.
    """
    try:
        post_text = generate_linkedin_post(data, today, post_type)
        path = save_pending_post(post_text)
        char_count = len(post_text)
        print(f"[LinkedIn] Post generated ({char_count} chars) → {path}")
        return {
            "status": "ok",
            "char_count": char_count,
            "pending_file": str(path),
        }
    except Exception as e:
        print(f"[LinkedIn] ERROR generating post: {e}")
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    # Quick test with dummy data
    dummy = {
        "gold":   {"price": 2345.50, "day_chg_pct": 0.42, "day_chg": 9.8, "rsi": 58, "week_chg_pct": 1.1},
        "silver": {"price": 29.45},
        "dxy":    {"price": 103.2, "day_chg_pct": -0.15},
        "sp500":  {"price": 5200, "day_chg_pct": 0.3},
    }
    today = datetime.datetime.now()
    print(generate_linkedin_post(dummy, today, "africa_regional"))
