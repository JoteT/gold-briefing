#!/usr/bin/env python3
"""
africa_data_agent.py — Africa Gold Intelligence
================================================
Collects Africa-specific gold market data unavailable from mainstream
financial sources. Feeds into the content synthesis stage to produce
deeply differentiated briefings.

Data collected:
  · African listed miner stocks (GFI, AU, HMY, SBSW, EDV)
  · Real-time AISC margin analysis per miner
  · Currency leverage — how FX moves impact producer margins & buyer costs
  · Africa-specific gold news (Mining Weekly, Engineering News, BusinessDay)
  · Production-weighted pan-African gold price composite
  · Country production share & mining sector context
  · Seasonal demand signals (Islamic calendar, harvest seasons, wedding cycles)
  · Miner profitability ranking
"""

import os, sys, json, datetime, math
from pathlib import Path

# ── Load .env ────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
_env_file  = SCRIPT_DIR.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            _k, _v = _k.strip(), _v.strip()
            if _v and "REPLACE_WITH" not in _v and "your_" not in _v.lower():
                os.environ[_k] = _v

TROY_OZ_TO_GRAM = 31.1035

# ── African miner universe ────────────────────────────────────────────────────
# AISC = All-In Sustaining Cost per oz (USD) — from latest annual reports
# Updated: FY2024 guidance / most recent published figures
AFRICAN_MINERS = {
    "Gold Fields":       {"ticker": "GFI",    "exchange": "NYSE", "hq": "South Africa", "aisc": 1340, "operations": ["South Africa","Ghana","Australia","Peru"]},
    "AngloGold Ashanti": {"ticker": "AU",     "exchange": "NYSE", "hq": "South Africa", "aisc": 1450, "operations": ["South Africa","Ghana","Tanzania","DRC","Guinea"]},
    "Harmony Gold":      {"ticker": "HMY",    "exchange": "NYSE", "hq": "South Africa", "aisc": 1520, "operations": ["South Africa","Papua New Guinea"]},
    "Sibanye-Stillwater":{"ticker": "SBSW",   "exchange": "NYSE", "hq": "South Africa", "aisc": 1480, "operations": ["South Africa","USA","Zimbabwe"]},
    "Endeavour Mining":  {"ticker": "EDV.TO", "exchange": "TSX",  "hq": "Côte d'Ivoire","aisc": 1340, "operations": ["Burkina Faso","Côte d'Ivoire","Senegal","Mali"]},
}

# ── African country production weights ───────────────────────────────────────
# % share of African gold production (WGC 2024 estimates)
PRODUCTION_WEIGHTS = {
    "South Africa":  0.130,
    "Ghana":         0.125,
    "Mali":          0.100,
    "Burkina Faso":  0.085,
    "Tanzania":      0.080,
    "DRC":           0.070,
    "Guinea":        0.065,
    "Sudan":         0.060,
    "Zimbabwe":      0.055,
    "Egypt":         0.050,
    "Côte d'Ivoire": 0.040,
    "Senegal":       0.035,
    "Others":        0.105,
}

