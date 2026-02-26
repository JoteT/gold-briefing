#!/usr/bin/env python3
"""
monetization_agent.py — Africa Gold Intelligence — Tier 3: Monetization Optimizer
==================================================================================
Analyses market conditions and pipeline history to maximise premium subscription
revenue and free-to-paid conversion.

What it does each day:
  1. Scores today's upsell opportunity (0–100) based on:
       - Gold price volatility / momentum (high moves = premium urgency)
       - RSI extremes (overbought/oversold = reader anxiety = upsell moment)
       - Post type premium value (trader intel & macro = highest willingness to pay)
       - Gold ATH proximity (record prices = viral / high attention)
       - Pipeline streak (consecutive successes = trust building)
  2. Selects the best upsell strategy for today's conditions
  3. Generates ready-to-paste CTA copy (subject line, in-post banner, email PS)
  4. Recommends promotional pricing windows
  5. Tracks 30-day conversion pressure (avoids overselling)
  6. Logs everything to monetization_log.jsonl

Output: monetization_data dict included in the daily oversight email.

Usage (standalone test):
    python3 monetization_agent.py

Called by orchestrator.py after Partnership Outreach, before Human Oversight Gate.
"""

import json
import datetime
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR       = Path(__file__).parent
MONETIZATION_LOG = SCRIPT_DIR.parent / "logs" / "monetization_log.jsonl"
RUN_LOG          = SCRIPT_DIR.parent / "logs" / "run_log.jsonl"
SITE_URL         = "https://www.africagoldintelligence.com"
PREMIUM_URL      = f"{SITE_URL}/?utm_source=briefing&utm_medium=cta&utm_campaign=upsell"

# Premium pricing tiers
MONTHLY_PRICE    = 9    # USD/month
ANNUAL_PRICE     = 79   # USD/year (saves ~$29)
PROMO_PRICE      = 59   # USD/year (promotional)

# How often to include an aggressive upsell (prevents fatigue)
HARD_UPSELL_COOLDOWN_DAYS = 3
PROMO_COOLDOWN_DAYS       = 14


# ── Scoring engine ─────────────────────────────────────────────────────────────

# Post type premium value weights (higher = more premium-relevant content)
POST_TYPE_SCORES = {
    "trader_intelligence": 95,
    "macro_outlook":       90,
    "africa_regional":     80,
    "week_review":         85,
    "karat_pricing":       70,
    "aggregator":          65,
    "educational":         60,
}

def score_opportunity(data: dict, post_type: str, today: datetime.datetime) -> dict:
    """
    Score today's monetization opportunity from 0–100.
    Returns a breakdown dict with total score and component scores.
    """
    gold  = data.get("gold", {})
    price = gold.get("price", 0)
    pct   = abs(gold.get("day_chg_pct", 0) or 0)
    rsi   = gold.get("rsi")

    scores = {}

    # 1. Volatility score (big moves = urgency to know what's next)
    if pct >= 3.0:
        scores["volatility"] = 30
    elif pct >= 2.0:
        scores["volatility"] = 22
    elif pct >= 1.0:
        scores["volatility"] = 14
    else:
        scores["volatility"] = 5

    # 2. RSI extremes (readers feel uncertainty = premium analysis is valuable)
    if rsi is not None:
        if rsi >= 75 or rsi <= 25:
            scores["rsi_extreme"] = 20
        elif rsi >= 65 or rsi <= 35:
            scores["rsi_extreme"] = 12
        else:
            scores["rsi_extreme"] = 4
    else:
        scores["rsi_extreme"] = 0

    # 3. Post type premium value
    base = POST_TYPE_SCORES.get(post_type, 60)
    scores["post_type"] = round(base * 0.25)  # max 25 points

    # 4. ATH proximity (all-time high energy drives FOMO)
    # Gold ATH is approx $3,500 as of early 2025; by 2026 it's clearly higher
    # We score based on absolute price level as a proxy
    if price >= 5000:
        scores["ath_proximity"] = 20
    elif price >= 3500:
        scores["ath_proximity"] = 14
    elif price >= 2500:
        scores["ath_proximity"] = 8
    else:
        scores["ath_proximity"] = 3

    # 5. Pipeline streak bonus (consecutive successful runs = trust built up)
    streak = _get_success_streak()
    if streak >= 7:
        scores["streak_bonus"] = 5
    elif streak >= 3:
        scores["streak_bonus"] = 3
    else:
        scores["streak_bonus"] = 0

    total = min(100, sum(scores.values()))
    scores["total"] = total
    return scores


