#!/usr/bin/env python3
"""
notebooklm_digest.py — Africa Gold Intelligence
================================================
Generates a richly structured weekly source document for NotebookLM's
Audio Overview (podcast) feature. Runs on Sundays as part of the
week_review pipeline pass.

Output: data/podcasts/notebooklm_YYYY-WXX.md
        (also written to data/podcasts/latest.md for the scheduled task)

The document is written for spoken-word comprehension — dense facts,
narrative connective tissue, no raw HTML, no markdown tables.
"""

import os, json, datetime, re
from pathlib import Path

SCRIPT_DIR  = Path(__file__).parent.parent
PODCAST_DIR = SCRIPT_DIR / "data" / "podcasts"
LOG_FILE    = SCRIPT_DIR / "logs" / "run_log.jsonl"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sign(v):
    if v is None: return ""
    return "+" if float(v) >= 0 else ""

def _fmt(v, dp=2, prefix="$"):
    if v is None: return "N/A"
    return f"{prefix}{float(v):,.{dp}f}"

def _pct(v):
    if v is None: return "N/A"
    return f"{_sign(v)}{float(v):.2f}%"

def _week_label(dt: datetime.datetime) -> str:
    """Returns ISO week label, e.g. '2026-W10'."""
    return dt.strftime("%Y-W%V")

def _load_recent_logs(n_days=7) -> list:
    """Load last n_days of SUCCESS entries from run_log.jsonl."""
    if not LOG_FILE.exists():
        return []
    cutoff = datetime.datetime.now() - datetime.timedelta(days=n_days)
    entries = []
    for line in LOG_FILE.read_text().strip().splitlines():
        try:
            r = json.loads(line)
            if r.get("status") == "SUCCESS":
                ts = datetime.datetime.fromisoformat(r["ts"])
                if ts >= cutoff:
                    entries.append(r)
        except Exception:
            pass
    return entries


# ── Narrative section builders ────────────────────────────────────────────────

def _section_gold_summary(data: dict, today: datetime.datetime) -> str:
    gold   = data.get("gold",   {})
    silver = data.get("silver", {})
    dxy    = data.get("dxy",    {})
    sp500  = data.get("sp500",  {})
    btc    = data.get("btc",    {})

    g_price = gold.get("price", 0)
    g_pct   = gold.get("day_chg_pct", 0) or 0
    g_week  = gold.get("week_chg_pct", 0) or 0
    g_rsi   = gold.get("rsi")
    direction = "higher" if g_pct >= 0 else "lower"
    week_dir  = "gaining" if g_week >= 0 else "losing"

    rsi_note = ""
    if g_rsi:
        if g_rsi > 70:
            rsi_note = f" The RSI-14 reading of {g_rsi} signals overbought conditions — momentum traders may begin taking profits."
        elif g_rsi < 30:
            rsi_note = f" The RSI-14 reading of {g_rsi} signals oversold conditions — historically a setup for mean reversion."
        else:
            rsi_note = f" The RSI-14 sits at {g_rsi}, neutral territory with no extreme signal in either direction."

    lines = [
        "GOLD MARKET WEEKLY REVIEW",
        "=" * 40,
        "",
        f"Week of {today.strftime('%B %d, %Y')} — Africa Gold Intelligence Briefing",
        "",
        "GOLD PRICE OVERVIEW",
        "-" * 20,
        f"Gold closed this week at {_fmt(g_price)}/oz, finishing {direction} by {_pct(g_pct)} on the day "
        f"and {week_dir} {_pct(g_week)} over the full seven-day period.{rsi_note}",
        "",
    ]

    if silver and silver.get("price"):
        gs_ratio = g_price / silver["price"] if silver["price"] else None
        gs_note = (
            f"The gold-to-silver ratio stands at {gs_ratio:.1f}, meaning it takes "
            f"{gs_ratio:.0f} ounces of silver to buy one ounce of gold."
            if gs_ratio else ""
        )
        lines += [
            f"Silver tracked at {_fmt(silver.get('price'))}/oz ({_pct(silver.get('day_chg_pct'))}). {gs_note}",
            "",
        ]

    if dxy and dxy.get("price"):
        dxy_dir = "strengthened" if (dxy.get("day_chg_pct") or 0) >= 0 else "weakened"
        lines += [
            f"The US Dollar Index {dxy_dir} to {_fmt(dxy.get('price'), dp=3, prefix='')} ({_pct(dxy.get('day_chg_pct'))}). "
            f"Dollar moves are the single biggest external driver of gold's price in local African currencies.",
            "",
        ]

    if sp500 and sp500.get("price"):
        eq_dir = "rallied" if (sp500.get("day_chg_pct") or 0) >= 0 else "sold off"
        lines += [
            f"US equities {eq_dir} — the S&P 500 closed at {_fmt(sp500.get('price'), dp=0)} ({_pct(sp500.get('day_chg_pct'))}). "
            f"Risk appetite in global markets influences whether investors rotate into or out of safe-haven gold.",
            "",
        ]

    if btc and btc.get("price"):
        lines += [
            f"Bitcoin closed at {_fmt(btc.get('price'), dp=0)} ({_pct(btc.get('day_chg_pct'))}), "
            f"a benchmark for risk-on sentiment that often moves inversely to gold during liquidity-driven selloffs.",
            "",
        ]

    return "\n".join(lines)