# ── Country context (updated manually each quarter) ──────────────────────────
COUNTRY_CONTEXT = {
    "South Africa": {
        "currency": "ZAR",
        "mining_status": "stable",
        "key_note": "Loadshedding risk remains a structural cost headwind for deep-level mines. Witwatersrand basin output continues long-term decline; operations shifting to open-pit and surface tailings.",
        "regulatory": "DMRE royalty regime (0.5–5% sliding scale on revenue). New Mining Charter requires 30% BEE ownership.",
        "key_miners": ["Gold Fields (GFI)", "Harmony Gold (HMY)", "Sibanye-Stillwater (SBSW)"],
    },
    "Ghana": {
        "currency": "GHS",
        "mining_status": "stable",
        "key_note": "World's second-largest African gold producer. Government targets 5% royalty on mining revenue. Galamsey (illegal ASM) activity adds ~20–30 toz/year informally.",
        "regulatory": "Minerals Commission oversees licensing. 10% carried interest for government in new mines.",
        "key_miners": ["Gold Fields (GFI - Tarkwa)", "AngloGold (AU - Obuasi)", "Kinross (KGC - Chirano)"],
    },
    "Mali": {
        "currency": "XOF",
        "mining_status": "elevated_risk",
        "key_note": "Military junta renegotiating all mining contracts since 2023 coup. Barrick's Loulo-Gounkoto suspended; ~800koz/yr offline. Political risk premium remains high.",
        "regulatory": "New mining code (2023) raises royalties to 6–10%. Junta demanding larger state stakes.",
        "key_miners": ["Barrick Gold (GOLD - Loulo-Gounkoto)", "Endeavour Mining (EDV)"],
    },
    "Burkina Faso": {
        "currency": "XOF",
        "mining_status": "high_risk",
        "key_note": "Security crisis in Sahel region disrupting supply chains. Several mines operating under force majeure. Endeavour Mining navigating challenging operating environment.",
        "regulatory": "Transitional government demanding 15% state equity in all mines. Tax regime being overhauled.",
        "key_miners": ["Endeavour Mining (EDV)", "IAMGOLD (IAG - Essakane)"],
    },
    "Tanzania": {
        "currency": "TZS",
        "mining_status": "stable",
        "key_note": "Post-Acacia dispute stability under Samia government. Barrick's Twiga JV producing 500koz+/yr. New mineral wealth fund reinvesting royalties locally.",
        "regulatory": "Mining Act (2017) requires 16% government free-carry interest. 6% royalty on gold.",
        "key_miners": ["Barrick/Twiga JV (Bulyanhulu, North Mara)", "AngloGold (Geita)"],
    },
    "DRC": {
        "currency": "CDF",
        "mining_status": "elevated_risk",
        "key_note": "Largest ASM gold producer in Africa — 90%+ of output is artisanal. Formal sector growing in Ituri/Kivu. Conflict minerals tracking frameworks (OECD DD) increasingly required by buyers.",
        "regulatory": "Mining Code (2018) raised royalties. CAMI issues permits. Security costs are major AISC driver.",
        "key_miners": ["AngloGold (Kibali JV)", "Twangiza Mining"],
    },
    "Zimbabwe": {
        "currency": "ZWG",
        "mining_status": "stable",
        "key_note": "Fastest-growing gold sector in Africa — targeting 100 toz/yr by 2025. Fidelity Gold Refinery (state) is sole offtaker. Currency reforms improving miner confidence.",
        "regulatory": "Mandatory selling to Fidelity Bullion (state) at market rates. 5% royalty.",
        "key_miners": ["Caledonia Mining (CMCL - Blanket Mine)", "Great Dyke Investments"],
    },
    "Egypt": {
        "currency": "EGP",
        "mining_status": "stable",
        "key_note": "Sukari mine (Centamin) is Africa's largest single open-pit gold mine by production. Eastern Desert prospective for new discoveries. High jewelry demand from 100M+ population.",
        "regulatory": "Concession-based system. Profit-sharing with EMRA (state authority). 3% royalty.",
        "key_miners": ["Centamin (CEY - Sukari)", "Aton Resources"],
    },
    "Guinea": {
        "currency": "GNF",
        "mining_status": "elevated_risk",
        "key_note": "Post-coup military government (CNRD) renegotiating contracts. SAG (AngloGold) and Leocor operations continue with uncertainty. Bauxite dominates sector but gold growing.",
        "regulatory": "2011 Mining Code under revision. Government targeting larger state participation.",
        "key_miners": ["AngloGold Ashanti (Siguiri)", "Leocor Gold"],
    },
}

# ── Africa RSS news feeds ─────────────────────────────────────────────────────
AFRICA_FEEDS = [
    ("Mining Weekly",     "https://www.miningweekly.com/rss/latest"),
    ("Engineering News",  "https://www.engineeringnews.co.za/rss/latest"),
    ("BusinessDay NG",    "https://businessday.ng/feed/"),
    ("African Mining",    "https://www.africanmining.co.za/feed/"),
    ("IOL Business",      "https://iol.co.za/rss/feed?id=2"),
]

AFRICA_GOLD_KEYWORDS = [
    "gold", "miner", "mining", "ounce", "oz", "bullion", "precious metal",
    "gold fields", "anglogold", "harmony", "sibanye", "endeavour", "centamin",
    "witwatersrand", "ashanti", "rand", "JSE", "mine production", "AISC",
    "royalty", "concession", "artisanal", "ASM", "doré", "concentrate",
    "loadshedding", "eskom", "sahel", "mali gold", "ghana gold", "zimbabwe gold",
    "african gold", "sub-saharan", "west africa gold", "east africa gold",
]