def _get_success_streak() -> int:
    """Count consecutive successful pipeline runs from run_log.jsonl."""
    if not RUN_LOG.exists():
        return 0
    try:
        lines = RUN_LOG.read_text().strip().splitlines()
        streak = 0
        for line in reversed(lines):
            rec = json.loads(line)
            if rec.get("status") == "SUCCESS":
                streak += 1
            else:
                break
        return streak
    except Exception:
        return 0


def _days_since_last_upsell(upsell_type: str = "hard") -> int:
    """Days since the last hard upsell or promo was included."""
    if not MONETIZATION_LOG.exists():
        return 9999
    try:
        lines = MONETIZATION_LOG.read_text().strip().splitlines()
        for line in reversed(lines):
            rec = json.loads(line)
            if rec.get("upsell_type") == upsell_type:
                ts = datetime.datetime.fromisoformat(rec["ts"])
                return (datetime.datetime.now() - ts).days
        return 9999
    except Exception:
        return 9999


# ── Strategy selector ──────────────────────────────────────────────────────────

def select_strategy(score: int, post_type: str, data: dict) -> str:
    """
    Choose the upsell strategy based on opportunity score and cooldowns.
    Returns: "hard_upsell" | "soft_upsell" | "value_reminder" | "promo" | "none"
    """
    days_since_hard  = _days_since_last_upsell("hard")
    days_since_promo = _days_since_last_upsell("promo")

    # Promotional offer (highest conversion, use sparingly)
    if score >= 80 and days_since_promo >= PROMO_COOLDOWN_DAYS:
        return "promo"

    # Hard upsell (direct ask with price)
    if score >= 65 and days_since_hard >= HARD_UPSELL_COOLDOWN_DAYS:
        return "hard_upsell"

    # Soft upsell (feature highlight, no price)
    if score >= 45:
        return "soft_upsell"

    # Value reminder (keep premium top of mind)
    if score >= 25:
        return "value_reminder"

    return "none"


# ── CTA copy generators ────────────────────────────────────────────────────────