def _section_african_currencies(data: dict) -> str:
    fx_rates     = data.get("fx_rates",     {})
    karat_prices = data.get("karat_prices", {})
    gold_price   = data.get("gold", {}).get("price", 0)

    NAMES = {
        "ZAR": ("South African Rand",  "R",   "South Africa"),
        "GHS": ("Ghanaian Cedi",       "GH₵", "Ghana"),
        "NGN": ("Nigerian Naira",      "₦",   "Nigeria"),
        "KES": ("Kenyan Shilling",     "KSh", "Kenya"),
        "EGP": ("Egyptian Pound",      "E£",  "Egypt"),
        "MAD": ("Moroccan Dirham",     "MAD", "Morocco"),
    }

    lines = [
        "GOLD PRICES FOR AFRICAN INVESTORS",
        "-" * 20,
        "For African buyers and investors, the dollar price of gold is only part of the story. "
        "Local currency exchange rates determine what you actually pay at the jeweler or receive when you sell.",
        "",
    ]

    for cur, rate in fx_rates.items():
        if not rate or cur not in NAMES:
            continue
        full_name, sym, country = NAMES[cur]
        k24 = karat_prices.get(cur, {}).get("24K")
        k22 = karat_prices.get(cur, {}).get("22K")
        k18 = karat_prices.get(cur, {}).get("18K")
        if not k24:
            continue
        oz_local = gold_price * rate if gold_price and rate else None
        lines += [
            f"In {country}, one US dollar buys {rate:,.2f} {full_name}s (USD/{cur}: {rate:.2f}). "
            f"At this rate, a troy ounce of gold costs {sym}{oz_local:,.0f}. "
            f"Per gram: 24-karat is {sym}{k24:,.0f}, 22-karat is {sym}{k22:,.0f}, 18-karat is {sym}{k18:,.0f}.",
            "",
        ]

    return "\n".join(lines)


def _section_africa_miners(data: dict, africa_data: dict) -> str:
    if not africa_data:
        return ""

    miners     = africa_data.get("miners", {})
    pan        = africa_data.get("pan_african", {})
    seasonal   = africa_data.get("seasonal_signals", [])

    lines = [
        "AFRICA MINING SECTOR",
        "-" * 20,
    ]

    if pan:
        w_margin     = pan.get("weighted_avg_margin", 0)
        w_margin_pct = pan.get("weighted_margin_pct", 0)
        lines += [
            f"The pan-African composite mining margin — the average profit per ounce after all-in sustaining costs — "
            f"stands at ${w_margin:,.0f}/oz, representing a {w_margin_pct:.1f}% return on the current gold price. "
            f"This figure captures the blended profitability of the continent's major gold producers.",
            "",
        ]

    if miners:
        best_name   = africa_data.get("top_miner", "")
        best_margin = 0
        worst_name  = africa_data.get("weakest_miner", "")
        worst_margin = 0
        for name, m in miners.items():
            mg = m.get("margin", 0) or 0
            if name == best_name:
                best_margin = mg
            if name == worst_name:
                worst_margin = mg

        if best_name and best_margin:
            lines += [
                f"Among tracked miners, {best_name} leads the field with a margin of ${best_margin:,.0f}/oz — "
                f"the highest profitability per ounce this week.",
            ]
        if worst_name and worst_margin is not None:
            lines += [
                f"At the other end, {worst_name} operates on a tighter margin of ${worst_margin:,.0f}/oz, "
                f"making it most sensitive to any pullback in the gold price.",
                "",
            ]

    if seasonal:
        for sig in seasonal[:2]:
            lines.append(f"Seasonal note: {sig.get('signal', '')} — {sig.get('detail', '')}")
        lines.append("")

    return "\n".join(lines)


