#!/usr/bin/env python3
"""
orchestrator.py — Africa Gold Intelligence — Tier 0 Orchestrator
=================================================================
Coordinates the Phase 1 agent pipeline:

  Agent 1   · Market Intelligence      — fetches prices, FX rates, news
  Agent 1.5 · Africa Intelligence      — miner AISC margins, currency leverage,
                                         pan-African composite, seasonal signals,
                                         Africa-specific news feeds
  Agent 1.6 · Contract Transparency   — mining contracts database, royalty gap
                                         analysis, shadow economy tracker,
                                         resource nationalism monitor, illicit
                                         flow intelligence (Dubai gap, GFI data)
  Agent 2   · Content Synthesis        — builds free + premium briefing HTML
                                         (enriched with Africa + contract sections)
  Agent 3   · Distribution             — creates draft post on Beehiiv

Human Oversight Gate
  All posts are created as DRAFTS. The orchestrator sends you a notification
  email with a direct link to review and approve the draft before it reaches
  any subscribers.

Anomaly Detection
  Gold price range check ($800–$15,000), unusual daily swings (>10%),
  missing FX rates. Critical anomalies halt the pipeline before posting.

Run Logging
  Every run is appended to run_log.jsonl (JSONL format) in this directory.
  Fields: timestamp, status, stage, gold_price, day_pct, post_type, warnings,
          elapsed_s, africa_miners, pan_african_margin, contracts_tracked,
          royalty_gap_usd_m, shadow_tonnes, nationalism_alerts

USAGE:
  python3 orchestrator.py                              # live run → creates Beehiiv draft
  python3 orchestrator.py --dry-run                   # build content, skip Beehiiv post
  python3 orchestrator.py --publish                   # live run → publish immediately
  python3 orchestrator.py --log                       # print the last 5 run log entries
  python3 orchestrator.py --dry-run --post-type africa_regional   # force Tuesday edition
  python3 orchestrator.py --dry-run --post-type monday_deep_dive  # force Monday edition

  Post type names: monday_deep_dive, africa_regional, aggregator,
                   africa_premium, trader_intel, analysis, week_review

ENVIRONMENT VARIABLES (required for live runs):
  BEEHIIV_API_KEY   — Beehiiv V2 API key  (beehiiv.com/settings/api)
  NOTIFY_PASSWORD   — Gmail App Password for operator notifications
                      (myaccount.google.com/apppasswords)

OPTIONAL:
  BEEHIIV_PUB_ID    — publication ID (defaults to AGI pub)
  NOTIFY_EMAIL      — operator email (defaults to jote.taddese@gmail.com)
"""

import os, sys, json, datetime, traceback, smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR      = Path(__file__).parent
LOG_FILE        = SCRIPT_DIR / "logs" / "run_log.jsonl"
BEEHIIV_DRAFTS  = "https://app.beehiiv.com/posts?tab=draft"

# Load .env file if present — always overrides plist/shell placeholders
_env_file = SCRIPT_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            _k, _v = _k.strip(), _v.strip()
            # Skip lines that still contain placeholder text
            if _v and "REPLACE_WITH" not in _v and "your_" not in _v.lower():
                os.environ[_k] = _v

NOTIFY_EMAIL    = os.environ.get("NOTIFY_EMAIL",    "jote.taddese@gmail.com")
NOTIFY_PASSWORD = os.environ.get("NOTIFY_PASSWORD", os.environ.get("GOLD_EMAIL_PASSWORD", ""))
DRY_RUN         = os.environ.get("AGI_DRY_RUN", "0") == "1" or "--dry-run" in sys.argv
AUTO_PUBLISH    = os.environ.get("AGI_AUTO_PUBLISH", "0") == "1" or "--publish" in sys.argv
PRINT_LOG       = "--log" in sys.argv

# --post-type <name>  forces a specific edition regardless of the day of the week
# Valid names: monday_deep_dive, africa_regional, aggregator, africa_premium,
#              trader_intel, analysis, week_review
_FORCE_POST_TYPE = None
if "--post-type" in sys.argv:
    _pt_idx = sys.argv.index("--post-type")
    if _pt_idx + 1 < len(sys.argv):
        _FORCE_POST_TYPE = sys.argv[_pt_idx + 1]

# publish_type: "draft" = human reviews before sending; "instant" = posts live immediately
PUBLISH_TYPE    = "instant" if AUTO_PUBLISH else "draft"
os.environ["AGI_PUBLISH_TYPE"] = PUBLISH_TYPE


# ── Utilities ─────────────────────────────────────────────────────────────────