def build_cta_copy(strategy: str, post_type: str, data: dict,
                   today: datetime.datetime) -> dict:
    """
    Generate ready-to-paste CTA copy for three placements:
      - subject_addition : appended to email subject line
      - in_post_banner   : HTML banner to embed in free content
      - email_ps         : plain-text PS for the email footer
    """
    gold  = data.get("gold", {})
    price = gold.get("price", 0)
    pct   = gold.get("day_chg_pct", 0) or 0
    sign  = "+" if pct >= 0 else ""
    move  = f"{sign}{pct:.1f}%"

    post_labels = {
        "trader_intelligence": "our full technical analysis",
        "macro_outlook":       "the full macro breakdown",
        "africa_regional":     "the complete Africa regional report",
        "week_review":         "the full weekly review",
        "karat_pricing":       "live karat prices in all 6 currencies",
        "aggregator":          "the full curated digest",
        "educational":         "the complete guide",
    }
    premium_feature = post_labels.get(post_type, "the full analysis")

    if strategy == "promo":
        subject_addition = " 🔓 Unlock Premium — Limited Offer Inside"
        email_ps = (
            f"P.S. Gold is {move} today. For a limited time, get full premium access "
            f"for ${PROMO_PRICE}/year (normally ${ANNUAL_PRICE}). "
            f"Upgrade now → {PREMIUM_URL}&offer=annual_promo"
        )
        banner_html = f"""
<div style="background:linear-gradient(135deg,#92400e,#b45309);
            border-radius:10px;padding:20px 24px;margin:24px 0;color:#fff;">
  <p style="margin:0 0 4px;font-size:11px;opacity:.8;text-transform:uppercase;
            letter-spacing:.08em;">Limited-Time Offer</p>
  <h3 style="margin:0 0 8px;font-size:18px;font-weight:800;">
    Gold {move} today — unlock the full picture
  </h3>
  <p style="margin:0 0 14px;font-size:14px;opacity:.9;">
    Premium subscribers get {premium_feature}, full karat pricing in all 6 currencies,
    macro context, and RSI signals — every single day.
  </p>
  <p style="margin:0 0 16px;font-size:13px;font-weight:700;">
    🎁 Annual plan: <s style="opacity:.6;">${ANNUAL_PRICE}</s>
    <span style="font-size:18px;"> ${PROMO_PRICE}/year</span>
    &nbsp;— limited offer
  </p>
  <a href="{PREMIUM_URL}&offer=annual_promo"
     style="display:inline-block;background:#fff;color:#92400e;font-weight:800;
            padding:11px 22px;border-radius:7px;text-decoration:none;font-size:14px;">
    Upgrade Now — Save ${ANNUAL_PRICE - PROMO_PRICE} →
  </a>
</div>"""

    elif strategy == "hard_upsell":
        subject_addition = " — Premium inside"
        email_ps = (
            f"P.S. Enjoying the briefing? Premium subscribers see {premium_feature} "
            f"every day. From ${MONTHLY_PRICE}/month or ${ANNUAL_PRICE}/year. "
            f"Upgrade → {PREMIUM_URL}"
        )
        banner_html = f"""
<div style="background:#fef9c3;border:2px solid #f59e0b;
            border-radius:8px;padding:18px 20px;margin:24px 0;">
  <h3 style="margin:0 0 8px;font-size:16px;color:#92400e;font-weight:800;">
    🔒 Premium: {premium_feature.capitalize()}
  </h3>
  <p style="margin:0 0 14px;font-size:13px;color:#78350f;">
    Free subscribers see the market snapshot. Premium members get the full
    analysis — including {premium_feature} — plus RSI signals, macro context,
    and karat pricing across all 6 African currencies.
  </p>
  <a href="{PREMIUM_URL}"
     style="display:inline-block;background:#b45309;color:#fff;font-weight:700;
            padding:10px 20px;border-radius:6px;text-decoration:none;font-size:13px;">
    Unlock Premium — from ${MONTHLY_PRICE}/month →
  </a>
</div>"""

    elif strategy == "soft_upsell":
        subject_addition = ""
        email_ps = (
            f"P.S. Premium subscribers receive {premium_feature} every day, "
            f"plus full karat pricing across all African currencies. "
            f"See what's included → {PREMIUM_URL}"
        )
        banner_html = f"""
<div style="background:#f0fdf4;border-left:4px solid #16a34a;
            padding:14px 18px;border-radius:0 6px 6px 0;margin:20px 0;">
  <p style="margin:0;font-size:13px;color:#15803d;">
    <strong>💛 Premium includes:</strong> {premium_feature.capitalize()},
    full African karat pricing, RSI signals, and macro context — delivered daily.
    <a href="{PREMIUM_URL}" style="color:#15803d;font-weight:700;">
      See plans →
    </a>
  </p>
</div>"""

    elif strategy == "value_reminder":
        subject_addition = ""
        email_ps = (
            f"P.S. Africa Gold Intelligence Premium includes full market analysis, "
            f"karat pricing in 6 African currencies, and RSI signals every day. "
            f"Learn more → {PREMIUM_URL}"
        )
        banner_html = f"""
<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;
            padding:12px 16px;margin:16px 0;font-size:12px;color:#6b7280;">
  💛 <strong style="color:#374151;">Africa Gold Intelligence Premium</strong>
  — full analysis, karat pricing across 6 African currencies, RSI signals.
  <a href="{PREMIUM_URL}" style="color:#b45309;font-weight:600;">See plans</a>
</div>"""

    else:  # none
        subject_addition = ""
        email_ps        = ""
        banner_html     = ""

    return {
        "subject_addition": subject_addition,
        "in_post_banner":   banner_html,
        "email_ps":         email_ps,
    }


# ── Pricing window detector ────────────────────────────────────────────────────

