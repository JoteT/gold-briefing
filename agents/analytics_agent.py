#!/usr/bin/env python3
"""
analytics_agent.py — Africa Gold Intelligence — Tier 3: Analytics & Reporting Agent
====================================================================================
Aggregates data from all 7 agent logs and delivers a weekly performance report
every Sunday morning, plus a daily metrics snapshot in the oversight email.

Weekly report covers:
  - Pipeline health (success rate, failures, avg elapsed time)
  - Content performance (posts by type, gold price range, avg daily move)
  - SEO trends (top tags, avg tag count, slug history)
  - Social amplification (posts generated, platforms auto-posted)
  - Outreach pipeline (contacts approached, orgs, types, cooldown status)
  - Monetization (avg opportunity score, strategies used, pricing windows)
  - 30-day trend sparklines (ASCII, email-safe)

Logs read:
  run_log.jsonl          — orchestrator pipeline runs
  seo_log.jsonl          — SEO metadata per post
  social_log.jsonl       — social posts generated/posted
  outreach_log.jsonl     — partnership outreach drafts
  monetization_log.jsonl — monetization scores and strategies

Usage:
  python3 analytics_agent.py           # full weekly report → email
  python3 analytics_agent.py --report  # same, force regardless of day
  python3 analytics_agent.py --print   # print report to terminal

Called by orchestrator.py:
  - Daily: generates a compact metrics snapshot for the oversight email
  - Sunday: generates and emails the full weekly report
"""

import json
import os
import datetime
import smtplib
import ssl
import sys
from pathlib import Path
from collections import Counter
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── Config ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR       = Path(__file__).parent
LOGS = {
    "run":          SCRIPT_DIR.parent / "logs" / "run_log.jsonl",
    "seo":          SCRIPT_DIR.parent / "logs" / "seo_log.jsonl",
    "social":       SCRIPT_DIR.parent / "logs" / "social_log.jsonl",
    "outreach":     SCRIPT_DIR.parent / "logs" / "outreach_log.jsonl",
    "monetization": SCRIPT_DIR.parent / "logs" / "monetization_log.jsonl",
}

NOTIFY_EMAIL    = os.environ.get("NOTIFY_EMAIL", "jote.taddese@gmail.com")
NOTIFY_PASSWORD = os.environ.get("NOTIFY_PASSWORD", os.environ.get("GOLD_EMAIL_PASSWORD", ""))

# Load .env if present
_env_file = SCRIPT_DIR.parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            _k, _v = _k.strip(), _v.strip()
            if _v and "REPLACE_WITH" not in _v and "your_" not in _v.lower():
                os.environ[_k] = _v
    NOTIFY_EMAIL    = os.environ.get("NOTIFY_EMAIL", NOTIFY_EMAIL)
    NOTIFY_PASSWORD = os.environ.get("NOTIFY_PASSWORD", NOTIFY_PASSWORD)


# ── Log reader ─────────────────────────────────────────────────────────────────

def read_log(name: str, days: int = 7) -> list:
    """Read last N days of records from a JSONL log file."""
    path = LOGS.get(name)
    if not path or not path.exists():
        return []
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    records = []
    try:
        for line in path.read_text().strip().splitlines():
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                ts  = datetime.datetime.fromisoformat(rec.get("ts", "1970-01-01"))
                if ts >= cutoff:
                    records.append(rec)
            except Exception:
                continue
    except Exception:
        pass
    return records


# ── Metric calculators ─────────────────────────────────────────────────────────

def pipeline_metrics(days: int = 7) -> dict:
    runs     = read_log("run", days)
    total    = len(runs)
    success  = [r for r in runs if r.get("status") == "SUCCESS"]
    failed   = [r for r in runs if r.get("status") == "FAILED"]
    halted   = [r for r in runs if r.get("status") == "HALTED"]
    dry_runs = [r for r in runs if r.get("status") == "DRY_RUN"]

    success_rate = round(len(success) / total * 100) if total else 0
    avg_elapsed  = (
        round(sum(r.get("elapsed_s", 0) for r in success) / len(success), 1)
        if success else 0
    )
    post_types   = Counter(r.get("post_type", "unknown") for r in success)
    gold_prices  = [r.get("gold_price", 0) for r in success if r.get("gold_price")]
    avg_price    = round(sum(gold_prices) / len(gold_prices), 2) if gold_prices else 0
    price_range  = (round(min(gold_prices), 2), round(max(gold_prices), 2)) if gold_prices else (0, 0)
    avg_pct      = (
        round(sum(r.get("day_pct", 0) for r in success) / len(success), 2)
        if success else 0
    )
    # Consecutive success streak
    streak = 0
    for r in reversed(runs):
        if r.get("status") == "SUCCESS":
            streak += 1
        else:
            break

    return {
        "total": total, "success": len(success), "failed": len(failed),
        "halted": len(halted), "dry_runs": len(dry_runs),
        "success_rate": success_rate, "avg_elapsed_s": avg_elapsed,
        "post_types": dict(post_types), "avg_gold_price": avg_price,
        "gold_price_range": price_range, "avg_day_pct": avg_pct,
        "streak": streak,
    }