# ── Seasonal demand calendar ──────────────────────────────────────────────────
def get_seasonal_signals(today: datetime.datetime) -> list:
    """
    Return active seasonal demand signals affecting African gold markets.
    Covers Islamic calendar (Eid, Ramadan), African harvest seasons,
    South Asian wedding cycle, and Chinese demand seasonality.
    """
    signals = []
    m, d = today.month, today.day

    # ── Chinese demand cycle
    if m == 1 or (m == 2 and d <= 15):
        signals.append({
            "signal": "🇨🇳 Chinese New Year Buying Season",
            "impact": "POSITIVE",
            "note": "China is Africa's #1 gold buyer (doré & concentrate). Pre-CNY restocking typically lifts African mine-gate prices 2–5% above spot.",
            "affected": ["DRC", "Zimbabwe", "Guinea", "Mali"],
        })

    # ── South Asian wedding season (two peaks)
    if (m == 11 and d >= 15) or m == 12 or (m == 1 and d <= 15):
        signals.append({
            "signal": "💍 South Asian Winter Wedding Season",
            "impact": "POSITIVE",
            "note": "Nov–Jan wedding season drives Indian jewelry demand — India imports ~40% of African gold. Typically adds 3–8% to physical premium.",
            "affected": ["Ghana", "South Africa", "Tanzania"],
        })
    if (m == 4 and d >= 15) or (m == 5 and d <= 31):
        signals.append({
            "signal": "💍 South Asian Spring Wedding Season",
            "impact": "POSITIVE",
            "note": "Apr–May wedding season — second Indian peak demand period. Watch for physical premiums above London AM fix.",
            "affected": ["Ghana", "South Africa", "Tanzania"],
        })

    # ── Ramadan & Eid demand (approximate — varies by year)
    # Ramadan 2025: Mar 1 – Mar 30; Eid al-Fitr: Mar 30–31
    # Ramadan 2026: Feb 18 – Mar 19; Eid al-Fitr: Mar 19–20
    if (m == 2 and d >= 18) or (m == 3 and d <= 19):
        signals.append({
            "signal": "🌙 Ramadan 2026 (Feb 18 – Mar 19)",
            "impact": "MIXED",
            "note": "Trading volumes typically lighter during Ramadan in North/West Africa. Post-Eid gifting (gold jewelry) creates demand spike in Egypt, Morocco, Nigeria.",
            "affected": ["Egypt", "Morocco", "Nigeria", "Senegal"],
        })
    if (m == 3 and d >= 19 and d <= 30):
        signals.append({
            "signal": "🎉 Eid al-Fitr Gift Buying",
            "impact": "POSITIVE",
            "note": "Strong gold jewelry gifting tradition at Eid. Egyptian souk and Moroccan medina traders report 20–40% volume spikes in the week post-Eid.",
            "affected": ["Egypt", "Morocco", "Nigeria"],
        })

    # ── Harvest season wealth conversion (West Africa)
    if m in [11, 12]:
        signals.append({
            "signal": "🌾 West African Harvest Season",
            "impact": "POSITIVE",
            "note": "Cocoa/cashew harvest payments in Ghana, Côte d'Ivoire, Nigeria drive wealth conversion to gold. Rural gold buying typically rises 15–25% in Q4.",
            "affected": ["Ghana", "Côte d'Ivoire", "Nigeria"],
        })

    # ── South African year-end / bonus season
    if m == 12:
        signals.append({
            "signal": "💰 SA Year-End Bonus Season",
            "impact": "POSITIVE",
            "note": "December bonuses in South Africa drive retail gold coin and krugerrand purchases. SA Mint reports strongest coin sales in Q4.",
            "affected": ["South Africa"],
        })

    return signals


# ── Core data collection ──────────────────────────────────────────────────────