def detect_pricing_window(score: int, data: dict, today: datetime.datetime) -> dict:
    """
    Detect whether conditions favour a promotional pricing window.
    Returns recommendation dict.
    """
    gold = data.get("gold", {})
    pct  = abs(gold.get("day_chg_pct", 0) or 0)

    is_monday    = today.weekday() == 0
    is_friday    = today.weekday() == 4
    high_vol     = pct >= 2.0
    days_to_promo = max(0, PROMO_COOLDOWN_DAYS - (PROMO_COOLDOWN_DAYS - _days_since_last_upsell("promo")))

    if score >= 80 and high_vol:
        window = "NOW"
        reason = f"High volatility ({pct:.1f}%) + score {score}/100 — peak attention moment"
    elif score >= 70 and is_monday:
        window = "NOW"
        reason = "Monday + strong score — readers starting the week engaged"
    elif score >= 70 and is_friday:
        window = "NOW"
        reason = "Friday + strong score — weekend reading behaviour drives conversions"
    elif score >= 60:
        window = "SOON"
        reason = f"Score {score}/100 — solid conditions, next cooldown clears in {days_to_promo}d"
    else:
        window = "WAIT"
        reason = f"Score {score}/100 — hold until a higher-volatility day"

    return {
        "window":     window,
        "reason":     reason,
        "score":      score,
        "promo_price": PROMO_PRICE,
        "annual_price": ANNUAL_PRICE,
        "monthly_price": MONTHLY_PRICE,
    }


# ── Logging ────────────────────────────────────────────────────────────────────

