#!/usr/bin/env python3
"""
beehiiv_daily_post.py — Africa Gold Intelligence Daily Automation
=================================================================
Creates and publishes a daily gold-market post to Beehiiv using the V2 API.
Content rotates by day of week (7-day editorial calendar).

SETUP — DO THIS ONCE:
  1. Go to https://app.beehiiv.com/settings/api  →  generate an API key.
  2. Export it in your shell (or add to ~/.zshrc / ~/.bashrc):
       export BEEHIIV_API_KEY="your_key_here"
  3. Optionally set BEEHIIV_PUB_ID if different from the default below.
  4. Install dependencies:
       pip install yfinance feedparser requests --break-system-packages

RUN MANUALLY:
  python3 beehiiv_daily_post.py

SCHEDULED (via schedule-task or cron):
  0 6 * * * /usr/bin/python3 /path/to/beehiiv_daily_post.py >> /tmp/agi_post.log 2>&1
"""

import os, sys, json, datetime, math, time
import urllib.request

# ── CONFIG ────────────────────────────────────────────────────────────────────
BEEHIIV_API_KEY = os.environ.get("BEEHIIV_API_KEY", "")
BEEHIIV_PUB_ID  = os.environ.get("BEEHIIV_PUB_ID",  "pub_5927fa56-6b7c-4310-8f35-2ff9d18f523b")
BEEHIIV_API_URL = f"https://api.beehiiv.com/v2/publications/{BEEHIIV_PUB_ID}/posts"

# Set to "draft" while testing, "instant" for live publishing
PUBLISH_TYPE    = os.environ.get("AGI_PUBLISH_TYPE", "instant")

# Africa regional spotlight rotation (one country per day-of-month cycle)
REGIONAL_ROTATION = ["South Africa", "Ghana", "Nigeria", "Kenya", "Egypt",
                     "Morocco", "Ethiopia", "Tanzania", "Uganda", "Zimbabwe"]
# ──────────────────────────────────────────────────────────────────────────────

# Yahoo Finance tickers
GOLD_TICKER   = "GC=F"
SILVER_TICKER = "SI=F"
DXY_TICKER    = "DX-Y.NYB"
SP500_TICKER  = "^GSPC"
BTC_TICKER    = "BTC-USD"

# African FX pairs (USD → local currency)
FX_TICKERS = {
    "ZAR": "USDZAR=X",
    "GHS": "USDGHS=X",
    "NGN": "USDNGN=X",
    "KES": "USDKES=X",
    "EGP": "USDEGP=X",
    "MAD": "USDMAD=X",
}

# Karat weights (fraction of pure gold)
KARATS = {"24K": 1.0, "22K": 22/24, "18K": 18/24, "14K": 14/24, "9K": 9/24}
TROY_OZ_TO_GRAM = 31.1035

# RSS news sources — ordered by reliability; pipeline stops once max_items reached
NEWS_FEEDS = [
    ("Kitco",        "https://www.kitco.com/rss/feed/news.xml"),
    ("Investing.com","https://www.investing.com/rss/news_25.rss"),       # Commodities
    ("FX Street",    "https://www.fxstreet.com/rss/news"),
    ("Nasdaq",       "https://www.nasdaq.com/feed/rssoutbound?category=Commodities"),
    ("BullionVault", "https://www.bullionvault.com/gold-news/rss.do"),
    ("MarketWatch",  "https://feeds.marketwatch.com/marketwatch/marketpulse/"),
]
GOLD_KEYWORDS = [
    "gold", "xau", "bullion", "precious metal", "silver", "platinum",
    "fed rate", "federal reserve", "inflation", "dollar index", "safe haven",
    "treasury yield", "bond yield", "real yield", "commodity",
    "rate cut", "rate hike", "fomc", "powell", "central bank",
]

# 7-day editorial calendar
DAY_TYPES = {
    0: "trader_intelligence",   # Monday
    1: "africa_regional",       # Tuesday
    2: "aggregator",            # Wednesday
    3: "karat_pricing",         # Thursday
    4: "macro_outlook",         # Friday
    5: "educational",           # Saturday
    6: "week_review",           # Sunday
}


# ════════════════════════════════════════════════════════════════════════════
# DATA FETCHING
# ════════════════════════════════════════════════════════════════════════════