def seo_metrics(days: int = 7) -> dict:
    recs = read_log("seo", days)
    if not recs:
        return {"total": 0}
    all_tags = []
    for r in recs:
        all_tags.extend(r.get("tags", []))
    tag_freq    = Counter(all_tags)
    top_tags    = tag_freq.most_common(8)
    avg_tags    = round(sum(r.get("tag_count", 0) for r in recs) / len(recs), 1)
    post_types  = Counter(r.get("post_type") for r in recs)
    return {
        "total": len(recs), "top_tags": top_tags,
        "avg_tags_per_post": avg_tags, "post_types": dict(post_types),
        "unique_slugs": len(set(r.get("slug","") for r in recs)),
    }


def social_metrics(days: int = 7) -> dict:
    recs = read_log("social", days)
    if not recs:
        return {"total": 0}
    auto_twitter  = sum(1 for r in recs if r.get("posted", {}).get("twitter", {}).get("success"))
    auto_linkedin = sum(1 for r in recs if r.get("posted", {}).get("linkedin", {}).get("success"))
    avg_tw_chars  = round(sum(r.get("twitter_chars", 0) for r in recs) / len(recs))
    post_types    = Counter(r.get("post_type") for r in recs)
    return {
        "total": len(recs), "auto_twitter": auto_twitter,
        "auto_linkedin": auto_linkedin, "manual_posts": len(recs) - auto_twitter,
        "avg_twitter_chars": avg_tw_chars, "post_types": dict(post_types),
    }


def outreach_metrics(days: int = 7) -> dict:
    recs = read_log("outreach", days)
    if not recs:
        return {"total": 0}
    orgs    = Counter(r.get("org") for r in recs)
    types   = Counter(r.get("type", "unknown") for r in recs)  # from partners.json
    return {
        "total": len(recs), "unique_orgs": len(orgs),
        "top_orgs": orgs.most_common(5),
        "by_type": dict(types),
    }


def monetization_metrics(days: int = 7) -> dict:
    recs = read_log("monetization", days)
    if not recs:
        return {"total": 0}
    scores     = [r.get("score", 0) for r in recs]
    strategies = Counter(r.get("strategy") for r in recs)
    windows    = Counter(r.get("pricing_window") for r in recs)
    avg_score  = round(sum(scores) / len(scores)) if scores else 0
    peak_score = max(scores) if scores else 0
    return {
        "total": len(recs), "avg_score": avg_score, "peak_score": peak_score,
        "strategies": dict(strategies), "pricing_windows": dict(windows),
        "hard_upsells": strategies.get("hard_upsell", 0),
        "promos": strategies.get("promo", 0),
    }


# ── Sparkline (ASCII, email-safe) ──────────────────────────────────────────────

def sparkline(values: list, width: int = 14) -> str:
    """Generate an ASCII bar sparkline from a list of numbers."""
    bars = " ▁▂▃▄▅▆▇█"
    if not values or all(v == 0 for v in values):
        return "─" * width
    mn, mx = min(values), max(values)
    span   = mx - mn or 1
    result = ""
    for v in values[-width:]:
        idx = int((v - mn) / span * (len(bars) - 1))
        result += bars[idx]
    return result


def _daily_gold_prices(days: int = 14) -> list:
    """Extract daily gold prices from run_log for sparkline."""
    runs   = read_log("run", days)
    prices = [r.get("gold_price", 0) for r in runs if r.get("gold_price")]
    return prices


def _daily_scores(days: int = 14) -> list:
    recs   = read_log("monetization", days)
    return [r.get("score", 0) for r in recs]


# ── Daily snapshot (compact, for oversight email) ──────────────────────────────