def sep(label=""):
    width = 60
    if label:
        pad = max(2, (width - len(label) - 2) // 2)
        print(f"\n{'─'*pad} {label} {'─'*(width - pad - len(label) - 2)}\n")
    else:
        print(f"\n{'─'*width}\n")


def log_run(status: str, details: dict) -> dict:
    record = {"ts": datetime.datetime.now().isoformat(), "status": status, **details}
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")
    return record


def print_recent_logs(n=5):
    if not LOG_FILE.exists():
        print("  No run log found yet.")
        return
    lines = LOG_FILE.read_text().strip().splitlines()
    recent = lines[-n:]
    print(f"\n  Last {len(recent)} run(s):\n")
    for line in recent:
        try:
            r = json.loads(line)
            ts      = r.get("ts", "?")[:19]
            status  = r.get("status", "?")
            ptype   = r.get("post_type", "?")
            price   = r.get("gold_price", "?")
            elapsed = r.get("elapsed_s", "?")
            icon    = "✅" if status == "SUCCESS" else ("🔬" if status == "DRY_RUN" else "❌")
            print(f"  {icon} {ts}  {status:<10}  {ptype:<22}  ${price}  {elapsed}s")
        except Exception:
            print(f"  {line}")
    print()


# ── Anomaly Detection ─────────────────────────────────────────────────────────

def check_data_quality(data: dict) -> list:
    """
    Returns list of warning strings. Strings starting with 'CRITICAL'
    will halt the pipeline before any post is created.
    """
    warnings = []
    gold  = data.get("gold", {})
    price = gold.get("price", 0)

    # Gold price sanity band (raised ceiling to $15,000 to accommodate 2026 ATH levels)
    if not (800 <= price <= 15000):
        warnings.append(
            f"CRITICAL: Gold price ${price:,.2f} is outside expected range ($800–$15,000). "
            f"Possible stale or corrupted data. Halting pipeline."
        )

    # Unusually large daily swing
    pct = abs(gold.get("day_chg_pct") or 0)
    if pct > 10:
        warnings.append(
            f"WARNING: Daily gold move of {pct:.1f}% is unusually large (>10%). "
            f"Verify market conditions before publishing."
        )

    # Missing FX data
    fx = data.get("fx_rates", {})
    missing = [c for c in ["ZAR", "GHS", "NGN", "KES"] if not fx.get(c)]
    if missing:
        warnings.append(
            f"WARNING: FX rates missing for {', '.join(missing)}. "
            f"Fallback rates used in karat pricing table."
        )

    # News fetch failure
    if not data.get("news"):
        warnings.append(
            "WARNING: No news headlines fetched. RSS feeds may be temporarily down."
        )

    return warnings


# ── Notifications ─────────────────────────────────────────────────────────────

def _send_email(subject: str, html: str) -> bool:
    if not NOTIFY_PASSWORD:
        print("  ℹ️  NOTIFY_PASSWORD not set — skipping notification.")
        print("     Set GOLD_EMAIL_PASSWORD or NOTIFY_PASSWORD to receive alerts.")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = NOTIFY_EMAIL
        msg["To"]      = NOTIFY_EMAIL
        msg.attach(MIMEText(html, "html"))
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
            s.login(NOTIFY_EMAIL, NOTIFY_PASSWORD)
            s.sendmail(NOTIFY_EMAIL, NOTIFY_EMAIL, msg.as_string())
        print(f"  ✅ Email sent → {NOTIFY_EMAIL}")
        return True
    except smtplib.SMTPAuthenticationError:
        print(f"  ❌ Email auth failed — check NOTIFY_PASSWORD in .env")
        print(f"     Password loaded: {'yes (' + str(len(NOTIFY_PASSWORD)) + ' chars)' if NOTIFY_PASSWORD else 'NO — empty'}")
        return False
    except Exception as e:
        print(f"  ⚠️  Notification failed: {e}")
        return False


def _social_html_block(social_data: dict) -> str:
    """Renders social posts as a copy-paste block for the operator email."""
    tw = social_data.get("twitter", "")
    li = social_data.get("linkedin", "")
    wa = social_data.get("whatsapp", "")
    if not any([tw, li, wa]):
        return ""

    def box(label, icon, content):
        safe = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"""
        <div style="margin:12px 0;">
          <p style="margin:0 0 4px;font-size:12px;font-weight:700;color:#374151;">
            {icon} {label}
          </p>
          <pre style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;
                      padding:12px;font-size:12px;white-space:pre-wrap;
                      font-family:monospace;margin:0;color:#111;">{safe}</pre>
        </div>"""

    blocks = '<h3 style="font-size:14px;color:#374151;margin:20px 0 8px;">📣 Social Posts — Copy &amp; Post</h3>'
    if tw:
        posted = social_data.get("posted_platforms", {}).get("twitter", {})
        label = f"Twitter/X ✅ Auto-posted → {posted.get('url','')}" if posted.get("success") else "Twitter/X (copy &amp; post manually)"
        blocks += box(label, "🐦", tw)
    if li:
        posted = social_data.get("posted_platforms", {}).get("linkedin", {})
        label = "LinkedIn ✅ Auto-posted" if posted.get("success") else "LinkedIn (copy &amp; post manually)"
        blocks += box(label, "💼", li)
    if wa:
        blocks += box("WhatsApp Broadcast (copy &amp; send)", "📱", wa)
    return blocks


def notify_draft_ready(title, gold_price, day_pct, post_type, post_id, warnings, social_data=None, partnership_data=None, monetization_data=None, analytics_data=None):
    arrow = "▲" if day_pct >= 0 else "▼"
    sign  = "+" if day_pct >= 0 else ""
    color = "#16a34a" if day_pct >= 0 else "#dc2626"
    label = post_type.replace("_", " ").title()
    is_live = AUTO_PUBLISH

    warn_html = ""
    if warnings:
        items = "".join(f"<li style='margin:4px 0;color:#713f12;'>{w}</li>" for w in warnings)
        warn_html = f"""
        <div style="background:#fef9c3;border-left:4px solid #eab308;
                    padding:12px 16px;border-radius:4px;margin:14px 0;">
          <strong style="color:#713f12;">⚠️ Warnings — review before sending:</strong>
          <ul style="margin:6px 0 0;padding-left:1.2em;">{items}</ul>
        </div>"""

    if is_live:
        headline    = "🚀 Post Published Live"
        cta_label   = "View Live Post →"
        cta_href    = post_url if 'post_url' in dir() else BEEHIIV_DRAFTS
        footer_note = "This post is now <strong>LIVE</strong> on your website and has been sent to subscribers."
    else:
        headline    = "📬 Draft Ready for Review"
        cta_label   = "Review &amp; Approve Draft →"
        cta_href    = BEEHIIV_DRAFTS
        footer_note = ("This draft was created automatically. It has <strong>NOT</strong> been "
                       "sent to subscribers.<br>Open the draft in Beehiiv, review it, then click Send.")

    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                max-width:520px;margin:0 auto;padding:28px 24px;">
      <p style="margin:0 0 4px;font-size:11px;color:#9ca3af;
                text-transform:uppercase;letter-spacing:.1em;">
        Africa Gold Intelligence · Orchestrator Alert
      </p>
      <h2 style="margin:0 0 20px;font-size:20px;color:#111827;">
        {headline}
      </h2>

      <div style="background:#f9fafb;border:1px solid #e5e7eb;
                  border-radius:8px;padding:16px 18px;margin-bottom:4px;">
        <p style="margin:0 0 6px;"><strong>Post:</strong> {title}</p>
        <p style="margin:0 0 6px;"><strong>Type:</strong> {label}</p>
        <p style="margin:0 0 6px;"><strong>Beehiiv ID:</strong>
          <code style="font-size:12px;">{post_id}</code></p>
        <p style="margin:0;"><strong>Gold:</strong>
          <span style="color:{color};font-weight:700;">
            ${gold_price:,.2f} &nbsp;{arrow} {sign}{day_pct:.2f}%
          </span>
        </p>
      </div>

      {warn_html}

      <a href="{cta_href}"
         style="display:inline-block;background:#1c1917;color:#fff;
                padding:13px 22px;border-radius:8px;text-decoration:none;
                font-weight:700;font-size:14px;margin-top:16px;">
        {cta_label}
      </a>

      <p style="margin:20px 0 0;font-size:11px;color:#9ca3af;line-height:1.6;">
        {footer_note}
      </p>

      {_social_html_block(social_data or {})}

      {(partnership_data or {}).get("html_block", "")}

      {(monetization_data or {}).get("html_block", "")}

      {(analytics_data or {}).get("html_block", "")}

    </div>"""

    subject = f"[AGI] Draft ready · Gold ${gold_price:,.0f} ({sign}{day_pct:.1f}%)"
    ok = _send_email(subject, html)
    print(f"  {'✅ Notification sent.' if ok else '⚠️  Notification skipped (no password).'}")


def notify_failure(stage: str, error: str):
    html = f"""
    <div style="font-family:-apple-system,sans-serif;max-width:520px;
                margin:0 auto;padding:28px 24px;">
      <h2 style="color:#dc2626;margin:0 0 16px;">🚨 AGI Pipeline Failure</h2>
      <p><strong>Stage:</strong> {stage}</p>
      <pre style="background:#f9fafb;padding:14px;border-radius:6px;
                  font-size:11px;overflow:auto;white-space:pre-wrap;">{error[:1200]}</pre>
      <p style="color:#9ca3af;font-size:11px;">
        Full trace in /tmp/agi_post_error.log · Fix and re-run manually.
      </p>
    </div>"""
    _send_email(f"[AGI] ⚠️ Pipeline failure at {stage}", html)


def _send_briefing_email(title, gold_price, day_pct, post_type, free_html, premium_html, warnings, social_data=None, partnership_data=None, monetization_data=None, analytics_data=None):
    """Fallback: email the full briefing content when Beehiiv API is unavailable."""
    sign  = "+" if day_pct >= 0 else ""
    label = post_type.replace("_", " ").title()

    warn_html = ""
    if warnings:
        items = "".join(f"<li style='color:#713f12;margin:4px 0'>{w}</li>" for w in warnings)
        warn_html = f"""
        <div style="background:#fef9c3;border-left:4px solid #eab308;
                    padding:12px 16px;border-radius:4px;margin:0 0 20px;">
          <strong style="color:#713f12;">⚠️ Data warnings:</strong>
          <ul style="margin:6px 0 0;padding-left:1.2em;">{items}</ul>
        </div>"""

    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                max-width:680px;margin:0 auto;padding:28px 24px;">

      <p style="margin:0 0 4px;font-size:11px;color:#9ca3af;
                text-transform:uppercase;letter-spacing:.1em;">
        Africa Gold Intelligence · Daily Briefing
      </p>
      <h2 style="margin:0 0 6px;font-size:22px;color:#111827;">{title}</h2>
      <p style="margin:0 0 20px;font-size:14px;color:#6b7280;">
        Gold <strong style="color:#111">${gold_price:,.2f}</strong>
        &nbsp;<span style="color:{'#16a34a' if day_pct>=0 else '#dc2626'}">
          {sign}{day_pct:.2f}%
        </span>
        &nbsp;·&nbsp;{label}
      </p>

      {warn_html}

      <div style="background:#fef3c7;border:1px solid #fcd34d;border-radius:8px;
                  padding:14px 16px;margin:0 0 24px;font-size:13px;color:#92400e;">
        <strong>📋 Beehiiv API not enabled on your plan.</strong><br>
        Copy the content below and paste it into a new Beehiiv post manually,
        or upgrade your plan at
        <a href="https://app.beehiiv.com/settings/billing" style="color:#92400e;">
          beehiiv.com/settings/billing
        </a>
        to enable auto-draft creation.
      </div>

      <h3 style="font-size:15px;color:#374151;border-bottom:1px solid #e5e7eb;
                 padding-bottom:8px;margin:0 0 16px;">Free Content</h3>
      {free_html}

      <h3 style="font-size:15px;color:#374151;border-bottom:1px solid #e5e7eb;
                 padding-bottom:8px;margin:24px 0 16px;">Premium Content</h3>
      {premium_html}

      <hr style="border:none;border-top:1px solid #e5e7eb;margin:28px 0 16px;">
      <p style="font-size:11px;color:#9ca3af;margin:0;">
        Generated by AGI Orchestrator · Phase 1 Pipeline
      </p>
    </div>"""

    social_block = _social_html_block(social_data or {})
    html = html.replace("</div>", f"{social_block}</div>", 1) if social_block else html

    subject = f"[AGI] Daily Briefing · Gold ${gold_price:,.0f} ({sign}{day_pct:.1f}%)"
    ok = _send_email(subject, html)
    print(f"  {'✅ Briefing emailed successfully.' if ok else '⚠️  Email skipped (NOTIFY_PASSWORD not set).'}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # ── Print log mode ────────────────────────────────────────────────────────
    if PRINT_LOG:
        sep("AGI Run Log")
        print_recent_logs(10)
        return

    run_start = datetime.datetime.now()

    sep("AGI Orchestrator · Phase 1 Pipeline")
    print(f"  Started:   {run_start.strftime('%Y-%m-%d %H:%M:%S')}")
    if DRY_RUN:
        mode_str = "🔬 DRY RUN — no post created"
        gate_str = "N/A"
    elif AUTO_PUBLISH:
        mode_str = "🚀 AUTO-PUBLISH — posts go live immediately"
        gate_str = "⚠️  No human gate — posts published directly to site"
    else:
        mode_str = "📋 DRAFT MODE — post created as draft for review"
        gate_str = "Human review required before any subscriber send"
    print(f"  Mode:      {mode_str}")
    print(f"  Gate:      {gate_str}\n")

    # ── Import agent modules ──────────────────────────────────────────────────
    stage = "import"
    try:
        sys.path.insert(0, str(SCRIPT_DIR))
        sys.path.insert(0, str(SCRIPT_DIR / "agents"))
        sys.path.insert(0, str(SCRIPT_DIR / "distribution"))
        import beehiiv_daily_post as market_agent
    except ImportError as e:
        msg = f"Cannot import beehiiv_daily_post: {e}\nExpected at: {SCRIPT_DIR}"
        print(f"  ❌ {msg}")
        log_run("FAILED", {"stage": stage, "error": msg})
        notify_failure(stage, msg)
        sys.exit(1)

    today      = datetime.datetime.now()
    if _FORCE_POST_TYPE and _FORCE_POST_TYPE in market_agent.POST_TYPE_LABELS:
        post_type  = _FORCE_POST_TYPE
        type_label = market_agent.POST_TYPE_LABELS[post_type]
        print(f"  Post type: {type_label}  [FORCED via --post-type]  ({today.strftime('%A %B %d, %Y')})\n")
    elif _FORCE_POST_TYPE:
        valid = ", ".join(market_agent.POST_TYPE_LABELS.keys())
        print(f"  ⚠️  Unknown --post-type '{_FORCE_POST_TYPE}'. Valid options: {valid}")
        print(f"       Falling back to today's scheduled type.")
        post_type  = market_agent.DAY_TYPES.get(today.weekday(), "aggregator")
        type_label = market_agent.POST_TYPE_LABELS[post_type]
        print(f"  Post type: {type_label}  ({today.strftime('%A %B %d, %Y')})\n")
    else:
        post_type  = market_agent.DAY_TYPES.get(today.weekday(), "aggregator")
        type_label = market_agent.POST_TYPE_LABELS[post_type]
        print(f"  Post type: {type_label}  ({today.strftime('%A %B %d, %Y')})\n")

    # ═════════════════════════════════════════════════════════════════════════
    # AGENT 1 — MARKET INTELLIGENCE
    # ═════════════════════════════════════════════════════════════════════════
    sep("Agent 1 · Market Intelligence")
    stage = "market_intelligence"
    try:
        print("  📊 Prices (Yahoo Finance)...")
        gold   = market_agent.fetch_yfinance(market_agent.GOLD_TICKER)
        silver = market_agent.fetch_yfinance(market_agent.SILVER_TICKER)
        dxy    = market_agent.fetch_yfinance(market_agent.DXY_TICKER)
        sp500  = market_agent.fetch_yfinance(market_agent.SP500_TICKER)
        btc    = market_agent.fetch_yfinance(market_agent.BTC_TICKER)

        if not gold:
            raise RuntimeError(
                "Gold price returned empty — Yahoo Finance may be throttled. "
                "Try again in a few minutes."
            )

        g_price = gold["price"]
        g_pct   = gold.get("day_chg_pct", 0)
        g_sign  = "+" if g_pct >= 0 else ""
        print(f"  Gold:   ${g_price:,.2f}  ({g_sign}{g_pct:.2f}%)  RSI-14: {gold.get('rsi', 'N/A')}")
        if silver: print(f"  Silver: ${silver.get('price', 0):,.2f}")
        if dxy:    print(f"  DXY:    {dxy.get('price', 0):.3f}")
        if sp500:  print(f"  S&P500: ${sp500.get('price', 0):,.0f}")

        print("\n  💱 African FX rates...")
        fx_rates     = market_agent.fetch_fx_rates()
        karat_prices = market_agent.calc_karat_prices(g_price, fx_rates)
        for cur, rate in fx_rates.items():
            sym = market_agent.CURRENCY_SYMBOLS.get(cur, cur)
            k24 = karat_prices.get(cur, {}).get("24K", 0)
            if rate:
                print(f"  USD/{cur}: {rate:.2f}  →  {sym}{k24:,.0f}/g (24K)")

        print("\n  📰 News headlines (RSS)...")
        news = market_agent.fetch_news(max_items=6)
        print(f"  Found {len(news)} relevant headline(s).")
        for n in news:
            print(f"    · [{n['source']}] {n['title'][:70]}...")

        data = {
            "gold": gold, "silver": silver, "dxy": dxy,
            "sp500": sp500, "btc": btc,
            "fx_rates": fx_rates, "karat_prices": karat_prices,
            "news": news,
        }
        print("\n  ✅ Market Intelligence complete.")

    except Exception as e:
        tb = traceback.format_exc()
        print(f"  ❌ Market Intelligence failed:\n{tb}")
        log_run("FAILED", {"stage": stage, "error": str(e)})
        notify_failure(stage, tb)
        sys.exit(1)

    # ─── Anomaly detection ────────────────────────────────────────────────────
    sep("Data Quality Check")
    warnings  = check_data_quality(data)
    criticals = [w for w in warnings if w.startswith("CRITICAL")]

    if not warnings:
        print("  ✅ All checks passed — data looks clean.")
    for w in warnings:
        icon = "❌" if w.startswith("CRITICAL") else "⚠️ "
        print(f"  {icon} {w}")

    if criticals:
        log_run("HALTED", {"stage": "anomaly_detection",
                           "gold_price": g_price, "warnings": warnings})
        notify_failure("anomaly_detection", "\n".join(criticals))
        print("\n  Pipeline halted due to critical data anomaly.")
        sys.exit(1)

    # ═════════════════════════════════════════════════════════════════════════
    # AGENT 1.5 — AFRICA INTELLIGENCE
    # ═════════════════════════════════════════════════════════════════════════
    sep("Agent 1.5 · Africa Intelligence")
    stage = "africa_intelligence"
    africa_data = None
    try:
        import africa_data_agent
        africa_data = africa_data_agent.run(data, today)
        miners   = africa_data.get("miners", {})
        pan      = africa_data.get("pan_african", {})
        seasonal = africa_data.get("seasonal_signals", [])
        print(f"\n  ✅ Africa Intelligence complete.")
        print(f"     Miners tracked:     {len(miners)}")
        if miners:
            avg_m = africa_data.get("avg_margin", 0)
            best  = africa_data.get("top_miner", "")
            print(f"     Avg AISC margin:    ${avg_m:,.0f}/oz")
            print(f"     Best performer:     {best}")
        if pan:
            print(f"     Pan-African margin: ${pan.get('weighted_avg_margin', 0):,.0f}/oz ({pan.get('weighted_margin_pct', 0):.1f}%)")
        if seasonal:
            print(f"     Seasonal signals:   {len(seasonal)} active ({', '.join(s['signal'][:30] for s in seasonal[:2])})")
        africa_news = africa_data.get("africa_news", [])
        print(f"     Africa headlines:   {len(africa_news)}")
    except ImportError:
        print("  ⚠️  africa_data_agent.py not found — skipping Africa intelligence.")
    except Exception as e:
        tb = traceback.format_exc()
        print(f"  ⚠️  Africa Intelligence failed (non-fatal): {e}")
        print(f"     Continuing pipeline without Africa data...")
        africa_data = None

    # ═════════════════════════════════════════════════════════════════════════
    # AGENT 1.6 — CONTRACT TRANSPARENCY & SHADOW ECONOMY
    # ═════════════════════════════════════════════════════════════════════════
    sep("Agent 1.6 · Contract Transparency")
    stage = "contract_transparency"
    contract_data = None
    try:
        import contract_transparency_agent
        contract_data = contract_transparency_agent.run(data, today)
        print(f"\n  ✅ Contract Transparency complete.")
        print(f"     Contracts tracked:    {contract_data.get('contracts_count', 0)}")
        total_paid = contract_data.get("total_royalties_paid", 0)
        total_gap  = contract_data.get("total_gap_usd", 0)
        print(f"     Royalties paid/yr:    ${total_paid/1e6:.0f}M at spot")
        print(f"     Fair-value gap/yr:    ${total_gap/1e6:.0f}M (vs 8% NRGI benchmark)")
        sd  = contract_data.get("shadow_data", {})
        print(f"     Shadow economy:       ~{sd.get('illicit_mid_tonnes',0)}t/yr (${sd.get('illicit_mid_usd_bn',0)}B)")
        alerts = [n for n in contract_data.get("nationalism_alerts", [])
                  if n["status"] in ("nationalised", "renegotiated", "renegotiating")]
        print(f"     Nationalism alerts:   {len(alerts)} active")
        c_news = contract_data.get("contract_news", [])
        print(f"     Contract headlines:   {len(c_news)}")
    except ImportError:
        print("  ⚠️  contract_transparency_agent.py not found — skipping.")
    except Exception as e:
        tb = traceback.format_exc()
        print(f"  ⚠️  Contract Transparency failed (non-fatal): {e}")
        contract_data = None

    # ═════════════════════════════════════════════════════════════════════════
    # AGENT 2 — CONTENT SYNTHESIS
    # ═════════════════════════════════════════════════════════════════════════
    sep("Agent 2 · Content Synthesis")
    stage = "content_synthesis"
    try:
        print(f"  ✍️  Building {type_label}...")
        free_html    = market_agent.build_free_content(data, post_type, today, africa_data, contract_data)
        premium_html = market_agent.build_premium_content(post_type, data, today, africa_data, contract_data)

        rsi_str  = f" · RSI {gold.get('rsi')}" if gold.get("rsi") else ""
        zar_str  = (f"R{karat_prices.get('ZAR', {}).get('24K', 0):,.0f}/g"
                    if "ZAR" in karat_prices else "")
        title    = f"Gold Market Briefing | {today.strftime('%a %b %d, %Y')}"
        subtitle = (f"XAU/USD at ${g_price:,.2f} · DXY {dxy.get('price', 0):.2f}"
                    f"{rsi_str} · {zar_str} + full {type_label} inside")
        preview  = (f"Gold {g_sign}{g_pct:.2f}% today at ${g_price:,.2f}. "
                    f"Full {type_label} for Africa subscribers inside.")

        print(f"  Title:    {title}")
        print(f"  Subtitle: {subtitle[:75]}...")
        print(f"  Free HTML:    {len(free_html):,} chars")
        print(f"  Premium HTML: {len(premium_html):,} chars")
        print("  ✅ Content Synthesis complete.")

    except Exception as e:
        tb = traceback.format_exc()
        print(f"  ❌ Content Synthesis failed:\n{tb}")
        log_run("FAILED", {"stage": stage, "error": str(e)})
        notify_failure(stage, tb)
        sys.exit(1)

    # ═════════════════════════════════════════════════════════════════════════
    # AGENT 4 — SEO & DISCOVERABILITY
    # ═════════════════════════════════════════════════════════════════════════
    sep("Agent 4 · SEO & Discoverability")
    stage = "seo"
    try:
        import seo_agent
        seo_data = seo_agent.run(post_type, data, today, title)

        print(f"  🔗 Slug:        {seo_data['slug']}")
        print(f"  🏷️  Tags ({len(seo_data['tags'])}):   {', '.join(seo_data['tags'][:6])}{'...' if len(seo_data['tags']) > 6 else ''}")
        print(f"  📝 Meta ({len(seo_data['meta_description'])} chars): {seo_data['meta_description'][:80]}...")
        if seo_data["internal_links"]:
            print(f"  🔁 Internal links: {len(seo_data['internal_links'])} suggestion(s)")
            for lnk in seo_data["internal_links"]:
                print(f"       → {lnk['type']}: {lnk['url']}")

        # Inject JSON-LD into the free HTML (before </body> if present, else append)
        if "</body>" in free_html:
            free_html = free_html.replace("</body>", seo_data["json_ld_html"] + "\n</body>")
        else:
            free_html = free_html + "\n" + seo_data["json_ld_html"]

        print("  ✅ SEO & Discoverability complete.")

    except ImportError:
        print("  ⚠️  seo_agent.py not found — skipping SEO enrichment.")
        seo_data = {"slug": None, "tags": ["gold", "africa", "markets"],
                    "meta_description": preview, "internal_links": []}
    except Exception as e:
        tb = traceback.format_exc()
        print(f"  ⚠️  SEO agent failed (non-fatal): {e}")
        seo_data = {"slug": None, "tags": ["gold", "africa", "markets"],
                    "meta_description": preview, "internal_links": []}

    # ─── Dry run: save previews and exit ──────────────────────────────────────
    if DRY_RUN:
        sep("Dry Run · Saving Previews")
        fp = Path("/tmp/agi_preview_free.html")
        pp = Path("/tmp/agi_preview_premium.html")
        fp.write_text(free_html)
        pp.write_text(premium_html)
        print(f"  Free content    → {fp}")
        print(f"  Premium content → {pp}")

        # Generate LinkedIn post even in dry run so it can be previewed
        sep("LinkedIn · Post Generator (dry run)")
        try:
            import linkedin_post as li_agent
            li_result = li_agent.run(data, today, post_type)
            if li_result.get("status") == "ok":
                print(f"  ✅ LinkedIn post saved → {li_result['pending_file']}")
            else:
                print(f"  ⚠️  LinkedIn post generator warning: {li_result.get('error','unknown')}")
        except ImportError:
            print("  ⚠️  linkedin_post.py not found — skipping LinkedIn preview.")
        except Exception as e:
            print(f"  ⚠️  LinkedIn post generator failed (non-fatal): {e}")

        elapsed = (datetime.datetime.now() - run_start).total_seconds()
        log_run("DRY_RUN", {
            "post_type": post_type, "gold_price": round(g_price, 2),
            "day_pct": round(g_pct, 2), "elapsed_s": round(elapsed, 1),
            "warnings": warnings,
        })
        sep("Done")
        print(f"  Dry run complete in {elapsed:.1f}s. No post created.\n")
        return

    # ═════════════════════════════════════════════════════════════════════════
    # AGENT 3 — DISTRIBUTION  (Human Oversight Gate: always draft)
    # ═════════════════════════════════════════════════════════════════════════
    sep("Agent 3 · Distribution")
    stage      = "distribution"
    post_id    = None
    post_url   = ""       # real Beehiiv web_url — only set when post is created
    beehiiv_ok = False

    # ── Method 1: Beehiiv V2 API (requires Enterprise plan) ───────────────────
    if not market_agent.BEEHIIV_API_KEY:
        print("  ⚠️  BEEHIIV_API_KEY not set — skipping API, trying browser automation.")
    else:
        try:
            action_label = "PUBLISHING live post" if AUTO_PUBLISH else "Creating DRAFT post"
            print(f"  📡 Trying Beehiiv API: {action_label}...")
            result  = market_agent.beehiiv_create_post(
                title=title, subtitle=subtitle,
                email_subject=title, preview_text=seo_data.get("meta_description", preview),
                free_html=free_html, premium_html=premium_html,
                publish_type=PUBLISH_TYPE,
                slug=seo_data.get("slug"),
                content_tags=seo_data.get("tags"),
            )
            post_id    = result.get("data", {}).get("id", "unknown")
            post_url   = result.get("data", {}).get("web_url", "")
            beehiiv_ok = True
            status_label = "✅ Published live" if AUTO_PUBLISH else "✅ Draft created"
            print(f"  {status_label} via API  —  ID: {post_id}")
            if post_url:
                print(f"     Web URL: {post_url}")

        except Exception as e:
            err_str = str(e)
            if "403" in err_str or "SEND_API_DISABLED" in err_str or "not enabled" in err_str.lower():
                print("  ⚠️  Beehiiv API requires Enterprise plan — trying browser automation...")
            else:
                print(f"  ⚠️  Beehiiv API error: {err_str[:120]} — trying browser automation...")

    # ── Method 2: Browser automation (works on any Beehiiv plan) ──────────────
    if not beehiiv_ok:
        try:
            import beehiiv_browser
            br_result  = beehiiv_browser.publish_post(
                title        = title,
                subtitle     = subtitle,
                free_html    = free_html,
                premium_html = premium_html,
                publish_type = PUBLISH_TYPE,
                slug         = seo_data.get("slug"),
                tags         = seo_data.get("tags"),
            )
            post_id    = br_result.get("post_id", "browser-post")
            post_url   = br_result.get("post_url", "")
            beehiiv_ok = True
            print(f"  ✅ Post created via browser automation")

        except ImportError:
            print("  ⚠️  beehiiv_browser.py not found — falling back to email delivery.")
        except RuntimeError as e:
            err_str = str(e)
            if "not installed" in err_str.lower() or "playwright" in err_str.lower():
                print(f"  ⚠️  Playwright not installed — falling back to email delivery.")
                print(f"       To enable browser automation, run:")
                print(f"       pip install playwright --break-system-packages && playwright install chromium")
            elif "BEEHIIV_EMAIL" in err_str or "BEEHIIV_PASSWORD" in err_str:
                print(f"  ⚠️  Browser login credentials not set — falling back to email delivery.")
                print(f"       Add BEEHIIV_EMAIL and BEEHIIV_PASSWORD to your .env file.")
            else:
                print(f"  ⚠️  Browser automation failed: {err_str[:150]}")
                print(f"       Falling back to email delivery.")
        except Exception as e:
            print(f"  ⚠️  Browser automation error: {str(e)[:150]}")
            print(f"       Falling back to email delivery.")

    # ── LinkedIn Post Generator (runs after Beehiiv publish) ──────────────────
    sep("LinkedIn · Post Generator")
    linkedin_result = {"status": "skipped", "char_count": 0, "pending_file": ""}
    try:
        import linkedin_post as li_agent
        linkedin_result = li_agent.run(data, today, post_type)
        if linkedin_result.get("status") == "ok":
            print(f"  ✅ LinkedIn post saved → {linkedin_result['pending_file']}")
        else:
            print(f"  ⚠️  LinkedIn post generator warning: {linkedin_result.get('error','unknown')}")
    except ImportError:
        print("  ⚠️  linkedin_post.py not found — skipping LinkedIn post generation.")
    except Exception as e:
        print(f"  ⚠️  LinkedIn post generator failed (non-fatal): {e}")

    # ═════════════════════════════════════════════════════════════════════════
    # AGENT 5 — SOCIAL AMPLIFICATION
    # ═════════════════════════════════════════════════════════════════════════
    sep("Agent 5 · Social Amplification")
    stage = "social"
    try:
        import social_agent
        social_data = social_agent.run(post_type, data, today, seo_data, post_url)
        print("  ✅ Social Amplification complete.")
    except ImportError:
        print("  ⚠️  social_agent.py not found — skipping social posts.")
        social_data = {"twitter": "", "linkedin": "", "whatsapp": "", "posted_platforms": {}}
    except Exception as e:
        print(f"  ⚠️  Social agent failed (non-fatal): {e}")
        social_data = {"twitter": "", "linkedin": "", "whatsapp": "", "posted_platforms": {}}

    # ═════════════════════════════════════════════════════════════════════════
    # AGENT 6 — PARTNERSHIP OUTREACH
    # ═════════════════════════════════════════════════════════════════════════
    sep("Agent 6 · Partnership Outreach")
    try:
        import partnership_agent
        partnership_data = partnership_agent.run(data, today)
        print("  ✅ Partnership Outreach complete.")
    except ImportError:
        print("  ⚠️  partnership_agent.py not found — skipping.")
        partnership_data = {"drafts": [], "html_block": "", "contacts_due": 0}
    except Exception as e:
        print(f"  ⚠️  Partnership agent failed (non-fatal): {e}")
        partnership_data = {"drafts": [], "html_block": "", "contacts_due": 0}

    # ═════════════════════════════════════════════════════════════════════════
    # AGENT 7 — MONETIZATION OPTIMIZER
    # ═════════════════════════════════════════════════════════════════════════
    sep("Agent 7 · Monetization Optimizer")
    try:
        import monetization_agent
        monetization_data = monetization_agent.run(post_type, data, today)

        # Inject CTA banner into free content if strategy calls for it
        banner = monetization_data.get("cta", {}).get("in_post_banner", "")
        if banner:
            # Insert banner before the last </div> in free content
            if "</div>" in free_html:
                insert_pos = free_html.rfind("</div>")
                free_html  = free_html[:insert_pos] + banner + free_html[insert_pos:]
            else:
                free_html += banner

        print("  ✅ Monetization Optimizer complete.")
    except ImportError:
        print("  ⚠️  monetization_agent.py not found — skipping.")
        monetization_data = {"score": 0, "strategy": "none", "cta": {}, "html_block": ""}
    except Exception as e:
        print(f"  ⚠️  Monetization agent failed (non-fatal): {e}")
        monetization_data = {"score": 0, "strategy": "none", "cta": {}, "html_block": ""}

    # ═════════════════════════════════════════════════════════════════════════
    # AGENT 8 — ANALYTICS & REPORTING
    # ═════════════════════════════════════════════════════════════════════════
    sep("Agent 8 · Analytics & Reporting")
    try:
        import analytics_agent
        analytics_data = analytics_agent.run(post_type, data, today)
        print("  ✅ Analytics & Reporting complete.")
    except ImportError:
        print("  ⚠️  analytics_agent.py not found — skipping.")
        analytics_data = {"html_block": ""}
    except Exception as e:
        print(f"  ⚠️  Analytics agent failed (non-fatal): {e}")
        analytics_data = {"html_block": ""}

    # ═════════════════════════════════════════════════════════════════════════
    # HUMAN OVERSIGHT GATE — Notify operator
    # ═════════════════════════════════════════════════════════════════════════
    sep("Human Oversight Gate" if not AUTO_PUBLISH else "Notification")
    if beehiiv_ok:
        if AUTO_PUBLISH:
            print("  📬 Notifying operator that post is LIVE...")
        else:
            print("  📬 Notifying operator that draft is ready for review...")
        notify_draft_ready(title, g_price, g_pct, post_type, post_id, warnings,
                           social_data, partnership_data, monetization_data, analytics_data)
    else:
        print("  📬 Emailing full briefing content for manual review...")
        _send_briefing_email(title, g_price, g_pct, post_type, free_html, premium_html,
                             warnings, social_data, partnership_data, monetization_data, analytics_data)

    # ─── Log success ──────────────────────────────────────────────────────────
    elapsed = (datetime.datetime.now() - run_start).total_seconds()
    _cd = contract_data or {}
    _sd = _cd.get("shadow_data", {})
    _nationalism_active = [
        n for n in _cd.get("nationalism_alerts", [])
        if n.get("status") in ("nationalised", "renegotiated", "renegotiating")
    ]
    log_run("SUCCESS", {
        "post_type":           post_type,
        "post_id":             post_id or "email-delivery",
        "post_url":            post_url or "",
        "gold_price":          round(g_price, 2),
        "day_pct":             round(g_pct, 2),
        "headlines":           len(news),
        # Africa Intelligence (Agent 1.5)
        "africa_miners":       len((africa_data or {}).get("miners", {})),
        "africa_headlines":    len((africa_data or {}).get("africa_news", [])),
        "africa_seasonal":     len((africa_data or {}).get("seasonal_signals", [])),
        "pan_african_margin":  (africa_data or {}).get("pan_african", {}).get("weighted_avg_margin", 0),
        # Contract Transparency (Agent 1.6)
        "contracts_tracked":   _cd.get("contracts_count", 0),
        "royalty_gap_usd_m":   round(_cd.get("total_gap_usd", 0) / 1e6, 1),
        "shadow_tonnes":       _sd.get("illicit_mid_tonnes", 0),
        "shadow_value_bn":     _sd.get("illicit_mid_usd_bn", 0),
        "nationalism_alerts":  len(_nationalism_active),
        "contract_headlines":  len(_cd.get("contract_news", [])),
        # Pipeline metadata
        "warnings":            warnings,
        "elapsed_s":           round(elapsed, 1),
        "beehiiv_used":        beehiiv_ok,
        "publish_type":        PUBLISH_TYPE if beehiiv_ok else "email-fallback",
        "outreach_drafts":     len(partnership_data.get("drafts", [])),
        "upsell_score":        monetization_data.get("score", 0),
        "upsell_strategy":     monetization_data.get("strategy", "none"),
    })

    sep("Pipeline Complete")
    # Base pipeline: agents 1, 2, 3, 4, 5, 6, 7, 8 = 8 agents
    # Agent 1.5 (Africa Intelligence) and 1.6 (Contract Transparency) are optional extras
    agent_count = 8
    if africa_data is not None:
        agent_count += 1   # Agent 1.5
    if contract_data is not None:
        agent_count += 1   # Agent 1.6
    print(f"  ✅ All {agent_count} agents ran successfully in {elapsed:.1f}s")
    if beehiiv_ok:
        if AUTO_PUBLISH:
            print(f"  🚀 Post is LIVE on your website!")
            if post_url:
                print(f"     → {post_url}")
        else:
            print(f"  📋 Draft is waiting in Beehiiv for your review:")
            print(f"     → {BEEHIIV_DRAFTS}")
            print(f"     💡 To auto-publish without reviewing, use: python3 orchestrator.py --publish")
    else:
        print(f"  📬 Full briefing emailed to {NOTIFY_EMAIL} for manual review.")
        print(f"\n  ⚠️  BEEHIIV API NOT CONNECTED — posts are not appearing on your site.")
        print(f"     Run the diagnostic to find the fix:")
        print(f"     → python3 beehiiv_api_check.py")
    print(f"  📊 Run log: {LOG_FILE}")
    print(f"  📋 Print log: python3 orchestrator.py --log\n")


if __name__ == "__main__":
    main()