def fetch_yfinance(ticker: str, period="30d") -> dict:
    """Fetch OHLCV from Yahoo Finance via yfinance.
    Uses 30d history so RSI-14 always has enough data points (needs 15+ closes)."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        hist = t.history(period=period, interval="1d")
        if hist.empty:
            return {}
        current  = float(hist["Close"].iloc[-1])
        prev     = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
        # week_ago: 5 trading days back from latest
        week_idx = max(0, len(hist) - 6)
        week_ago = float(hist["Close"].iloc[week_idx])
        day_chg      = current - prev
        day_chg_pct  = (day_chg / prev * 100) if prev else 0
        week_chg_pct = ((current - week_ago) / week_ago * 100) if week_ago else 0
        # RSI-14 — guaranteed enough data with 30d
        closes = list(hist["Close"])
        rsi = calc_rsi(closes)
        return {
            "price": current, "prev": prev,
            "day_chg": day_chg, "day_chg_pct": day_chg_pct,
            "week_chg_pct": week_chg_pct, "rsi": rsi,
        }
    except Exception as e:
        print(f"  yfinance [{ticker}] error: {e}")
        return {}


def calc_rsi(closes: list, period=14) -> "float | None":
    """Simple RSI-14 calculation."""
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_g = sum(gains[-period:]) / period
    avg_l = sum(losses[-period:]) / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return round(100 - (100 / (1 + rs)), 1)


def fetch_fx_rates() -> dict:
    """Fetch USD → African currency FX rates."""
    rates = {}
    for currency, ticker in FX_TICKERS.items():
        d = fetch_yfinance(ticker, period="5d")
        if d:
            rates[currency] = d["price"]
        else:
            # Approximate fallback rates (updated periodically)
            fallback = {"ZAR": 18.50, "GHS": 15.80, "NGN": 1620.0,
                        "KES": 129.0, "EGP": 50.5, "MAD": 10.05}
            rates[currency] = fallback.get(currency)
            print(f"  FX fallback used for {currency}: {rates[currency]}")
    return rates


def calc_karat_prices(gold_usd: float, fx_rates: dict) -> dict:
    """
    Returns nested dict: result[currency][karat] = price_per_gram
    """
    gold_per_gram_usd = gold_usd / TROY_OZ_TO_GRAM
    result = {}
    for currency, rate in fx_rates.items():
        if rate is None:
            continue
        gold_per_gram_local = gold_per_gram_usd * rate
        result[currency] = {k: round(gold_per_gram_local * frac, 2)
                            for k, frac in KARATS.items()}
    return result


def fetch_news(max_items=6) -> list:
    """Fetch gold-related headlines from RSS feeds.
    Each feed gets a 10s timeout; dead feeds are skipped silently."""
    try:
        import feedparser
    except ImportError:
        print("feedparser not installed — skipping news")
        return []
    import socket
    items = []
    orig_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(10)   # 10s per feed — don't let one dead feed stall pipeline
    try:
        for source, url in NEWS_FEEDS:
            if len(items) >= max_items:
                break
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:40]:
                    title   = entry.get("title", "")
                    summary = entry.get("summary", "")
                    link    = entry.get("link", "#")
                    if any(kw in (title + " " + summary).lower() for kw in GOLD_KEYWORDS):
                        items.append({"source": source, "title": title, "link": link})
                    if len(items) >= max_items:
                        break
            except Exception as e:
                print(f"  RSS [{source}] error: {e}")
    finally:
        socket.setdefaulttimeout(orig_timeout)
    return items[:max_items]


# ════════════════════════════════════════════════════════════════════════════
# FORMATTING HELPERS
# ════════════════════════════════════════════════════════════════════════════

def arrow(v):
    return "▲" if (v or 0) >= 0 else "▼"

def sign_str(v, suffix="", dp=2):
    if v is None: return "—"
    s = "+" if v >= 0 else ""
    return f"{s}{v:.{dp}f}{suffix}"

def fmt_price(v, prefix="$", dp=2):
    return f"{prefix}{v:,.{dp}f}" if v is not None else "—"

def green_red(v):
    return "#16a34a" if (v or 0) >= 0 else "#dc2626"

def rsi_label(rsi):
    if rsi is None: return "N/A"
    if rsi >= 70: return f"{rsi} 🔴 Overbought"
    if rsi <= 30: return f"{rsi} 🟢 Oversold"
    return f"{rsi} ⚪ Neutral"

def support_resistance(gold_price: float) -> dict:
    """Approximate key levels based on round numbers and % bands."""
    p = gold_price
    levels = {
        "s1": round(p * 0.990 / 10) * 10,
        "s2": round(p * 0.975 / 10) * 10,
        "r1": round(p * 1.010 / 10) * 10,
        "r2": round(p * 1.025 / 10) * 10,
    }
    return levels

def bias_str(rsi, day_chg_pct):
    """Simple bias based on RSI + daily momentum."""
    if rsi is None: return "NEUTRAL"
    if rsi < 40 and (day_chg_pct or 0) < 0: return "BEARISH"
    if rsi > 60 and (day_chg_pct or 0) > 0: return "BULLISH"
    if rsi < 45: return "MILD BEARISH"
    if rsi > 55: return "MILD BULLISH"
    return "NEUTRAL"

CURRENCY_SYMBOLS = {
    "ZAR": "R", "GHS": "GH₵", "NGN": "₦",
    "KES": "KSh", "EGP": "E£", "MAD": "DH"
}
CURRENCY_NAMES = {
    "ZAR": "South African Rand", "GHS": "Ghanaian Cedi",
    "NGN": "Nigerian Naira", "KES": "Kenyan Shilling",
    "EGP": "Egyptian Pound", "MAD": "Moroccan Dirham"
}


# ════════════════════════════════════════════════════════════════════════════
# CSS / SHARED HTML COMPONENTS
# ════════════════════════════════════════════════════════════════════════════

BASE_STYLE = """
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         color: #111827; line-height: 1.6; margin: 0; padding: 0; }

  /* ── Brand header ───────────────────────────────── */
  .agi-header { border-bottom: 3px solid #f59e0b; padding-bottom: 16px; margin-bottom: 22px; }
  .agi-header-wordmark { font-size: 0.65rem; font-weight: 900; text-transform: uppercase;
         letter-spacing: 0.18em; color: #92400e; margin: 0 0 4px; }
  .agi-header-title { font-size: 1.45rem; font-weight: 900; color: #111827;
         margin: 0 0 6px; line-height: 1.2; }
  .agi-header-meta { font-size: 0.78rem; color: #6b7280; margin: 0; }
  .agi-header-meta strong { color: #374151; }
  .agi-tier-free    { display:inline-block; background:#fef3c7; color:#92400e;
         font-size:10px; font-weight:800; text-transform:uppercase; letter-spacing:.1em;
         padding:2px 9px; border-radius:3px; border:1px solid #fde68a; }
  .agi-tier-premium { display:inline-block; background:#111827; color:#fbbf24;
         font-size:10px; font-weight:800; text-transform:uppercase; letter-spacing:.1em;
         padding:2px 9px; border-radius:3px; }

  /* ── Typography ─────────────────────────────────── */
  h2 { font-size: 1.15rem; font-weight: 800; color: #111827; margin: 1.6em 0 0.5em;
       padding-bottom: 8px; border-bottom: 2px solid #fde68a; }
  h3 { font-size: 0.97rem; font-weight: 700; color: #111827; margin: 1.4em 0 0.4em;
       padding-left: 10px; border-left: 3px solid #f59e0b; }
  p  { margin: 0.5em 0 0.8em; font-size: 0.92rem; color: #374151; }

  /* ── Snapshot box ───────────────────────────────── */
  .snapshot-box { background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
         border: 1px solid #fde68a; border-left: 4px solid #f59e0b;
         border-radius: 10px; padding: 18px 22px; margin: 12px 0; }
  .snapshot-label { font-size: 10px; font-weight: 800; text-transform: uppercase;
         letter-spacing: 0.12em; color: #92400e; margin: 0 0 6px; }
  .snapshot-price { font-size: 2.3rem; font-weight: 900; color: #111827; line-height: 1.1; }

  /* ── Tag / pill ─────────────────────────────────── */
  .tag { display: inline-block; font-size: 10px; font-weight: 800; text-transform: uppercase;
         letter-spacing: .1em; color: #92400e; background: #fef3c7;
         border: 1px solid #fde68a; border-radius: 4px; padding: 3px 9px; margin-bottom: 8px; }
  .pill { display: inline-block; border-radius: 999px; padding: 3px 10px;
          font-size: 11px; font-weight: 700; }
  .pill-buy     { background: #dcfce7; color: #15803d; }
  .pill-sell    { background: #fee2e2; color: #b91c1c; }
  .pill-neutral { background: #f3f4f6; color: #374151; }

  /* ── Tables ─────────────────────────────────────── */
  table.data { width: 100%; border-collapse: collapse; margin: 10px 0 16px;
               border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; }
  table.data th { font-size: 10px; color: #6b7280; font-weight: 800;
         text-transform: uppercase; letter-spacing: 0.07em;
         padding: 8px 12px; background: #f9fafb;
         border-bottom: 1px solid #e5e7eb; text-align: left; }
  table.data td { padding: 10px 12px; border-bottom: 1px solid #f3f4f6;
                  font-size: 0.88rem; color: #374151; }
  table.data tr:last-child td { border-bottom: none; }

  /* ── Colours ────────────────────────────────────── */
  .up   { color: #15803d; font-weight: 700; }
  .down { color: #dc2626; font-weight: 700; }

  /* ── CTA block ──────────────────────────────────── */
  .cta { background: #1c1917; color: #fff; border-radius: 10px;
         padding: 18px 22px; margin: 18px 0; border-left: 4px solid #f59e0b; }
  .cta p { color: #d6d3d1; margin: 0; font-size: 0.88rem; line-height: 1.65; }
  .cta strong { color: #fbbf24; }

  /* ── Footer ─────────────────────────────────────── */
  .agi-footer { margin-top: 28px; padding-top: 16px; border-top: 2px solid #fde68a;
         font-size: 0.73rem; color: #9ca3af; line-height: 1.8; }
  .agi-footer strong { color: #6b7280; }
  .agi-footer a { color: #f59e0b; text-decoration: none; }
</style>
"""

# ── Brand header helper ───────────────────────────────────────────────────────
def brand_header(title: str, date_str: str, post_type_label: str, is_premium: bool = False) -> str:
    tier_cls  = "agi-tier-premium" if is_premium else "agi-tier-free"
    tier_text = "Premium Edition" if is_premium else "Free Preview"
    return (
        '<div class="agi-header">\n'
        '  <p class="agi-header-wordmark">Africa Gold Intelligence</p>\n'
        f'  <p class="agi-header-title">{title}</p>\n'
        f'  <p class="agi-header-meta">{date_str} &nbsp;·&nbsp; {post_type_label} &nbsp;·&nbsp; '
        f'<span class="{tier_cls}">{tier_text}</span></p>\n'
        '</div>\n'
    )

# ── Brand footer helper ───────────────────────────────────────────────────────
def brand_footer(disclaimer: str = "Prices delayed up to 20 minutes.") -> str:
    return (
        '<div class="agi-footer">\n'
        '  <strong>Africa Gold Intelligence</strong> — Daily briefing for African gold investors and traders.<br>\n'
        f'  Not financial advice. {disclaimer}<br>\n'
        '  <a href="https://africagoldintelligence.beehiiv.com">africagoldintelligence.beehiiv.com</a>\n'
        '</div>\n'
    )

def pill(text):
    t = text.upper()
    if "BULL" in t or t == "BUY":   return f'<span class="pill pill-buy">{text}</span>'
    if "BEAR" in t or t == "SELL":  return f'<span class="pill pill-sell">{text}</span>'
    return f'<span class="pill pill-neutral">{text}</span>'


# ════════════════════════════════════════════════════════════════════════════
# FREE CONTENT BUILDER (shown to all subscribers)
# ════════════════════════════════════════════════════════════════════════════

def build_free_content(data: dict, post_type: str, today: datetime.datetime, africa_data: dict = None, contract_data: dict = None) -> str:
    gold  = data.get("gold", {})
    silver= data.get("silver", {})
    dxy   = data.get("dxy", {})
    g_price = gold.get("price", 0)
    g_pct   = gold.get("day_chg_pct", 0)
    g_chg   = gold.get("day_chg", 0)
    rsi     = gold.get("rsi")
    dxy_p   = dxy.get("price", 0)
    s_price = silver.get("price", 0)

    day_label = today.strftime("%A")
    date_str  = today.strftime("%B %d, %Y")
    chg_color = green_red(g_pct)
    chg_arrow = arrow(g_pct)

    # Post-type intro line
    intros = {
        "trader_intelligence": "Gold opened the week with key technical levels in play — here's what every Africa-focused trader needs to know before the New York open.",
        "africa_regional":     "Gold prices are moving across Africa's key markets today. Here's your regional currency snapshot before the full briefing.",
        "aggregator":          "Midweek gold market roundup: the top stories shaping precious metals markets across Africa and global macro.",
        "karat_pricing":       "Thursday karat pricing update: gold prices across all major Africa currencies and karat weights, updated for today's spot price.",
        "macro_outlook":       "Friday macro outlook: what the Fed, dollar, and global bond markets are signalling for gold as the week closes out.",
        "educational":         "Weekend gold education: understanding the forces that move gold prices and how African investors can position accordingly.",
        "week_review":         "Weekly gold market recap: a look back at the key price moves, data releases, and African market stories that defined this week.",
    }
    intro_text = intros.get(post_type, "Your daily Africa Gold Intelligence briefing.")


    # Inject seasonal teaser if africa_data is available
    seasonal_signals = (africa_data or {}).get("seasonal_signals", [])
    if seasonal_signals:
        sig = seasonal_signals[0]
        seasonal_teaser = f'''<p style="margin:6px 0 0;font-size:0.85rem;color:#fef3c7;">
    {sig["signal"]} — {sig["note"][:100]}…</p>'''
    else:
        seasonal_teaser = ""

    hdr = brand_header(f"Gold Market Briefing · {date_str}", day_label, POST_TYPE_LABELS.get(post_type,"Daily Briefing"), is_premium=False)
    return BASE_STYLE + hdr + f"""
<p>{intro_text}</p>

<div class="snapshot-box">
  <p class="snapshot-label">Today's Snapshot</p>
  <div class="snapshot-price">{fmt_price(g_price)}</div>
  <p style="margin:6px 0 0;font-size:1rem;color:{chg_color};font-weight:700;">
    {chg_arrow} {sign_str(g_chg, ' USD')} &nbsp;({sign_str(g_pct, '%')})
  </p>
</div>

<table class="data">
  <tr><th>Asset</th><th>Price</th><th>1D Change</th></tr>
  <tr>
    <td>XAU/USD (Gold)</td>
    <td><strong>{fmt_price(g_price)}</strong></td>
    <td class="{'up' if (g_pct or 0) >= 0 else 'down'}">{chg_arrow} {sign_str(g_pct, '%')}</td>
  </tr>
  <tr>
    <td>Silver (XAG/USD)</td>
    <td>{fmt_price(s_price)}</td>
    <td class="{'up' if (silver.get('day_chg_pct') or 0) >= 0 else 'down'}">
      {arrow(silver.get('day_chg_pct'))} {sign_str(silver.get('day_chg_pct'), '%')}
    </td>
  </tr>
  <tr>
    <td>DXY (Dollar Index)</td>
    <td>{fmt_price(dxy_p, '', 2)}</td>
    <td class="{'up' if (dxy.get('day_chg_pct') or 0) >= 0 else 'down'}">
      {arrow(dxy.get('day_chg_pct'))} {sign_str(dxy.get('day_chg_pct'), '%')}
    </td>
  </tr>
</table>

<p>📌 <strong>RSI-14:</strong> {rsi_label(rsi)} —
{'momentum is extended; watch for a pullback.' if (rsi or 50) >= 70 else
 'oversold territory; potential reversal setup.' if (rsi or 50) <= 30 else
 'momentum is balanced — direction will be set by macro data.'}</p>

<div class="cta">
  <p><strong style="color:#fbbf24;">🔐 Unlock the full briefing below</strong></p>
  <p>Premium subscribers get: full technical setup with support/resistance levels · karat pricing in ZAR, GHS, NGN, KES · Africa regional spotlight · African miner AISC margins · currency leverage analysis · Pan-African composite · curated Africa-specific headlines.</p>
  {seasonal_teaser}
</div>
"""



# ════════════════════════════════════════════════════════════════════════════
# AFRICA-SPECIFIC HTML BUILDERS (used in premium content)
# ════════════════════════════════════════════════════════════════════════════

def build_miner_dashboard_html(miners: dict, gold_price: float) -> str:
    """African miner stock dashboard with AISC margin analysis."""
    if not miners:
        return ""
    rows = ""
    for name, m in sorted(miners.items(), key=lambda x: x[1].get("margin_usd", 0), reverse=True):
        pct   = m.get("day_pct", 0)
        cls   = "up" if pct >= 0 else "down"
        arrow = "▲" if pct >= 0 else "▼"
        margin_usd = m.get("margin_usd", 0)
        margin_cls = "up" if margin_usd > 0 else "down"
        margin_pct = m.get("margin_pct", 0)
        profitable = "✅" if m.get("profitable") else "⚠️"
        rows += f"""
  <tr>
    <td><strong>{name}</strong><br>
        <small style="color:#9ca3af;">{m["ticker"]} · {m["hq"]}</small></td>
    <td>{fmt_price(m["price"])}</td>
    <td class="{cls}">{arrow} {sign_str(pct, "%")}</td>
    <td>${m["aisc"]:,}</td>
    <td class="{margin_cls}">${margin_usd:,.0f} <small>({margin_pct:.1f}%)</small></td>
    <td>{profitable}</td>
  </tr>"""

    avg_margin = sum(m.get("margin_usd", 0) for m in miners.values()) / len(miners)
    return f"""
<h3>⛏️ African Miner Dashboard — AISC Margin Analysis</h3>
<p style="font-size:0.85rem;color:#6b7280;">
  Gold spot: {fmt_price(gold_price)}/oz · AISC = All-In Sustaining Cost (latest annual report) ·
  Margin = Spot − AISC · Average miner margin: <strong>${avg_margin:,.0f}/oz</strong>
</p>
<table class="data">
  <tr>
    <th>Miner</th><th>Stock Price</th><th>1D Chg</th>
    <th>AISC/oz</th><th>Margin/oz</th><th>Profitable</th>
  </tr>
  {rows}
</table>
<p style="font-size:0.82rem;color:#6b7280;margin-top:4px;">
  💡 At ${gold_price:,.0f}/oz spot, a miner with $1,300 AISC earns ${gold_price-1300:,.0f}/oz. Every $100 move in gold spot directly impacts miner free cash flow.
</p>
"""


def build_africa_news_html(africa_news: list) -> str:
    """Africa-specific gold news section."""
    if not africa_news:
        return ""
    items = ""
    for n in africa_news:
        items += f"""
  <li style="margin-bottom:10px;">
    <span style="font-size:10px;font-weight:700;text-transform:uppercase;
                 color:#92400e;background:#fef3c7;padding:1px 6px;border-radius:3px;">
      {n["source"]}
    </span><br>
    <a href="{n["link"]}" style="color:#1d4ed8;text-decoration:none;font-size:0.93rem;
                                  font-weight:500;">{n["title"]}</a>
  </li>"""
    return f"""
<h3>🌍 Africa Gold Intelligence — Regional Headlines</h3>
<p style="font-size:0.83rem;color:#6b7280;margin-bottom:6px;">
  Sourced from Mining Weekly, Engineering News, BusinessDay NG, African Mining — news the global wires miss.
</p>
<ul style="padding-left:1.2em;margin:0;">{items}</ul>
"""


def build_currency_leverage_html(currency_leverage: dict) -> str:
    """FX leverage analysis — impact of currency moves on gold buyers and producers."""
    if not currency_leverage:
        return ""
    rows = ""
    CURRENCY_SYMBOLS = {
        "ZAR": "R", "GHS": "GH₵", "NGN": "₦",
        "KES": "KSh", "EGP": "E£", "MAD": "DH"
    }
    for cur, d in currency_leverage.items():
        sym = CURRENCY_SYMBOLS.get(cur, cur)
        role_label = {"major_producer": "🏭 Producer", "consumer": "🛒 Buyer", "mixed": "🔄 Mixed"}.get(d["role"], d["role"])
        buyer_cls  = "down" if d["buyer_impact"] == "negative" else "up"
        prod_cls   = "up"   if d["producer_impact"] == "positive" else ("down" if d["producer_impact"] == "negative" else "")
        rows += f"""
  <tr>
    <td><strong>{cur}</strong><br><small style="color:#9ca3af;">{d["country"]}</small></td>
    <td>{role_label}</td>
    <td>{sym}{d["gold_per_gram_local"]:,.0f}/g</td>
    <td class="{buyer_cls}">{"↑ Costs more" if d["buyer_impact"] == "negative" else "↓ Costs less"}</td>
    <td class="{prod_cls}">{"✅ Margin widens" if d["producer_impact"] == "positive" else ("⚠️ Margin shrinks" if d["producer_impact"] == "negative" else "—")}</td>
  </tr>"""

    return f"""
<h3>💱 Currency Leverage — What FX Moves Mean for Africa</h3>
<p style="font-size:0.83rem;color:#6b7280;">
  For every <strong>1% local currency depreciation vs USD</strong>, local gold prices rise ~1%.
  Producers earn in USD, pay costs in local currency — so currency weakness <em>benefits</em> producers but hurts buyers.
</p>
<table class="data">
  <tr><th>Currency</th><th>Role</th><th>Gold/gram</th><th>Buyer Impact</th><th>Producer Impact</th></tr>
  {rows}
</table>
"""


def build_pan_african_html(pan_african: dict) -> str:
    """Production-weighted Pan-African gold margin composite."""
    if not pan_african:
        return ""
    wm   = pan_african.get("weighted_avg_margin", 0)
    wmp  = pan_african.get("weighted_margin_pct", 0)
    best = pan_african.get("best_margin_country", "")
    bm   = pan_african.get("best_margin", 0)
    wrst = pan_african.get("worst_margin_country", "")
    wom  = pan_african.get("worst_margin", 0)

    bd   = pan_african.get("breakdown", {})
    # Show top 6 by production weight
    top6 = sorted(bd.items(), key=lambda x: x[1]["weight_pct"], reverse=True)[:6]
    rows = ""
    for country, d in top6:
        margin_cls = "up" if d["margin"] > 0 else "down"
        rows += f"""
  <tr>
    <td>{country}</td>
    <td style="color:#9ca3af;">{d["weight_pct"]}%</td>
    <td>${d["aisc"]:,}</td>
    <td class="{margin_cls}">${d["margin"]:,.0f} <small>({d["margin_pct"]}%)</small></td>
  </tr>"""

    margin_cls = "up" if wm > 0 else "down"
    return f"""
<h3>🌍 Pan-African Gold Composite — Production-Weighted Margin</h3>
<p style="font-size:0.83rem;color:#6b7280;">
  Weighted average miner margin across all African producing nations (by production share).
  This proprietary composite captures Africa's collective gold profitability in real-time.
</p>
<table class="data">
  <tr><th>Country</th><th>Production Weight</th><th>AISC</th><th>Margin at Spot</th></tr>
  {rows}
</table>
<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;
            padding:12px 16px;margin:10px 0;font-size:0.9rem;">
  <strong>📊 AGI Pan-African Composite Margin:</strong>
  <span class="{margin_cls}" style="font-size:1.1rem;"> ${wm:,.0f}/oz ({wmp:.1f}%)</span><br>
  <span style="color:#6b7280;font-size:0.82rem;">
    Best margin: <strong>{best}</strong> (${bm:,.0f}/oz) ·
    Most pressured: <strong>{wrst}</strong> (${wom:,.0f}/oz)
  </span>
</div>
"""


def build_seasonal_signals_html(seasonal_signals: list) -> str:
    """Active seasonal gold demand signals."""
    if not seasonal_signals:
        return ""
    cards = ""
    for s in seasonal_signals:
        impact_color = {"POSITIVE": "#16a34a", "NEGATIVE": "#dc2626", "MIXED": "#d97706"}.get(s["impact"], "#374151")
        impact_bg    = {"POSITIVE": "#dcfce7", "NEGATIVE": "#fee2e2", "MIXED": "#fef3c7"}.get(s["impact"], "#f3f4f6")
        affected_str = ", ".join(s.get("affected", []))
        cards += f"""
<div style="border:1px solid #e5e7eb;border-radius:8px;padding:12px 16px;margin:8px 0;">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
    <strong style="font-size:0.95rem;">{s["signal"]}</strong>
    <span style="background:{impact_bg};color:{impact_color};font-size:10px;font-weight:700;
                 padding:2px 8px;border-radius:999px;">{s["impact"]}</span>
  </div>
  <p style="margin:0 0 4px;font-size:0.88rem;color:#374151;">{s["note"]}</p>
  <p style="margin:0;font-size:0.8rem;color:#9ca3af;">Affected markets: {affected_str}</p>
</div>"""

    return f"""
<h3>📅 Active Seasonal Demand Signals</h3>
<p style="font-size:0.83rem;color:#6b7280;margin-bottom:4px;">
  Cultural and agricultural calendars that drive physical gold demand across Africa — data that global trackers miss.
</p>
{cards}
"""


def build_country_context_html(country: str, ctx: dict) -> str:
    """Deep-dive country mining context card."""
    if not ctx:
        return ""
    status_config = {
        "stable":        ("🟢 Stable",        "#16a34a", "#dcfce7"),
        "elevated_risk": ("🟡 Elevated Risk",  "#d97706", "#fef9c3"),
        "high_risk":     ("🔴 High Risk",      "#dc2626", "#fee2e2"),
    }
    sc_label, sc_color, sc_bg = status_config.get(
        ctx.get("mining_status", "stable"),
        ("⚪ Unknown", "#9ca3af", "#f3f4f6")
    )
    miners_str = " · ".join(ctx.get("key_miners", []))

    return f"""
<div style="border:1px solid #e5e7eb;border-radius:10px;padding:14px 18px;margin:12px 0;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <h3 style="margin:0 0 6px;font-size:1rem;">🏳️ {country} — Mining Sector Overview</h3>
    <span style="background:{sc_bg};color:{sc_color};font-size:10px;font-weight:700;
                 padding:2px 10px;border-radius:999px;white-space:nowrap;">{sc_label}</span>
  </div>
  <p style="margin:6px 0;font-size:0.88rem;color:#374151;"><strong>Key Note:</strong> {ctx.get("key_note", "")}</p>
  <p style="margin:4px 0;font-size:0.85rem;color:#6b7280;"><strong>Regulatory:</strong> {ctx.get("regulatory", "")}</p>
  <p style="margin:4px 0 0;font-size:0.83rem;color:#9ca3af;"><strong>Key Miners:</strong> {miners_str}</p>
</div>
"""



# ════════════════════════════════════════════════════════════════════════════
# PREMIUM CONTENT BUILDERS (one per day type)
# ════════════════════════════════════════════════════════════════════════════

def build_karat_table_html(karat_prices: dict, gold_price: float) -> str:
    rows = ""
    currencies = ["ZAR", "GHS", "NGN", "KES", "EGP", "MAD"]
    for cur in currencies:
        if cur not in karat_prices: continue
        sym  = CURRENCY_SYMBOLS.get(cur, cur)
        name = CURRENCY_NAMES.get(cur, cur)
        k    = karat_prices[cur]
        rows += f"""
  <tr>
    <td><strong>{cur}</strong><br><small style="color:#9ca3af;">{name}</small></td>
    <td>{sym}{k.get('24K',0):,.0f}</td>
    <td>{sym}{k.get('22K',0):,.0f}</td>
    <td>{sym}{k.get('18K',0):,.0f}</td>
    <td>{sym}{k.get('14K',0):,.0f}</td>
    <td>{sym}{k.get('9K',0):,.0f}</td>
  </tr>"""

    return f"""
<h3>💰 Karat Pricing Table — Africa Currencies</h3>
<p style="font-size:0.85rem;color:#6b7280;">Gold spot: {fmt_price(gold_price)} /oz · Prices are per gram · Updated at time of publication</p>
<table class="data">
  <tr><th>Currency</th><th>24K</th><th>22K</th><th>18K</th><th>14K</th><th>9K</th></tr>
  {rows}
</table>
"""


def build_headlines_html(news: list) -> str:
    if not news:
        return "<p style='color:#9ca3af;font-size:0.9rem;'>No gold-specific headlines found today.</p>"
    items = ""
    for n in news:
        items += f"""
  <li style="margin-bottom:10px;">
    <span style="font-size:10px;font-weight:700;text-transform:uppercase;color:#9ca3af;">{n['source']}</span><br>
    <a href="{n['link']}" style="color:#1d4ed8;text-decoration:none;font-size:0.95rem;">{n['title']}</a>
  </li>"""
    return f"<h3>📰 Curated Headlines</h3><ul style='padding-left:1.2em;margin:0;'>{items}</ul>"


def build_watchlist_html(today: datetime.datetime) -> str:
    # Generate Mon–Fri events based on current week
    mon = today - datetime.timedelta(days=today.weekday())
    events = [
        (mon + datetime.timedelta(days=0), "Chicago Fed National Activity Index"),
        (mon + datetime.timedelta(days=1), "CB Consumer Confidence · Richmond Fed Mfg"),
        (mon + datetime.timedelta(days=2), "FOMC Meeting Minutes · EIA Crude Inventories"),
        (mon + datetime.timedelta(days=3), "US GDP (Advance) · SA PPI Data"),
        (mon + datetime.timedelta(days=4), "US Core PCE Inflation · Chicago PMI"),
    ]
    rows = ""
    for dt, label in events:
        day_str = dt.strftime("%a %b %d")
        is_today = dt.date() == today.date()
        style = "font-weight:700;background:#fffbeb;" if is_today else ""
        rows += f"<tr style='{style}'><td>{day_str}</td><td>{label}</td></tr>"

    return f"""
<h3>📅 This Week's Macro Watch List</h3>
<table class="data">
  <tr><th>Date</th><th>Event</th></tr>
  {rows}
</table>
<p style="font-size:0.8rem;color:#9ca3af;">Bold row = today. All times approximate. Data drives gold volatility — watch especially PCE and FOMC releases.</p>
"""


# ── Contract Transparency Builders ────────────────────────────────────────────

def build_mining_contracts_html(contract_data: dict, gold_price: float) -> str:
    """Mining contract royalty analysis — who pays what, and what Africa is owed."""
    if not contract_data:
        return ""
    royalty_analysis = contract_data.get("royalty_analysis", [])
    if not royalty_analysis:
        return ""

    total_paid    = contract_data.get("total_royalties_paid", 0)
    total_gap     = contract_data.get("total_gap_usd", 0)
    benchmark_pct = contract_data.get("fair_royalty_benchmark", 8.0)

    rows = ""
    for r in royalty_analysis[:8]:   # top 8 by revenue gap
        status_config = {
            "stable":       ("✅ Stable",       "#16a34a", "#dcfce7"),
            "renegotiated": ("🔄 Renegotiated", "#d97706", "#fef9c3"),
            "resolved":     ("🤝 Resolved",     "#2563eb", "#dbeafe"),
            "nationalised": ("🏛️ Nationalised", "#7c3aed", "#ede9fe"),
            "watching":     ("👁 Watching",     "#9ca3af", "#f3f4f6"),
        }
        s_label, s_color, s_bg = status_config.get(r["contract_status"],
            ("❓ Unknown", "#9ca3af", "#f3f4f6"))

        if r["contract_status"] == "nationalised":
            royalty_str = "100% state"
            gap_str     = "—"
        else:
            royalty_str = f"{r['royalty_pct']}%"
            gap_str     = f"${r['revenue_gap_usd']/1e6:.0f}M/yr"

        rows += f"""
  <tr>
    <td>
      <strong>{r['company']}</strong>
      <small style="color:#9ca3af;display:block;">{r['hq_country']} · {r['ticker']}</small>
    </td>
    <td>{r['host_country']}<br><small style="color:#9ca3af;">{r['mine']}</small></td>
    <td style="text-align:right;">{r['annual_oz']:,}</td>
    <td style="text-align:right;font-weight:700;">{royalty_str}</td>
    <td style="text-align:right;color:#6b7280;">{benchmark_pct}%</td>
    <td style="text-align:right;" class="{'down' if r['revenue_gap_usd'] > 0 else ''}">{gap_str}</td>
    <td><span style="background:{s_bg};color:{s_color};font-size:9px;font-weight:700;
                     padding:2px 6px;border-radius:999px;white-space:nowrap;">{s_label}</span></td>
  </tr>"""

    return f"""
<h3>📋 Mining Contract Transparency — Who Pays What to Africa</h3>
<p style="font-size:0.83rem;color:#6b7280;margin-bottom:6px;">
  At today's spot price of {fmt_price(gold_price)}/oz, Africa's tracked mines generate
  <strong>${(total_paid + total_gap)/1e6:.0f}M/yr</strong> in gross royalty-equivalent revenue.
  African governments receive <strong>${total_paid/1e6:.0f}M/yr</strong> at contracted rates.
  At the NRGI fair-value benchmark of {benchmark_pct}%, they <em>should</em> receive
  <strong>${(total_paid + total_gap)/1e6:.0f}M/yr</strong> —
  a gap of <strong class="down">${total_gap/1e6:.0f}M/yr</strong>.
</p>
<table class="data" style="font-size:0.82rem;">
  <tr>
    <th>Company</th><th>Country / Mine</th><th style="text-align:right;">oz/yr</th>
    <th style="text-align:right;">Royalty</th><th style="text-align:right;">Fair Rate</th>
    <th style="text-align:right;">Annual Gap</th><th>Status</th>
  </tr>
  {rows}
</table>
<p style="font-size:0.78rem;color:#9ca3af;margin-top:4px;">
  Source: ResourceContracts.org · Company annual reports · EITI disclosures · Q1 2026 update.
  "Gap" = additional royalty revenue the host country would receive at the 8% NRGI benchmark.
  State equity distributions provide additional government income not reflected in royalty line.
</p>
"""


def build_shadow_economy_html(shadow_data: dict, gold_price: float) -> str:
    """Informal sector leakage and Dubai gap analysis."""
    if not shadow_data:
        return ""

    illicit_t   = shadow_data.get("illicit_mid_tonnes", 397)
    illicit_bn  = shadow_data.get("illicit_mid_usd_bn", 29)
    coeff       = shadow_data.get("shadow_coefficient", 0.38)
    dg          = shadow_data.get("dubai_gap", {})
    fl          = shadow_data.get("financial_losses", {})

    country_rows = ""
    for d in shadow_data.get("country_data", []):
        pct_cls = "down" if d["shadow_pct"] > 50 else ("" if d["shadow_pct"] < 30 else "")
        country_rows += f"""
  <tr>
    <td><strong>{d['country']}</strong></td>
    <td style="text-align:right;">{d['formal_tonnes']}t</td>
    <td style="text-align:right;">{d['estimated_total']}t</td>
    <td style="text-align:right;" class="{'down' if d['shadow_pct'] > 40 else ''}">{d['shadow_pct']}%</td>
    <td style="text-align:right;" class="down">{d['gap_tonnes']}t / ${d['gap_usd']}B</td>
    <td style="font-size:0.78rem;color:#6b7280;">{d['asm_miners']} miners</td>
  </tr>"""

    return f"""
<h3>👤 Africa's Shadow Gold Economy — The ${illicit_bn:.0f} Billion Blind Spot</h3>
<div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;
            padding:12px 16px;margin:8px 0;">
  <p style="margin:0;font-size:0.9rem;color:#991b1b;">
    <strong>~{illicit_t} tonnes of African gold leave the continent undeclared every year —
    worth approximately ${illicit_bn}B at today's prices.</strong>
    That's {round(coeff*100):.0f}% of Africa's formal production flowing
    through shadow channels with zero royalty, zero tax, zero benefit to host nations.
  </p>
</div>

<table class="data" style="font-size:0.82rem;">
  <tr>
    <th>Country</th><th style="text-align:right;">Official</th>
    <th style="text-align:right;">Estimated Actual</th>
    <th style="text-align:right;">Informal %</th>
    <th style="text-align:right;">Lost Annually</th>
    <th>ASM Workforce</th>
  </tr>
  {country_rows}
</table>

<div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:8px;
            padding:12px 16px;margin:10px 0;">
  <p style="margin:0 0 6px;font-weight:700;font-size:0.9rem;color:#9a3412;">
    🇦🇪 The Dubai Gap — Hard Evidence of Underdeclaration
  </p>
  <p style="margin:0 0 4px;font-size:0.85rem;color:#374151;">
    Between {dg.get('period','2012–2022')}, the UAE imported
    <strong>{dg.get('undeclared_tonnes','2,569'):,} tonnes</strong> of African gold
    that was <em>never declared as an export</em> by the source African countries —
    valued at <strong>{dg.get('undeclared_value_usd','$115.3 billion')}</strong>.
  </p>
  <p style="margin:0 0 4px;font-size:0.85rem;color:#374151;">
    In 2024 alone, the UAE imported <strong>{dg.get('latest_uae_africa_tonnes',748)} tonnes</strong>
    from Africa — up <strong>{dg.get('latest_yoy_pct',18)}% year-on-year</strong>.
    The UAE ({dg.get('uae_share_of_smuggled',47)}%), Switzerland ({dg.get('swiss_share',21)}%),
    and India ({dg.get('india_share',12)}%) are the three primary destinations for
    undeclared African gold.
  </p>
  <p style="margin:0;font-size:0.78rem;color:#9ca3af;">
    Source: {dg.get('source','Swissaid 2024')} ·
    Ghana alone: 229t / ${shadow_data.get('dubai_gap',{}).get('ghana_5yr_gap_usd_bn',11.4)}B undeclared over 5 years
  </p>
</div>

<p style="font-size:0.78rem;color:#9ca3af;">
  Annual losses to trade misinvoicing across African mining:
  ${fl.get('gfi_africa_annual_bn',52)}B (GFI est.) ·
  Ghana (2013–2022): ${fl.get('ghana_decade_loss_bn',54.1)}B ·
  South Africa: ${fl.get('sa_annual_loss_bn',7.4)}B/yr
</p>
"""


def build_resource_nationalism_html(nationalism_alerts: list) -> str:
    """Resource nationalism tracker — government moves on mine ownership and contracts."""
    if not nationalism_alerts:
        return ""

    status_config = {
        "nationalised":   ("🏛️ Nationalised",   "#7c3aed", "#ede9fe", 0),
        "renegotiated":   ("🔄 Renegotiated",   "#d97706", "#fef9c3", 1),
        "renegotiating":  ("⚡ Renegotiating",  "#dc2626", "#fee2e2", 2),
        "watching":       ("👁 Watching",        "#2563eb", "#dbeafe", 3),
        "stable":         ("✅ Stable",          "#16a34a", "#dcfce7", 4),
    }
    risk_config = {
        "completed":  ("—",       "#9ca3af"),
        "high":       ("🔴 HIGH", "#dc2626"),
        "elevated":   ("🟡 MED",  "#d97706"),
        "moderate":   ("🟠 MOD",  "#f59e0b"),
        "low":        ("🟢 LOW",  "#16a34a"),
    }

    cards = ""
    for n in nationalism_alerts[:6]:
        s_label, s_color, s_bg, _ = status_config.get(
            n["status"], ("❓ Unknown", "#9ca3af", "#f3f4f6", 9))
        r_label, r_color = risk_config.get(n["risk_level"], ("?", "#9ca3af"))
        affected = ", ".join(n.get("affected_cos", []))
        template = n.get("template_for", [])
        template_str = f" · <em>Template for: {', '.join(template)}</em>" if template else ""

        cards += f"""
<div style="border:1px solid #e5e7eb;border-radius:8px;padding:12px 16px;margin:8px 0;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;flex-wrap:wrap;gap:4px;">
    <strong style="font-size:0.95rem;">🏳️ {n['country']}</strong>
    <div style="display:flex;gap:6px;">
      <span style="background:{s_bg};color:{s_color};font-size:9px;font-weight:700;
                   padding:2px 8px;border-radius:999px;">{s_label}</span>
      <span style="color:{r_color};font-size:9px;font-weight:700;
                   padding:2px 8px;border-radius:999px;background:#f9fafb;">{r_label}</span>
    </div>
  </div>
  <p style="margin:0 0 4px;font-size:0.85rem;color:#374151;">{n.get('key_action','')}</p>
  {f'<p style="margin:2px 0;font-size:0.8rem;color:#6b7280;"><strong>Affected:</strong> {affected}</p>' if affected else ''}
  <p style="margin:4px 0 0;font-size:0.8rem;color:#374151;font-style:italic;">
    {n.get('investor_signal','')}{template_str}
  </p>
</div>"""

    return f"""
<h3>🏛️ Resource Nationalism Tracker — Who's Taking Back Control</h3>
<p style="font-size:0.83rem;color:#6b7280;margin-bottom:6px;">
  A wave of African governments are renegotiating or nationalising mining contracts —
  driven by the calculation that current royalty rates capture only a fraction of fair value.
  Burkina Faso is the live case study; Mali, Niger, and Ghana are watching closely.
</p>
{cards}
"""


def build_contract_news_html(contract_news: list) -> str:
    """Contract and policy-change news from Africa-focused feeds."""
    if not contract_news:
        return ""
    items = ""
    for n in contract_news:
        items += f"""
  <li style="margin-bottom:10px;">
    <span style="font-size:10px;font-weight:700;text-transform:uppercase;
                 color:#7c3aed;background:#ede9fe;padding:1px 6px;border-radius:3px;">
      {n["source"]}
    </span><br>
    <a href="{n["link"]}" style="color:#1d4ed8;text-decoration:none;
                                  font-size:0.93rem;font-weight:500;">{n["title"]}</a>
  </li>"""
    return f"""
<h3>⚖️ Contract & Policy Intelligence — Latest Developments</h3>
<p style="font-size:0.83rem;color:#6b7280;margin-bottom:6px;">
  Mining law changes, nationalizations, and contract renegotiations — the stories that
  shape African gold supply but rarely make the global wires.
</p>
<ul style="padding-left:1.2em;margin:0;">{items}</ul>
"""


# ─── Monday: Trader Intelligence ───────────────────────────────────────────

def build_premium_trader_intelligence(data: dict, today: datetime.datetime, africa_data: dict = None, contract_data: dict = None) -> str:
    gold   = data.get("gold", {})
    silver = data.get("silver", {})
    dxy    = data.get("dxy", {})
    sp500  = data.get("sp500", {})
    karat  = data.get("karat_prices", {})
    news   = data.get("news", [])

    g_price = gold.get("price", 0)
    g_pct   = gold.get("day_chg_pct", 0)
    rsi     = gold.get("rsi")
    levels  = support_resistance(g_price)
    b       = bias_str(rsi, g_pct)
    week_chg= sign_str(gold.get("week_chg_pct"), "%")

    return BASE_STYLE + f"""
{brand_header("Gold Trader Intelligence Briefing", today.strftime("%B %d, %Y"), "Monday Edition", is_premium=True)}

<h3>📊 Trader View — XAU/USD Technical Setup</h3>
<table class="data">
  <tr><td><strong>Spot Price</strong></td><td>{fmt_price(g_price)}</td></tr>
  <tr><td><strong>Daily Change</strong></td>
      <td class="{'up' if (g_pct or 0)>=0 else 'down'}">{arrow(g_pct)} {sign_str(g_pct,'%')}</td></tr>
  <tr><td><strong>Weekly Change</strong></td><td>{week_chg}</td></tr>
  <tr><td><strong>RSI-14</strong></td><td>{rsi_label(rsi)}</td></tr>
  <tr><td><strong>Bias</strong></td><td>{pill(b)}</td></tr>
</table>

<p><strong>Key Levels:</strong></p>
<table class="data">
  <tr><th>Level</th><th>Price</th><th>Significance</th></tr>
  <tr><td>Resistance 2</td><td class="up">{fmt_price(levels['r2'])}</td><td>+2.5% extension — major supply zone</td></tr>
  <tr><td>Resistance 1</td><td class="up">{fmt_price(levels['r1'])}</td><td>Near-term intraday ceiling</td></tr>
  <tr><td><strong>Spot</strong></td><td><strong>{fmt_price(g_price)}</strong></td><td>Current price</td></tr>
  <tr><td>Support 1</td><td class="down">{fmt_price(levels['s1'])}</td><td>First demand zone — watch for bounce</td></tr>
  <tr><td>Support 2</td><td class="down">{fmt_price(levels['s2'])}</td><td>Strong support — weekly low area</td></tr>
</table>

<p><strong>Context:</strong> Dollar Index at {fmt_price(dxy.get('price'), '', 2)}
({sign_str(dxy.get('day_chg_pct'),'%')} today) —
{'a weaker dollar is supportive of gold price gains.' if (dxy.get('day_chg_pct') or 0) < 0 else 'dollar strength is creating near-term headwinds for gold.'}
S&amp;P 500 at {fmt_price(sp500.get('price'),'',0)} ({sign_str(sp500.get('day_chg_pct'),'%')} today).</p>

{build_karat_table_html(karat, g_price)}
{build_headlines_html(news)}
{build_miner_dashboard_html((africa_data or {}).get("miners", {}), g_price)}
{build_africa_news_html((africa_data or {}).get("africa_news", []))}
{build_seasonal_signals_html((africa_data or {}).get("seasonal_signals", []))}
{build_watchlist_html(today)}

{brand_footer("Prices delayed up to 20 minutes.")}
"""


# ─── Tuesday: Africa Regional ──────────────────────────────────────────────

def build_premium_africa_regional(data: dict, today: datetime.datetime, africa_data: dict = None, contract_data: dict = None) -> str:
    gold   = data.get("gold", {})
    karat  = data.get("karat_prices", {})
    fx     = data.get("fx_rates", {})
    news   = data.get("news", [])
    g_price = gold.get("price", 0)

    # Pick spotlight country based on day of month
    spotlight = REGIONAL_ROTATION[(today.day - 1) % len(REGIONAL_ROTATION)]

    # Map country to currency
    country_cur = {
        "South Africa": "ZAR", "Ghana": "GHS", "Nigeria": "NGN",
        "Kenya": "KES", "Egypt": "EGP", "Morocco": "MAD",
        "Ethiopia": "ETB", "Tanzania": "TZS", "Uganda": "UGX", "Zimbabwe": "ZWL"
    }
    cur = country_cur.get(spotlight, "ZAR")
    sym = CURRENCY_SYMBOLS.get(cur, cur)
    fx_rate = fx.get(cur, "N/A")
    karat_24 = karat.get(cur, {}).get("24K", 0)
    karat_18 = karat.get(cur, {}).get("18K", 0)
    karat_22 = karat.get(cur, {}).get("22K", 0)

    return BASE_STYLE + f"""
{brand_header("Africa Regional Gold Report", today.strftime("%B %d, %Y"), "Tuesday Edition", is_premium=True)}

<h3>🌍 Regional Spotlight — {spotlight}</h3>

<p><strong>Gold in {cur}:</strong> At today's spot price of {fmt_price(g_price)},
one troy ounce of gold costs <strong>{sym}{g_price * (fx_rate if isinstance(fx_rate,float) else 1):,.0f}</strong> in {spotlight}.</p>

<table class="data">
  <tr><th>Metric</th><th>Value</th></tr>
  <tr><td>USD/{cur} Exchange Rate</td><td>{fx_rate if isinstance(fx_rate, float) else 'N/A':.2f} if isinstance(fx_rate, float) else {fx_rate}</td></tr>
  <tr><td>Gold per gram (24K)</td><td>{sym}{karat_24:,.0f}</td></tr>
  <tr><td>Gold per gram (22K)</td><td>{sym}{karat_22:,.0f}</td></tr>
  <tr><td>Gold per gram (18K)</td><td>{sym}{karat_18:,.0f}</td></tr>
</table>

<p>A weaker local currency amplifies gold price moves for buyers in {spotlight} — even when gold is flat in USD, a 1% move in the exchange rate directly impacts local gold costs. This is why African gold buyers often face higher volatility than the USD spot price suggests.</p>

{build_karat_table_html(karat, g_price)}
{build_headlines_html(news)}
{build_africa_news_html((africa_data or {}).get("africa_news", []))}
{build_currency_leverage_html((africa_data or {}).get("currency_leverage", {}))}
{build_pan_african_html((africa_data or {}).get("pan_african", {}))}
{build_seasonal_signals_html((africa_data or {}).get("seasonal_signals", []))}
{build_country_context_html(spotlight, (africa_data or {}).get("country_context", {}).get(spotlight, {}))}
{build_mining_contracts_html(contract_data or {}, g_price)}
{build_shadow_economy_html((contract_data or {}).get("shadow_data", {}), g_price)}
{build_resource_nationalism_html((contract_data or {}).get("nationalism_alerts", []))}
{build_contract_news_html((contract_data or {}).get("contract_news", []))}
{build_watchlist_html(today)}

{brand_footer("Exchange rates indicative only.")}
"""


# ─── Wednesday: Aggregator ─────────────────────────────────────────────────

def build_premium_aggregator(data: dict, today: datetime.datetime, africa_data: dict = None, contract_data: dict = None) -> str:
    gold  = data.get("gold", {})
    karat = data.get("karat_prices", {})
    news  = data.get("news", [])
    g_price = gold.get("price", 0)

    return BASE_STYLE + f"""
{brand_header("Midweek Gold Intelligence Digest", today.strftime("%B %d, %Y"), "Wednesday Edition", is_premium=True)}

<h3>📡 Market Pulse</h3>
<p>Gold is currently trading at {fmt_price(g_price)} —
{sign_str(gold.get('day_chg_pct'),'%')} on the day.
Weekly momentum: {sign_str(gold.get('week_chg_pct'),'%')}.
RSI-14 reads {rsi_label(gold.get('rsi'))}, suggesting
{'the rally may be overextended.' if (gold.get('rsi') or 50) >= 65 else
 'there is still room to the upside.' if (gold.get('rsi') or 50) <= 45 else
 'a balanced, range-bound near-term setup.'}
</p>

{build_headlines_html(news)}
{build_africa_news_html((africa_data or {}).get("africa_news", []))}
{build_miner_dashboard_html((africa_data or {}).get("miners", {}), g_price)}
{build_pan_african_html((africa_data or {}).get("pan_african", {}))}
{build_karat_table_html(karat, g_price)}
{build_seasonal_signals_html((africa_data or {}).get("seasonal_signals", []))}
{build_resource_nationalism_html((contract_data or {}).get("nationalism_alerts", []))}
{build_contract_news_html((contract_data or {}).get("contract_news", []))}
{build_watchlist_html(today)}

{brand_footer()}
"""


# ─── Thursday: Karat Pricing ───────────────────────────────────────────────

def build_premium_karat_pricing(data: dict, today: datetime.datetime, africa_data: dict = None, contract_data: dict = None) -> str:
    gold  = data.get("gold", {})
    karat = data.get("karat_prices", {})
    news  = data.get("news", [])
    g_price = gold.get("price", 0)
    g_gram  = g_price / TROY_OZ_TO_GRAM

    return BASE_STYLE + f"""
{brand_header("Karat Pricing Update", today.strftime("%B %d, %Y"), "Thursday Edition", is_premium=True)}

<p>Gold spot is <strong>{fmt_price(g_price)}/oz</strong> ({fmt_price(g_gram)}/gram in USD).
Below is the full karat pricing table across all major Africa markets, updated at time of publication.</p>

{build_karat_table_html(karat, g_price)}

<h3>📐 How to Read This Table</h3>
<p>Each row shows a local currency. Each column shows a karat purity level.
<strong>24K = pure gold.</strong> 22K (95.8% pure) is the most common jewelry standard in West Africa.
18K (75% pure) is typical for fine jewelry in East and Southern Africa.
9K is popular for affordable pieces in the UK/Commonwealth markets.</p>

<p>If the local currency weakens against the USD (e.g. NGN depreciates), the local gold price rises —
even if international spot gold stays flat. This is why tracking FX alongside gold is essential for African buyers and jewellers.</p>

{build_headlines_html(news)}
{build_africa_news_html((africa_data or {}).get("africa_news", []))}
{build_currency_leverage_html((africa_data or {}).get("currency_leverage", {}))}
{build_seasonal_signals_html((africa_data or {}).get("seasonal_signals", []))}
{build_watchlist_html(today)}

{brand_footer("Prices indicative only.")}
"""


# ─── Friday: Macro Outlook ─────────────────────────────────────────────────

def build_premium_macro_outlook(data: dict, today: datetime.datetime, africa_data: dict = None, contract_data: dict = None) -> str:
    gold  = data.get("gold", {})
    dxy   = data.get("dxy", {})
    sp500 = data.get("sp500", {})
    karat = data.get("karat_prices", {})
    news  = data.get("news", [])
    g_price = gold.get("price", 0)

    dxy_dir = "weakening" if (dxy.get("day_chg_pct") or 0) < 0 else "strengthening"
    sp_dir  = "risk-on" if (sp500.get("day_chg_pct") or 0) > 0 else "risk-off"

    return BASE_STYLE + f"""
{brand_header("Friday Macro Outlook", today.strftime("%B %d, %Y"), "Friday Edition", is_premium=True)}

<h3>🌐 Macro Environment for Gold</h3>
<table class="data">
  <tr><th>Driver</th><th>Current</th><th>Implication for Gold</th></tr>
  <tr>
    <td>US Dollar (DXY)</td>
    <td class="{'down' if (dxy.get('day_chg_pct') or 0)<0 else 'up'}">{fmt_price(dxy.get('price'),'',2)} ({sign_str(dxy.get('day_chg_pct'),'%')})</td>
    <td>{'Bullish ✅ — weaker dollar lifts gold' if (dxy.get('day_chg_pct') or 0)<0 else 'Bearish ⚠️ — dollar strength pressures gold'}</td>
  </tr>
  <tr>
    <td>S&amp;P 500</td>
    <td class="{'up' if (sp500.get('day_chg_pct') or 0)>=0 else 'down'}">{fmt_price(sp500.get('price'),'',0)} ({sign_str(sp500.get('day_chg_pct'),'%')})</td>
    <td>{'Risk-on: equities up — gold may see mild pressure' if (sp500.get('day_chg_pct') or 0)>=0 else 'Risk-off: equities weak — safe-haven demand supports gold'}</td>
  </tr>
  <tr>
    <td>Gold RSI-14</td>
    <td>{rsi_label(gold.get('rsi'))}</td>
    <td>{'Overbought — potential pullback next week' if (gold.get('rsi') or 50)>=70 else 'Oversold — potential reversal higher' if (gold.get('rsi') or 50)<=30 else 'Balanced — follow macro data next week'}</td>
  </tr>
</table>

<p>Going into the weekend, gold is {fmt_price(g_price)} with a
{sign_str(gold.get('week_chg_pct'),'%')} weekly change.
The dollar is {dxy_dir} this session, and equities are signalling {sp_dir} sentiment.
Next week's key catalysts: watch PCE inflation data (Friday), FOMC minutes, and any Fed speaker commentary for direction signals.</p>

{build_karat_table_html(karat, g_price)}
{build_headlines_html(news)}
{build_africa_news_html((africa_data or {}).get("africa_news", []))}
{build_miner_dashboard_html((africa_data or {}).get("miners", {}), g_price)}
{build_pan_african_html((africa_data or {}).get("pan_african", {}))}
{build_seasonal_signals_html((africa_data or {}).get("seasonal_signals", []))}

{brand_footer("Have a great weekend.")}
"""


# ─── Saturday: Educational ─────────────────────────────────────────────────

def build_premium_educational(data: dict, today: datetime.datetime, africa_data: dict = None, contract_data: dict = None) -> str:
    gold    = data.get("gold", {})
    karat   = data.get("karat_prices", {})
    g_price = gold.get("price", 0)

    # Rotate educational topics by week number
    week_num = today.isocalendar()[1]
    topics = [
        ("What Moves Gold Prices?", """
<p>Gold prices are influenced by several key forces that every Africa investor should understand:</p>
<ul>
  <li><strong>US Dollar (DXY):</strong> Gold has a strong inverse correlation with the dollar. When DXY falls, gold typically rises, and vice versa. This is because gold is priced in USD — a weaker dollar makes gold cheaper for foreign buyers, increasing demand.</li>
  <li><strong>Real Interest Rates:</strong> When real yields (nominal rates minus inflation) fall, the opportunity cost of holding gold drops, boosting gold's appeal. Fed rate cut expectations are a major gold driver.</li>
  <li><strong>Safe Haven Demand:</strong> In times of geopolitical tension, economic uncertainty, or banking stress, investors flee to gold as a store of value.</li>
  <li><strong>Central Bank Buying:</strong> Emerging market central banks (including several in Africa) have been significant net buyers of gold since 2022, providing structural demand support.</li>
  <li><strong>Inflation Expectations:</strong> Gold is widely seen as an inflation hedge. When CPI trends higher, gold tends to attract more institutional interest.</li>
</ul>
<p>For African investors, there is an additional layer: local currency depreciation. If your local currency weakens by 10%, your gold holdings (valued in USD) effectively gain 10% in local terms — making gold a powerful hedge against currency risk.</p>
"""),
        ("Understanding Gold Karats", f"""
<p>Gold purity is measured in <strong>karats</strong> (not to be confused with carats, a diamond weight). Pure gold is <strong>24 karat (24K)</strong>.</p>
<table class="data">
  <tr><th>Karat</th><th>Purity</th><th>Common Use</th></tr>
  <tr><td>24K</td><td>99.9% gold</td><td>Investment bars &amp; coins, reserves</td></tr>
  <tr><td>22K</td><td>91.7% gold</td><td>West African jewellery standard</td></tr>
  <tr><td>18K</td><td>75% gold</td><td>Fine jewellery (East/Southern Africa)</td></tr>
  <tr><td>14K</td><td>58.3% gold</td><td>Mid-range jewellery, more durable</td></tr>
  <tr><td>9K</td><td>37.5% gold</td><td>Affordable jewellery, UK/Commonwealth</td></tr>
</table>
<p>The remaining metal is typically silver, copper, or palladium — which also determines the colour (yellow, white, or rose gold).</p>
<p>At today's spot price of <strong>{fmt_price(g_price)}/oz</strong>, a gram of 24K gold costs {fmt_price(g_price / TROY_OZ_TO_GRAM)},
while 18K costs {fmt_price((g_price / TROY_OZ_TO_GRAM) * 0.75)}.
This is why the karat stamp on jewellery matters — it tells you the actual gold content you're paying for.</p>
"""),
        ("How Africa's Gold Mines Work", """
<p>Africa accounts for roughly <strong>20–25% of global gold production</strong>, with South Africa, Ghana, Mali, Burkina Faso, and Tanzania among the top producers.</p>
<p>Key facts for investors:</p>
<ul>
  <li><strong>South Africa</strong> was historically the world's largest gold producer but has declined due to aging deep mines and rising costs. The Witwatersrand Basin remains one of the richest gold-bearing regions on Earth.</li>
  <li><strong>Ghana (Ashanti Region)</strong> is now Africa's largest gold producer. AngloGold, Gold Fields, and Kinross all operate major mines here.</li>
  <li><strong>Mali &amp; Burkina Faso</strong> have significant production but face political instability risks that create supply uncertainty — and price spikes when major mines are disrupted.</li>
  <li><strong>Artisanal &amp; Small-Scale Mining (ASM)</strong> contributes 15–20% of Africa's gold output and employs millions, but faces challenges around formalisation and environmental standards.</li>
</ul>
<p>Mine supply disruptions in Africa can tighten global gold supply and push prices higher — something global traders don't always factor in, but Africa-focused investors should watch closely.</p>
"""),
    ]
    topic_title, topic_body = topics[week_num % len(topics)]

    return BASE_STYLE + f"""
{brand_header("Weekend Gold Education Series", today.strftime("%B %d, %Y"), "Saturday Edition", is_premium=True)}

<h3>📚 {topic_title}</h3>
{topic_body}

{build_karat_table_html(karat, g_price)}
{build_miner_dashboard_html((africa_data or {}).get("miners", {}), g_price)}
{build_africa_news_html((africa_data or {}).get("africa_news", []))}
{build_seasonal_signals_html((africa_data or {}).get("seasonal_signals", []))}

{brand_footer("Educational content only. Not financial advice.")}
"""


# ─── Sunday: Week Review ───────────────────────────────────────────────────

def build_premium_week_review(data: dict, today: datetime.datetime, africa_data: dict = None, contract_data: dict = None) -> str:
    gold  = data.get("gold", {})
    karat = data.get("karat_prices", {})
    news  = data.get("news", [])
    g_price = gold.get("price", 0)
    week_chg = gold.get("week_chg_pct", 0)

    week_start = today - datetime.timedelta(days=6)
    implied_open = g_price / (1 + (week_chg or 0) / 100)

    return BASE_STYLE + f"""
{brand_header("Weekly Gold Market Review", today.strftime("%B %d, %Y"), "Sunday Edition", is_premium=True)}

<h3>📈 Week in Review ({week_start.strftime('%b %d')} – {today.strftime('%b %d, %Y')})</h3>
<table class="data">
  <tr><td><strong>Week Open (est.)</strong></td><td>{fmt_price(implied_open)}</td></tr>
  <tr><td><strong>Week Close</strong></td><td>{fmt_price(g_price)}</td></tr>
  <tr><td><strong>Weekly Change</strong></td>
      <td class="{'up' if (week_chg or 0)>=0 else 'down'}">{arrow(week_chg)} {sign_str(week_chg,'%')}</td></tr>
  <tr><td><strong>RSI-14 (End of Week)</strong></td><td>{rsi_label(gold.get('rsi'))}</td></tr>
  <tr><td><strong>Weekly Bias</strong></td><td>{pill(bias_str(gold.get('rsi'), gold.get('day_chg_pct')))}</td></tr>
</table>

<p>Gold {'gained' if (week_chg or 0) >= 0 else 'lost'} {abs(week_chg or 0):.1f}% this week, closing at {fmt_price(g_price)}.
{'The bullish momentum suggests continued institutional interest and potential for new highs if macro conditions remain supportive.' if (week_chg or 0) >= 0 else 'Selling pressure this week reflected risk-on positioning and a stronger dollar; watch for consolidation before the next directional move.'}</p>

{build_headlines_html(news)}
{build_africa_news_html((africa_data or {}).get("africa_news", []))}
{build_karat_table_html(karat, g_price)}
{build_miner_dashboard_html((africa_data or {}).get("miners", {}), g_price)}
{build_currency_leverage_html((africa_data or {}).get("currency_leverage", {}))}
{build_pan_african_html((africa_data or {}).get("pan_african", {}))}
{build_seasonal_signals_html((africa_data or {}).get("seasonal_signals", []))}
{build_shadow_economy_html((contract_data or {}).get("shadow_data", {}), g_price)}
{build_resource_nationalism_html((contract_data or {}).get("nationalism_alerts", []))}

<h3>🔮 Looking Ahead</h3>
<p>Key data releases next week to watch: Core PCE inflation, FOMC minutes, US consumer confidence, and any central bank announcements from African nations.
A surprise in any of these could trigger significant moves in gold.</p>

{brand_footer("See you Monday.")}
"""


# ════════════════════════════════════════════════════════════════════════════
# CONTENT ROUTER
# ════════════════════════════════════════════════════════════════════════════

def build_premium_content(post_type: str, data: dict, today: datetime.datetime, africa_data: dict = None, contract_data: dict = None) -> str:
    builders = {
        "trader_intelligence": build_premium_trader_intelligence,
        "africa_regional":     build_premium_africa_regional,
        "aggregator":          build_premium_aggregator,
        "karat_pricing":       build_premium_karat_pricing,
        "macro_outlook":       build_premium_macro_outlook,
        "educational":         build_premium_educational,
        "week_review":         build_premium_week_review,
    }
    fn = builders.get(post_type, build_premium_aggregator)
    return fn(data, today, africa_data, contract_data)


POST_TYPE_LABELS = {
    "trader_intelligence": "Trader Intelligence Briefing",
    "africa_regional":     "Africa Regional Report",
    "aggregator":          "Midweek Gold Digest",
    "karat_pricing":       "Karat Pricing Update",
    "macro_outlook":       "Friday Macro Outlook",
    "educational":         "Weekend Gold Education",
    "week_review":         "Weekly Market Review",
}


# ════════════════════════════════════════════════════════════════════════════
# BEEHIIV API
# ════════════════════════════════════════════════════════════════════════════

def beehiiv_create_post(title: str, subtitle: str, email_subject: str,
                         preview_text: str, free_html: str, premium_html: str,
                         publish_type: str = "instant",
                         slug: str = None,
                         content_tags: list = None) -> dict:
    """
    Create a post via Beehiiv V2 API.
    Returns the API response dict (or raises on error).
    Docs: https://developers.beehiiv.com/docs/v2/posts-create
    """
    if not BEEHIIV_API_KEY:
        raise ValueError("BEEHIIV_API_KEY environment variable is not set.\n"
                         "  export BEEHIIV_API_KEY='your_key_here'")

    payload = {
        "title":               title,
        "subtitle":            subtitle,
        "email_subject_line":  email_subject,
        "preview_text":        preview_text,
        "free_web_content":    free_html,
        "free_email_content":  free_html,
        "premium_web_content": premium_html,
        "premium_email_content": premium_html,
        "audience":            "all",      # visible to all; paywall controls access
        "publish_type":        publish_type,
        "content_tags":        content_tags if content_tags else ["gold", "africa", "markets"],
    }

    if slug:
        payload["slug"] = slug

    import requests
    headers = {
        "Authorization": f"Bearer {BEEHIIV_API_KEY}",
        "Content-Type":  "application/json",
    }

    resp = requests.post(BEEHIIV_API_URL, headers=headers,
                         data=json.dumps(payload), timeout=30)

    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Beehiiv API error {resp.status_code}: {resp.text[:500]}")

    return resp.json()


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def main():
    today     = datetime.datetime.now()
    weekday   = today.weekday()           # 0=Mon … 6=Sun
    post_type = DAY_TYPES.get(weekday, "aggregator")
    type_label = POST_TYPE_LABELS[post_type]
    day_str   = today.strftime("%a %b %d, %Y")

    print(f"\n{'='*60}")
    print(f"  Africa Gold Intelligence — Daily Post Automation")
    print(f"  {day_str}  |  Post type: {type_label}")
    print(f"{'='*60}\n")

    # ── Fetch market data ──────────────────────────────────────────────────
    print("📊 Fetching market data...")
    gold   = fetch_yfinance(GOLD_TICKER)
    silver = fetch_yfinance(SILVER_TICKER)
    dxy    = fetch_yfinance(DXY_TICKER)
    sp500  = fetch_yfinance(SP500_TICKER)
    btc    = fetch_yfinance(BTC_TICKER)

    if not gold:
        print("❌ Could not fetch gold price. Aborting.")
        sys.exit(1)

    g_price = gold["price"]
    g_pct   = gold.get("day_chg_pct", 0)
    print(f"   Gold:   {fmt_price(g_price)}  ({sign_str(g_pct,'%')})")
    if silver: print(f"   Silver: {fmt_price(silver.get('price'))}")
    if dxy:    print(f"   DXY:    {fmt_price(dxy.get('price'),'',2)}")

    print("\n💱 Fetching FX rates...")
    fx_rates = fetch_fx_rates()
    for cur, rate in fx_rates.items():
        print(f"   USD/{cur}: {rate:.2f}" if rate else f"   USD/{cur}: N/A")

    karat_prices = calc_karat_prices(g_price, fx_rates)

    print("\n📰 Fetching news headlines...")
    news = fetch_news(max_items=6)
    print(f"   Found {len(news)} relevant headlines.")

    # ── Assemble data bundle ───────────────────────────────────────────────
    data = {
        "gold": gold, "silver": silver, "dxy": dxy,
        "sp500": sp500, "btc": btc,
        "fx_rates": fx_rates, "karat_prices": karat_prices,
        "news": news,
    }

    # ── Build content ──────────────────────────────────────────────────────
    print("\n✍️  Building post content...")
    free_html    = build_free_content(data, post_type, today)
    premium_html = build_premium_content(post_type, data, today)

    # ── Compose metadata ───────────────────────────────────────────────────
    title         = f"Gold Market Briefing | {today.strftime('%a %b %d, %Y')}"
    rsi_str       = f" · RSI {gold.get('rsi')}" if gold.get("rsi") else ""
    zar_str       = f"R{karat_prices.get('ZAR',{}).get('24K',0):,.0f}/g" if "ZAR" in karat_prices else ""
    subtitle      = (f"XAU/USD at {fmt_price(g_price)} · DXY {fmt_price(dxy.get('price',''),  '', 2)}"
                     f"{rsi_str} · {zar_str} + full {type_label} inside")
    email_subject = title
    preview_text  = (f"Gold {sign_str(g_pct,'%')} today at {fmt_price(g_price)}. "
                     f"Full {type_label} for Africa subscribers inside.")

    print(f"\n📝 Post title:    {title}")
    print(f"   Subtitle:     {subtitle[:80]}...")
    print(f"   Publish type: {PUBLISH_TYPE}")

    # ── Post to Beehiiv ────────────────────────────────────────────────────
    if not BEEHIIV_API_KEY:
        print("\n⚠️  BEEHIIV_API_KEY not set. Content built successfully but NOT posted.")
        print("   Set the key with:  export BEEHIIV_API_KEY='your_key_here'")
        print("   Then re-run this script.")
        # Save content preview for inspection
        with open("/tmp/agi_post_preview_free.html", "w") as f:
            f.write(free_html)
        with open("/tmp/agi_post_preview_premium.html", "w") as f:
            f.write(premium_html)
        print("   Content saved to /tmp/agi_post_preview_*.html for review.")
        return

    print("\n🚀 Posting to Beehiiv...")
    try:
        result = beehiiv_create_post(
            title=title, subtitle=subtitle,
            email_subject=email_subject, preview_text=preview_text,
            free_html=free_html, premium_html=premium_html,
            publish_type=PUBLISH_TYPE,
        )
        post_id  = result.get("data", {}).get("id", "unknown")
        post_url = result.get("data", {}).get("web_url", "")
        print(f"\n✅ Post published successfully!")
        print(f"   Post ID: {post_id}")
        if post_url:
            print(f"   URL:     {post_url}")
    except Exception as e:
        print(f"\n❌ Failed to post: {e}")
        sys.exit(1)

    print(f"\n{'='*60}\n  Done. {today.strftime('%H:%M:%S')}\n{'='*60}\n")


if __name__ == "__main__":
    main()