def _section_contract_watch(contract_data: dict) -> str:
    if not contract_data:
        return ""

    shadow       = contract_data.get("shadow_data", {})
    royalty_gap  = contract_data.get("total_gap_usd", 0)
    nationalism  = contract_data.get("nationalism_alerts", [])
    active_alerts = [n for n in nationalism
                     if n.get("status") in ("nationalised", "renegotiated", "renegotiating")]

    lines = [
        "CONTRACT TRANSPARENCY & RESOURCE GOVERNANCE",
        "-" * 20,
    ]

    if royalty_gap:
        lines += [
            f"Africa's mining royalty gap — the difference between royalties actually paid and what would be "
            f"collected under an eight percent benchmark — stands at ${royalty_gap/1e6:.0f} million annually. "
            f"This represents revenue that could fund public services but currently flows to mining companies.",
            "",
        ]

    if shadow and shadow.get("illicit_mid_tonnes"):
        val_bn = shadow.get("illicit_mid_usd_bn", 0)
        tonnes = shadow.get("illicit_mid_tonnes", 0)
        lines += [
            f"The shadow economy tracker estimates approximately {tonnes} tonnes of gold leave Africa "
            f"through informal or illicit channels each year, valued at around ${val_bn:.1f} billion — "
            f"a figure that underscores why contract transparency and border monitoring matter.",
            "",
        ]

    if active_alerts:
        lines.append(f"Active resource nationalism alerts this week ({len(active_alerts)}):")
        for alert in active_alerts[:3]:
            lines.append(
                f"  — {alert.get('country', 'Unknown')}: {alert.get('company', '')} contract status "
                f"is '{alert.get('status', '')}'. {alert.get('detail', '')}"
            )
        lines.append("")

    return "\n".join(lines)


def _section_news(data: dict, africa_data: dict, contract_data: dict) -> str:
    all_news = list(data.get("news", []))
    if africa_data:
        all_news += africa_data.get("africa_news", [])
    if contract_data:
        all_news += contract_data.get("contract_news", [])

    if not all_news:
        return ""

    lines = [
        "KEY NEWS AND MARKET HEADLINES",
        "-" * 20,
        "The following headlines shaped market sentiment this week:",
        "",
    ]
    seen = set()
    for item in all_news[:10]:
        title = item.get("title", "").strip()
        if title and title not in seen:
            seen.add(title)
            source = item.get("source", "")
            lines.append(f"From {source}: {title}")
    lines.append("")
    return "\n".join(lines)


def _section_outlook(data: dict, today: datetime.datetime) -> str:
    gold  = data.get("gold", {})
    g_rsi = gold.get("rsi")

    next_week = today + datetime.timedelta(days=7)
    lines = [
        "WEEK AHEAD — WHAT TO WATCH",
        "-" * 20,
    ]

    if g_rsi:
        if g_rsi > 65:
            lines.append(
                f"With RSI-14 at {g_rsi}, momentum is elevated. Watch for profit-taking pressure near current levels. "
                f"Any Fed communication or strong US jobs data could be the catalyst for a pullback."
            )
        elif g_rsi < 40:
            lines.append(
                f"With RSI-14 at {g_rsi}, gold is approaching oversold levels. Historically this creates a "
                f"mean-reversion setup, particularly if macro headlines remain gold-supportive."
            )
        else:
            lines.append(
                f"With RSI-14 at {g_rsi}, gold is in neutral territory — no strong directional signal from momentum alone. "
                f"Watch for macro catalysts: central bank commentary, inflation data, and geopolitical headlines."
            )
    else:
        lines.append(
            "Key factors to monitor: Federal Reserve commentary, US inflation prints, dollar index movement, "
            "and any central bank gold purchasing announcements — particularly from African central banks."
        )

    lines += [
        "",
        f"For African investors specifically: monitor your local currency against the dollar. "
        f"A weakening rand, cedi, or naira amplifies gold returns in local currency terms even if the dollar price is flat.",
        "",
        f"This briefing covers the week ending {today.strftime('%B %d, %Y')}. "
        f"The next Africa Gold Intelligence weekly review will cover the week of {next_week.strftime('%B %d')}.",
        "",
        "This report is produced by Africa Gold Intelligence for informational purposes. "
        "It does not constitute investment advice.",
    ]
    return "\n".join(lines)


# ── Main entry point ──────────────────────────────────────────────────────────

def run(data: dict, today: datetime.datetime,
        africa_data: dict = None, contract_data: dict = None) -> dict:
    """
    Generate the weekly NotebookLM source document.
    Returns {"status": "ok", "path": str, "word_count": int}
    """
    PODCAST_DIR.mkdir(parents=True, exist_ok=True)

    week_label = _week_label(today)
    filename   = f"notebooklm_{week_label}.md"
    out_path   = PODCAST_DIR / filename
    latest     = PODCAST_DIR / "latest.md"

    sections = [
        _section_gold_summary(data, today),
        _section_african_currencies(data),
        _section_africa_miners(data, africa_data or {}),
        _section_contract_watch(contract_data or {}),
        _section_news(data, africa_data or {}, contract_data or {}),
        _section_outlook(data, today),
    ]

    doc = "\n\n".join(s for s in sections if s.strip())
    word_count = len(doc.split())

    out_path.write_text(doc, encoding="utf-8")
    latest.write_text(doc, encoding="utf-8")

    print(f"  ✅ NotebookLM digest saved → {out_path.name}  ({word_count:,} words)")
    return {
        "status":     "ok",
        "path":       str(out_path),
        "latest":     str(latest),
        "week":       week_label,
        "word_count": word_count,
    }