def fetch_miner_stocks(gold_price: float) -> dict:
    """
    Fetch African miner stock prices and calculate AISC margins.
    Returns dict keyed by miner name.
    """
    try:
        import yfinance as yf
    except ImportError:
        print("  ⚠️  yfinance not installed — skipping miner stocks.")
        return {}

    results = {}
    for name, cfg in AFRICAN_MINERS.items():
        try:
            ticker  = cfg["ticker"]
            t       = yf.Ticker(ticker)
            hist    = t.history(period="5d", interval="1d")
            if hist.empty:
                continue

            price     = float(hist["Close"].iloc[-1])
            prev      = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price
            day_chg   = price - prev
            day_pct   = (day_chg / prev * 100) if prev else 0
            week_pct  = ((price - float(hist["Close"].iloc[0])) / float(hist["Close"].iloc[0]) * 100) if len(hist) > 1 else 0

            aisc        = cfg["aisc"]
            margin_usd  = round(gold_price - aisc, 0)
            margin_pct  = round((margin_usd / gold_price) * 100, 1) if gold_price else 0

            results[name] = {
                "ticker":      ticker,
                "exchange":    cfg["exchange"],
                "hq":          cfg["hq"],
                "price":       round(price, 2),
                "day_chg":     round(day_chg, 2),
                "day_pct":     round(day_pct, 2),
                "week_pct":    round(week_pct, 2),
                "aisc":        aisc,
                "margin_usd":  margin_usd,
                "margin_pct":  margin_pct,
                "operations":  cfg["operations"],
                "profitable":  margin_usd > 0,
            }
        except Exception as e:
            print(f"  ⚠️  Miner stock error [{name}]: {e}")

    return results


def fetch_africa_news(max_items: int = 8) -> list:
    """Fetch gold-related headlines from Africa-specific RSS feeds."""
    try:
        import feedparser
    except ImportError:
        return []

    items = []
    for source, url in AFRICA_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:30]:
                title   = entry.get("title", "")
                summary = entry.get("summary", "")
                link    = entry.get("link", "#")
                text    = (title + " " + summary).lower()
                if any(kw in text for kw in AFRICA_GOLD_KEYWORDS):
                    items.append({"source": source, "title": title, "link": link})
                if len(items) >= max_items:
                    return items[:max_items]
        except Exception:
            pass

    return items[:max_items]


def calc_currency_leverage(gold_price: float, fx_rates: dict, karat_prices: dict) -> dict:
    """
    For each African currency, calculate:
    - How much the local gold price changes for every 1% FX move
    - Current producer margin boost/drag vs last month (approximate)
    - Buyer vs producer impact (opposite directions)
    """
    result = {}
    country_map = {
        "ZAR": {"country": "South Africa", "role": "major_producer", "miners": ["Gold Fields", "Harmony Gold", "Sibanye-Stillwater"]},
        "GHS": {"country": "Ghana",        "role": "major_producer", "miners": ["Gold Fields (Tarkwa)", "AngloGold (Obuasi)"]},
        "NGN": {"country": "Nigeria",      "role": "consumer",       "miners": []},
        "KES": {"country": "Kenya",        "role": "consumer",       "miners": []},
        "EGP": {"country": "Egypt",        "role": "mixed",          "miners": ["Centamin (Sukari)"]},
        "MAD": {"country": "Morocco",      "role": "consumer",       "miners": []},
    }

    for cur, meta in country_map.items():
        rate = fx_rates.get(cur)
        if not rate:
            continue

        k24 = karat_prices.get(cur, {}).get("24K", 0)

        # A 1% weakening of local currency (rate goes up by 1%) raises local gold price by ~1%
        local_price_per_1pct_fx = round(k24 * 0.01, 0)

        # For producers: they earn USD, pay costs in local currency
        # → Currency weakness is GOOD for local producers (lower costs in USD terms)
        # For buyers: local currency weakness means gold costs MORE
        role = meta["role"]
        if role == "major_producer":
            impact_note = f"ZAR/USD weakness boosts {meta['country']} miner margins — costs fall in USD terms while gold revenue stays in USD."
            buyer_impact = "negative"
            producer_impact = "positive"
        elif role == "consumer":
            impact_note = f"Currency weakness increases gold cost for {meta['country']} buyers — local gold prices rise even if USD spot is flat."
            buyer_impact = "negative"
            producer_impact = "neutral"
        else:
            impact_note = f"{meta['country']} has both mining and jewelry demand — mixed currency impact."
            buyer_impact = "negative"
            producer_impact = "positive"

        result[cur] = {
            "country":                meta["country"],
            "role":                   role,
            "fx_rate":                rate,
            "gold_per_gram_local":    k24,
            "local_price_per_1pct_fx": local_price_per_1pct_fx,
            "buyer_impact":           buyer_impact,
            "producer_impact":        producer_impact,
            "impact_note":            impact_note,
            "miners":                 meta["miners"],
        }

    return result