def log_monetization(post_type: str, score_breakdown: dict, strategy: str,
                     pricing_window: dict, today: datetime.datetime):
    record = {
        "ts":             today.isoformat(),
        "post_type":      post_type,
        "score":          score_breakdown.get("total", 0),
        "score_breakdown": score_breakdown,
        "strategy":       strategy,
        "upsell_type":    strategy if strategy in ("hard_upsell", "promo") else "soft",
        "pricing_window": pricing_window["window"],
    }
    try:
        with open(MONETIZATION_LOG, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        print(f"  ⚠️  Monetization log write failed: {e}")


# ── HTML block for oversight email ─────────────────────────────────────────────

def build_monetization_html_block(score_breakdown: dict, strategy: str,
                                   cta: dict, pricing_window: dict) -> str:
    score = score_breakdown.get("total", 0)
    color = "#16a34a" if score >= 70 else "#d97706" if score >= 45 else "#6b7280"
    strategy_labels = {
        "promo":          "🎁 Promotional offer",
        "hard_upsell":    "💰 Direct upsell",
        "soft_upsell":    "💡 Feature highlight",
        "value_reminder": "📌 Value reminder",
        "none":           "⏸️  No upsell today",
    }
    strategy_label = strategy_labels.get(strategy, strategy)
    window_colors  = {"NOW": "#16a34a", "SOON": "#d97706", "WAIT": "#6b7280"}
    window_color   = window_colors.get(pricing_window["window"], "#6b7280")

    breakdown_rows = "".join(
        f"<tr><td style='padding:4px 8px;color:#6b7280;font-size:12px;'>{k.replace('_',' ').title()}</td>"
        f"<td style='padding:4px 8px;font-size:12px;font-weight:600;'>{v}</td></tr>"
        for k, v in score_breakdown.items() if k != "total"
    )

    ps_safe = (cta.get("email_ps", "") or "").replace("&", "&amp;").replace("<", "&lt;")

    return f"""
    <h3 style="font-size:14px;color:#374151;margin:24px 0 8px;">
      💰 Monetization Optimizer
    </h3>
    <div style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;margin-bottom:16px;">

      <div style="background:#f9fafb;padding:12px 16px;
                  display:flex;justify-content:space-between;align-items:center;
                  border-bottom:1px solid #e5e7eb;">
        <div>
          <span style="font-size:24px;font-weight:800;color:{color};">{score}</span>
          <span style="font-size:13px;color:#6b7280;">/100 opportunity score</span>
        </div>
        <div style="text-align:right;">
          <p style="margin:0;font-size:13px;font-weight:700;color:#111;">{strategy_label}</p>
          <p style="margin:2px 0 0;font-size:11px;color:{window_color};font-weight:600;">
            Pricing window: {pricing_window['window']}
          </p>
        </div>
      </div>

      <div style="padding:14px 16px;">
        <p style="margin:0 0 6px;font-size:12px;color:#6b7280;">
          <strong>Score breakdown:</strong>
        </p>
        <table style="width:100%;border-collapse:collapse;">
          {breakdown_rows}
        </table>
        <p style="margin:10px 0 0;font-size:12px;color:#6b7280;">
          <strong>Pricing signal:</strong> {pricing_window['reason']}
        </p>
      </div>

      {'<div style="border-top:1px solid #e5e7eb;padding:14px 16px;"><p style="margin:0 0 6px;font-size:12px;font-weight:700;color:#374151;">Email P.S. — add to bottom of briefing:</p><pre style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;padding:10px;font-size:11px;white-space:pre-wrap;font-family:monospace;margin:0;color:#111;">' + ps_safe + '</pre></div>' if ps_safe else ''}

    </div>

    {'<p style="font-size:12px;color:#374151;margin:0 0 4px;font-weight:700;">In-post CTA banner (paste into Beehiiv free content):</p>' + cta.get("in_post_banner","") if cta.get("in_post_banner") else ""}
    """


# ── Main entry point ───────────────────────────────────────────────────────────

def run(post_type: str, data: dict, today: datetime.datetime) -> dict:
    """
    Main entry point — called by orchestrator.py.

    Returns monetization_data dict:
        score           — opportunity score 0-100
        strategy        — selected strategy string
        cta             — dict with subject_addition, in_post_banner, email_ps
        pricing_window  — dict with window, reason, prices
        html_block      — HTML for operator email
    """
    score_breakdown = score_opportunity(data, post_type, today)
    score           = score_breakdown["total"]
    strategy        = select_strategy(score, post_type, data)
    cta             = build_cta_copy(strategy, post_type, data, today)
    pricing_window  = detect_pricing_window(score, data, today)

    print(f"  📊 Opportunity score: {score}/100  →  Strategy: {strategy}")
    print(f"  💳 Pricing window: {pricing_window['window']} — {pricing_window['reason']}")
    if cta["subject_addition"]:
        print(f"  ✉️  Subject addition: {cta['subject_addition']}")
    if cta["email_ps"]:
        print(f"  📝 PS copy ready ({len(cta['email_ps'])} chars)")

    log_monetization(post_type, score_breakdown, strategy, pricing_window, today)

    html_block = build_monetization_html_block(score_breakdown, strategy, cta, pricing_window)

    return {
        "score":          score,
        "strategy":       strategy,
        "cta":            cta,
        "pricing_window": pricing_window,
        "html_block":     html_block,
    }


# ── Standalone test ────────────────────────────────────────────────────────────

def _test():
    today = datetime.datetime.now()
    mock_data = {
        "gold":   {"price": 5205.60, "day_chg_pct": 2.89, "rsi": 68.4},
        "silver": {"price": 87.26},
        "dxy":    {"price": 97.81},
        "fx_rates": {
            "ZAR": 16.01, "GHS": 10.84, "NGN": 1344.40,
            "KES": 129.03, "EGP": 47.71, "MAD": 9.16,
        },
        "karat_prices": {
            "ZAR": {"24K": 2680}, "GHS": {"24K": 1814},
            "NGN": {"24K": 225004}, "KES": {"24K": 21595},
        },
        "news": [],
    }

    for pt in ["trader_intelligence", "karat_pricing", "educational"]:
        print(f"\n{'═'*60}")
        print(f"  POST TYPE: {pt}")
        result = run(pt, mock_data, today)
        print(f"\n  CTA subject addition: '{result['cta']['subject_addition']}'")
        print(f"  PS length: {len(result['cta']['email_ps'])} chars")
        print(f"  Banner length: {len(result['cta']['in_post_banner'])} chars")

    print(f"\n✅ Monetization Agent test complete. Log: {MONETIZATION_LOG}\n")


if __name__ == "__main__":
    _test()