def build_daily_snapshot() -> str:
    """Compact HTML metrics block for the daily oversight email."""
    pm  = pipeline_metrics(7)
    mm  = monetization_metrics(7)
    om  = outreach_metrics(7)
    prices = _daily_gold_prices(14)
    scores = _daily_scores(14)

    spark_price = sparkline(prices)
    spark_score = sparkline(scores)

    return f"""
    <h3 style="font-size:14px;color:#374151;margin:24px 0 8px;">
      📊 7-Day Analytics Snapshot
    </h3>
    <table style="width:100%;border-collapse:collapse;font-size:12px;">
      <tr style="background:#f9fafb;">
        <td style="padding:8px 10px;color:#6b7280;border:1px solid #e5e7eb;">Pipeline runs</td>
        <td style="padding:8px 10px;font-weight:600;border:1px solid #e5e7eb;">
          {pm.get('success',0)}/{pm.get('total',0)} successful
          &nbsp;·&nbsp; {pm.get('success_rate',0)}% success rate
          &nbsp;·&nbsp; streak: {pm.get('streak',0)}d
        </td>
      </tr>
      <tr>
        <td style="padding:8px 10px;color:#6b7280;border:1px solid #e5e7eb;">Gold (14d)</td>
        <td style="padding:8px 10px;font-weight:600;border:1px solid #e5e7eb;font-family:monospace;">
          {spark_price}&nbsp; avg ${pm.get('avg_gold_price',0):,.0f}
        </td>
      </tr>
      <tr style="background:#f9fafb;">
        <td style="padding:8px 10px;color:#6b7280;border:1px solid #e5e7eb;">Upsell scores (14d)</td>
        <td style="padding:8px 10px;font-weight:600;border:1px solid #e5e7eb;font-family:monospace;">
          {spark_score}&nbsp; avg {mm.get('avg_score',0)}/100
        </td>
      </tr>
      <tr>
        <td style="padding:8px 10px;color:#6b7280;border:1px solid #e5e7eb;">Outreach (7d)</td>
        <td style="padding:8px 10px;font-weight:600;border:1px solid #e5e7eb;">
          {om.get('total',0)} draft(s) across {om.get('unique_orgs',0)} org(s)
        </td>
      </tr>
    </table>
    <p style="margin:6px 0 0;font-size:11px;color:#9ca3af;">
      Full weekly report delivered every Sunday · run
      <code>python3 analytics_agent.py --report</code> to generate now
    </p>"""


# ── Full weekly report ─────────────────────────────────────────────────────────