def calc_pan_african_composite(gold_price: float, fx_rates: dict) -> dict:
    """
    Calculate a production-weighted Pan-African gold price composite.
    Shows what the average African gold producer effectively receives
    after weighting by each country's production share.
    For countries where miners sell in USD: it's just spot.
    The insight: which countries are relatively over/underperforming.
    """
    # Approximate AISC by country (weighted average of operating miners)
    country_aisc = {
        "South Africa":  1520,  # Deep-level mines; highest AISC
        "Ghana":         1280,
        "Mali":          1150,
        "Burkina Faso":  1300,
        "Tanzania":      1200,
        "DRC":            950,  # Low formal AISC; ASM dominated
        "Guinea":        1250,
        "Sudan":          900,  # ASM dominated
        "Zimbabwe":      1100,
        "Egypt":         1050,  # Sukari open-pit; efficient
        "Côte d'Ivoire": 1200,
        "Senegal":       1150,
        "Others":        1200,
    }

    weighted_margin = 0.0
    best_margin_country  = ""
    best_margin          = -99999
    worst_margin_country = ""
    worst_margin         = 99999
    breakdown            = {}

    for country, weight in PRODUCTION_WEIGHTS.items():
        aisc   = country_aisc.get(country, 1200)
        margin = gold_price - aisc
        weighted_margin += margin * weight
        breakdown[country] = {
            "weight_pct":  round(weight * 100, 1),
            "aisc":        aisc,
            "margin":      round(margin, 0),
            "margin_pct":  round((margin / gold_price) * 100, 1) if gold_price else 0,
        }
        if margin > best_margin:
            best_margin = margin
            best_margin_country = country
        if margin < worst_margin:
            worst_margin = margin
            worst_margin_country = country

    return {
        "weighted_avg_margin":    round(weighted_margin, 0),
        "weighted_margin_pct":    round((weighted_margin / gold_price) * 100, 1) if gold_price else 0,
        "best_margin_country":    best_margin_country,
        "best_margin":            round(best_margin, 0),
        "worst_margin_country":   worst_margin_country,
        "worst_margin":           round(worst_margin, 0),
        "breakdown":              breakdown,
    }


def get_miner_ranking(miners: dict) -> list:
    """Rank miners by today's stock performance."""
    ranked = sorted(
        [(name, d) for name, d in miners.items()],
        key=lambda x: x[1].get("day_pct", 0),
        reverse=True,
    )
    return ranked


# ── Main entry point ──────────────────────────────────────────────────────────

def run(data: dict, today: datetime.datetime) -> dict:
    """
    Run the Africa Intelligence data collection.

    Args:
        data: market data dict from Agent 1 (gold price, FX rates, etc.)
        today: current datetime

    Returns:
        africa_data dict with all Africa-specific intelligence
    """
    gold_price  = data.get("gold", {}).get("price", 0)
    fx_rates    = data.get("fx_rates", {})
    karat_prices= data.get("karat_prices", {})

    print("  ⛏️  African miner stocks & AISC margins...")
    miners = fetch_miner_stocks(gold_price)
    if miners:
        ranked = get_miner_ranking(miners)
        top_miner   = ranked[0][0]  if ranked else ""
        worst_miner = ranked[-1][0] if ranked else ""
        avg_margin  = round(sum(m["margin_usd"] for m in miners.values()) / len(miners), 0) if miners else 0
        print(f"     {len(miners)} miners tracked · avg margin ${avg_margin:,.0f}/oz")
    else:
        top_miner, worst_miner, avg_margin = "", "", 0

    print("  📡 Africa-specific news feeds...")
    africa_news = fetch_africa_news(max_items=8)
    print(f"     {len(africa_news)} Africa gold headline(s) found")

    print("  💱 Currency leverage analysis...")
    currency_leverage = calc_currency_leverage(gold_price, fx_rates, karat_prices)

    print("  🌍 Pan-African composite & production weights...")
    pan_african = calc_pan_african_composite(gold_price, fx_rates)

    print("  📅 Seasonal demand signals...")
    seasonal_signals = get_seasonal_signals(today)
    if seasonal_signals:
        print(f"     {len(seasonal_signals)} active signal(s): {', '.join(s['signal'] for s in seasonal_signals)}")
    else:
        print("     No major seasonal signals active today")

    return {
        "miners":           miners,
        "top_miner":        top_miner,
        "worst_miner":      worst_miner,
        "avg_margin":       avg_margin,
        "africa_news":      africa_news,
        "currency_leverage":currency_leverage,
        "pan_african":      pan_african,
        "seasonal_signals": seasonal_signals,
        "country_context":  COUNTRY_CONTEXT,
        "production_weights": PRODUCTION_WEIGHTS,
        "gold_price":       gold_price,
    }