def build_weekly_report_html(today: datetime.datetime) -> str:
    week_start = (today - datetime.timedelta(days=7)).strftime("%b %d")
    week_end   = today.strftime("%b %d, %Y")

    pm  = pipeline_metrics(7)
    sm  = seo_metrics(7)
    sc  = social_metrics(7)
    om  = outreach_metrics(7)
    mm  = monetization_metrics(7)

    prices = _daily_gold_prices(7)
    scores = _daily_scores(7)

    # Helpers
    def stat(label, value, sub=""):
        return f"""
        <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;
                    padding:14px 16px;margin:8px 0;">
          <p style="margin:0 0 2px;font-size:11px;color:#9ca3af;text-transform:uppercase;
                    letter-spacing:.06em;">{label}</p>
          <p style="margin:0;font-size:22px;font-weight:800;color:#111;">{value}</p>
          {"<p style='margin:2px 0 0;font-size:12px;color:#6b7280;'>"+sub+"</p>" if sub else ""}
        </div>"""

    def section(title, icon, content):
        return f"""
        <div style="margin:28px 0 0;">
          <h3 style="font-size:15px;color:#374151;border-bottom:2px solid #e5e7eb;
                     padding-bottom:8px;margin:0 0 12px;">
            {icon} {title}
          </h3>
          {content}
        </div>"""

    def kv_table(rows):
        row_parts = []
        for i, (k, v) in enumerate(rows):
            bg = "style=\"background:#f9fafb;\"" if i % 2 == 0 else ""
            row_parts.append(
                f"<tr {bg}>"
                f"<td style='padding:7px 10px;color:#6b7280;font-size:12px;border:1px solid #e5e7eb;'>{k}</td>"
                f"<td style='padding:7px 10px;font-weight:600;font-size:12px;border:1px solid #e5e7eb;'>{v}</td>"
                f"</tr>"
            )
        cells = "".join(row_parts)
        return f"<table style='width:100%;border-collapse:collapse;'>{cells}</table>"

    # ── Section: Pipeline ──
    pt_breakdown = " · ".join(f"{t}: {c}" for t, c in pm.get("post_types", {}).items())
    pipeline_html = kv_table([
        ("Runs", f"{pm.get('total',0)} total"),
        ("Success / Failed / Halted",
         f"{pm.get('success',0)} / {pm.get('failed',0)} / {pm.get('halted',0)}"),
        ("Success rate", f"{pm.get('success_rate',0)}%"),
        ("Avg run time", f"{pm.get('avg_elapsed_s',0)}s"),
        ("Current streak", f"{pm.get('streak',0)} consecutive successes"),
        ("Post types this week", pt_breakdown or "—"),
        ("Gold price (avg)", f"${pm.get('avg_gold_price',0):,.2f}"),
        ("Gold price (range)", f"${pm.get('gold_price_range',(0,0))[0]:,.2f} – ${pm.get('gold_price_range',(0,0))[1]:,.2f}"),
        ("Avg daily move", f"{pm.get('avg_day_pct',0):+.2f}%"),
        ("Gold 7d sparkline", f"<span style='font-family:monospace;font-size:14px;'>{sparkline(prices)}</span>"),
    ])

    # ── Section: SEO ──
    top_tags_str = ", ".join(f"{t} ({c})" for t, c in sm.get("top_tags", [])[:6])
    seo_html = kv_table([
        ("Posts enriched", str(sm.get("total", 0))),
        ("Avg tags per post", str(sm.get("avg_tags_per_post", 0))),
        ("Unique slugs", str(sm.get("unique_slugs", 0))),
        ("Top tags this week", top_tags_str or "—"),
    ])

    # ── Section: Social ──
    social_html = kv_table([
        ("Posts generated", str(sc.get("total", 0))),
        ("Auto-posted (Twitter/X)", str(sc.get("auto_twitter", 0))),
        ("Auto-posted (LinkedIn)", str(sc.get("auto_linkedin", 0))),
        ("Manual copy posts", str(sc.get("manual_posts", 0))),
        ("Avg tweet length", f"{sc.get('avg_twitter_chars',0)} chars"),
    ])

    # ── Section: Outreach ──
    top_orgs_str = ", ".join(o for o, _ in om.get("top_orgs", [])[:5])
    by_type_str  = " · ".join(f"{t}: {c}" for t, c in om.get("by_type", {}).items())
    outreach_html = kv_table([
        ("Drafts prepared", str(om.get("total", 0))),
        ("Unique organisations", str(om.get("unique_orgs", 0))),
        ("Top organisations", top_orgs_str or "—"),
        ("By contact type", by_type_str or "—"),
    ])

    # ── Section: Monetization ──
    strats_str  = " · ".join(f"{s}: {c}" for s, c in mm.get("strategies", {}).items())
    windows_str = " · ".join(f"{w}: {c}" for w, c in mm.get("pricing_windows", {}).items())
    monet_html = kv_table([
        ("Days scored", str(mm.get("total", 0))),
        ("Avg opportunity score", f"{mm.get('avg_score',0)}/100"),
        ("Peak score", f"{mm.get('peak_score',0)}/100"),
        ("Score 7d sparkline", f"<span style='font-family:monospace;font-size:14px;'>{sparkline(scores)}</span>"),
        ("Strategies used", strats_str or "—"),
        ("Hard upsells sent", str(mm.get("hard_upsells", 0))),
        ("Promo offers sent", str(mm.get("promos", 0))),
        ("Pricing windows", windows_str or "—"),
    ])

    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                max-width:640px;margin:0 auto;padding:32px 24px;">

      <p style="margin:0 0 4px;font-size:11px;color:#9ca3af;
                text-transform:uppercase;letter-spacing:.1em;">
        Africa Gold Intelligence · Weekly Analytics Report
      </p>
      <h1 style="margin:0 0 4px;font-size:24px;color:#111;">
        📊 Week of {week_start} – {week_end}
      </h1>
      <p style="margin:0 0 28px;font-size:14px;color:#6b7280;">
        Automated report from your 7-agent pipeline
      </p>

      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:24px;">
        {stat("Pipeline Success", f"{pm.get('success_rate',0)}%",
               f"{pm.get('success',0)} of {pm.get('total',0)} runs")}
        {stat("Avg Upsell Score", f"{mm.get('avg_score',0)}/100",
               f"peak {mm.get('peak_score',0)}")}
        {stat("Outreach Drafts", str(om.get('total',0)),
               f"{om.get('unique_orgs',0)} organisations")}
      </div>

      {section("Pipeline & Content", "🔄", pipeline_html)}
      {section("SEO & Discoverability", "🔍", seo_html)}
      {section("Social Amplification", "📣", social_html)}
      {section("Partnership Outreach", "🤝", outreach_html)}
      {section("Monetization Performance", "💰", monet_html)}

      <hr style="border:none;border-top:1px solid #e5e7eb;margin:32px 0 16px;">
      <p style="font-size:11px;color:#9ca3af;margin:0;">
        Generated by AGI Analytics Agent · Report covers {week_start} – {week_end}<br>
        Run <code>python3 analytics_agent.py --report</code> any time for an ad-hoc report.
      </p>
    </div>"""


# ── Email sender ───────────────────────────────────────────────────────────────

def send_weekly_report(html: str, today: datetime.datetime) -> bool:
    if not NOTIFY_PASSWORD:
        print("  ⚠️  NOTIFY_PASSWORD not set — printing report to terminal instead.")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[AGI] Weekly Report — {today.strftime('%b %d, %Y')}"
        msg["From"]    = NOTIFY_EMAIL
        msg["To"]      = NOTIFY_EMAIL
        msg.attach(MIMEText(html, "html"))
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
            s.login(NOTIFY_EMAIL, NOTIFY_PASSWORD)
            s.sendmail(NOTIFY_EMAIL, NOTIFY_EMAIL, msg.as_string())
        return True
    except Exception as e:
        print(f"  ⚠️  Failed to send weekly report: {e}")
        return False


# ── Main entry point ───────────────────────────────────────────────────────────

def run(post_type: str, data: dict, today: datetime.datetime) -> dict:
    """
    Called by orchestrator.py on every run.

    - Daily: returns compact snapshot HTML for the oversight email
    - Sunday: also emails the full weekly report
    Returns analytics_data dict with html_block.
    """
    is_sunday       = today.weekday() == 6
    force_report    = "--report" in sys.argv
    print_mode      = "--print" in sys.argv

    daily_html = build_daily_snapshot()

    # Full weekly report on Sundays (or when forced)
    if is_sunday or force_report:
        print("  📊 Sunday — generating full weekly report...")
        report_html = build_weekly_report_html(today)

        if print_mode:
            print("\n" + "="*60)
            print("  WEEKLY REPORT (HTML truncated for terminal)")
            print("="*60)
            # Print a text summary instead
            pm = pipeline_metrics(7)
            mm = monetization_metrics(7)
            om = outreach_metrics(7)
            print(f"  Pipeline: {pm.get('success',0)}/{pm.get('total',0)} successful ({pm.get('success_rate',0)}%)")
            print(f"  Avg upsell score: {mm.get('avg_score',0)}/100 | Peak: {mm.get('peak_score',0)}")
            print(f"  Outreach: {om.get('total',0)} drafts, {om.get('unique_orgs',0)} orgs")
        else:
            ok = send_weekly_report(report_html, today)
            if ok:
                print(f"  ✅ Weekly report emailed to {NOTIFY_EMAIL}")
            else:
                print("  ⚠️  Weekly report not sent (no email password).")
    else:
        print(f"  📊 Daily snapshot ready (full report sends on Sundays).")

    return {"html_block": daily_html}


# ── Standalone ─────────────────────────────────────────────────────────────────

def _test():
    today = datetime.datetime.now()
    mock_data = {
        "gold": {"price": 5205.60, "day_chg_pct": 2.89, "rsi": 68.4},
        "fx_rates": {"ZAR": 16.01, "GHS": 10.84, "NGN": 1344.40},
    }

    print("\n── Daily Snapshot ──")
    result = run("trader_intelligence", mock_data, today)

    print("\n── Forcing Weekly Report ──")
    sys.argv.append("--print")
    run("trader_intelligence", mock_data, today)

    print(f"\n✅ Analytics Agent test complete.\n")


if __name__ == "__main__":
    if "--report" in sys.argv or "--print" in sys.argv:
        today = datetime.datetime.now()
        mock_data = {"gold": {"price": 5205.60, "day_chg_pct": 2.89}}
        run("trader_intelligence", mock_data, today)
    else:
        _test()
