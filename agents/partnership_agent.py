#!/usr/bin/env python3
"""
partnership_agent.py — Africa Gold Intelligence — Tier 2: Partnership Outreach Agent
=====================================================================================
Identifies high-value contacts and drafts personalised outreach emails for review.

Contact types:
  - journalist      Financial journalists covering African markets & commodities
  - gold_dealer     Gold dealers, jewellers, bullion traders in Africa
  - mining          Mining companies, exploration firms, royalty companies
  - fintech         African fintech / digital gold / investment platforms
  - institution     Central banks, sovereign wealth, pension funds, regulators
  - media           Podcasts, YouTube channels, newsletters in the finance/Africa space

How it works:
  1. Loads contacts from partners.json (you add contacts; agent manages scheduling)
  2. Picks 1-2 contacts not contacted in the last 30 days, prioritised by score
  3. Drafts a personalised email anchored to today's gold data + their coverage area
  4. Adds drafts to the daily oversight email — YOU decide whether to send
  5. On confirmation (manual), logs the outreach to avoid duplicate contact

Log:      outreach_log.jsonl
Contacts: partners.json  ← edit this to add your target contacts

Usage (standalone test):
    python3 partnership_agent.py

Called by orchestrator.py as the final Tier 2 agent before Human Oversight Gate.
"""

import json
import datetime
import os
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR     = Path(__file__).parent
PARTNERS_FILE  = SCRIPT_DIR.parent / "data" / "partners.json"
OUTREACH_LOG   = SCRIPT_DIR.parent / "logs" / "outreach_log.jsonl"
SITE_URL       = "https://www.africagoldintelligence.com"
SENDER_NAME    = "Jote Taddese"
SENDER_TITLE   = "Founder, Africa Gold Intelligence"
SENDER_EMAIL   = os.environ.get("NOTIFY_EMAIL", "jote.taddese@gmail.com")

COOLDOWN_DAYS  = 30   # minimum days between contacts to the same person
MAX_DRAFTS     = 2    # maximum outreach drafts per day


# ── Default contacts (starter list — edit partners.json to expand) ────────────

DEFAULT_PARTNERS = [
    {
        "id":           "reuters_africa_01",
        "name":         "Reuters Africa Desk",
        "email":        "africa@reuters.com",
        "org":          "Reuters",
        "type":         "journalist",
        "region":       "Pan-Africa",
        "topics":       ["gold", "commodities", "mining", "African markets"],
        "score":        90,
        "notes":        "General commodities desk — pitch Africa-specific gold data angles",
        "last_contacted": None,
    },
    {
        "id":           "bloomberg_africa_01",
        "name":         "Bloomberg Africa",
        "email":        "africa@bloomberg.net",
        "org":          "Bloomberg",
        "type":         "journalist",
        "region":       "Pan-Africa",
        "topics":       ["gold", "commodities", "FX", "African markets"],
        "score":        88,
        "notes":        "Focus on data-driven angles — local currency gold pricing is unique",
        "last_contacted": None,
    },
    {
        "id":           "kitco_01",
        "name":         "Kitco News Editorial",
        "email":        "news@kitco.com",
        "org":          "Kitco",
        "type":         "media",
        "region":       "Global",
        "topics":       ["gold", "silver", "precious metals"],
        "score":        85,
        "notes":        "Pitch Africa-specific gold data as a unique angle they don't cover",
        "last_contacted": None,
    },
    {
        "id":           "wgc_africa_01",
        "name":         "World Gold Council — Africa",
        "email":        "info@gold.org",
        "org":          "World Gold Council",
        "type":         "institution",
        "region":       "Pan-Africa",
        "topics":       ["gold demand", "mining", "investment", "jewellery"],
        "score":        92,
        "notes":        "Long-term partnership potential — data sharing, co-promotion",
        "last_contacted": None,
    },
    {
        "id":           "miningweekly_01",
        "name":         "Mining Weekly",
        "email":        "editorial@miningweekly.com",
        "org":          "Mining Weekly",
        "type":         "media",
        "region":       "South Africa",
        "topics":       ["gold mining", "South Africa", "commodities"],
        "score":        80,
        "notes":        "SA-focused mining publication — pitch ZAR gold price data",
        "last_contacted": None,
    },
    {
        "id":           "businessday_ng_01",
        "name":         "Business Day Nigeria Editorial",
        "email":        "editor@businessdayng.com",
        "org":          "Business Day Nigeria",
        "type":         "journalist",
        "region":       "Nigeria",
        "topics":       ["Nigerian economy", "commodities", "investment"],
        "score":        78,
        "notes":        "Pitch NGN gold pricing and Nigeria-specific content",
        "last_contacted": None,
    },
    {
        "id":           "techcabal_01",
        "name":         "TechCabal",
        "email":        "hello@techcabal.com",
        "org":          "TechCabal",
        "type":         "media",
        "region":       "Pan-Africa",
        "topics":       ["African tech", "fintech", "investment"],
        "score":        72,
        "notes":        "Digital-savvy African audience — angle: gold as digital asset / fintech",
        "last_contacted": None,
    },
    {
        "id":           "quartz_africa_01",
        "name":         "Quartz Africa",
        "email":        "africa@qz.com",
        "org":          "Quartz Africa",
        "type":         "journalist",
        "region":       "Pan-Africa",
        "topics":       ["African business", "commodities", "economy"],
        "score":        82,
        "notes":        "English-language Pan-Africa business — unique karat pricing story",
        "last_contacted": None,
    },
]


# ── Contact management ──────────────────────────────────────────────────────────

def load_partners() -> list:
    """Load partners from partners.json, creating it with defaults if missing."""
    if not PARTNERS_FILE.exists():
        save_partners(DEFAULT_PARTNERS)
        print(f"  📋 Created partners.json with {len(DEFAULT_PARTNERS)} starter contacts.")
        return DEFAULT_PARTNERS
    try:
        return json.loads(PARTNERS_FILE.read_text())
    except Exception as e:
        print(f"  ⚠️  Could not read partners.json: {e}")
        return DEFAULT_PARTNERS


def save_partners(partners: list):
    """Save partners list back to partners.json."""
    PARTNERS_FILE.write_text(json.dumps(partners, indent=2))


def days_since_contacted(partner: dict) -> int:
    """Returns days since last contact, or 9999 if never contacted."""
    lc = partner.get("last_contacted")
    if not lc:
        return 9999
    try:
        last = datetime.datetime.fromisoformat(lc)
        return (datetime.datetime.now() - last).days
    except Exception:
        return 9999


def pick_contacts(partners: list, max_drafts: int = MAX_DRAFTS) -> list:
    """
    Select contacts to reach out to today.
    Priority: score DESC, then days_since_contacted DESC (most overdue first).
    Excludes anyone contacted within COOLDOWN_DAYS.
    """
    eligible = [
        p for p in partners
        if days_since_contacted(p) >= COOLDOWN_DAYS
        and p.get("email")
        and "@" in p.get("email", "")
    ]
    # Sort: highest score first, then longest since contact
    eligible.sort(key=lambda p: (-p.get("score", 0), -days_since_contacted(p)))
    return eligible[:max_drafts]


# ── Email draft builders ────────────────────────────────────────────────────────

def _format_gold_hook(data: dict) -> str:
    gold  = data.get("gold", {})
    price = gold.get("price", 0)
    pct   = gold.get("day_chg_pct", 0) or 0
    sign  = "+" if pct >= 0 else ""
    return f"Gold (XAU/USD) is at ${price:,.2f} ({sign}{pct:.2f}% today)"


def _format_africa_snapshot(data: dict) -> str:
    fx = data.get("fx_rates", {})
    kp = data.get("karat_prices", {})
    sym = {"ZAR": "R", "GHS": "GH₵", "NGN": "₦", "KES": "KSh", "EGP": "E£", "MAD": "DH"}
    lines = []
    for cur, rate in list(fx.items())[:4]:
        k24 = kp.get(cur, {}).get("24K")
        if rate and k24:
            lines.append(f"  {cur}: {sym.get(cur,'')}{k24:,.0f}/g (24K gold)")
    return "\n".join(lines) if lines else "  Live pricing across 6 African currencies"


def build_outreach_email(partner: dict, data: dict, today: datetime.datetime) -> dict:
    """
    Draft a personalised outreach email for a given contact.
    Returns dict with: subject, body, to_name, to_email
    """
    name      = partner.get("name", "")
    org       = partner.get("org", "")
    ptype     = partner.get("type", "media")
    region    = partner.get("region", "Africa")
    topics    = partner.get("topics", [])
    notes     = partner.get("notes", "")
    date_str  = today.strftime("%B %d, %Y")

    gold_hook  = _format_gold_hook(data)
    africa_snap = _format_africa_snapshot(data)
    gold       = data.get("gold", {})
    price      = gold.get("price", 0)
    pct        = gold.get("day_chg_pct", 0) or 0
    sign       = "+" if pct >= 0 else ""

    # ── Journalist / Media ──
    if ptype in ("journalist", "media"):
        subject = f"Africa gold data angle — {sign}{pct:.1f}% move today | Africa Gold Intelligence"
        body = f"""Hi {name.split()[0] if ' ' in name else name},

I'm reaching out because {org} covers {'African markets and commodities' if 'africa' in org.lower() or region == 'Pan-Africa' else region + '-focused financial news'} — and I think we have a data angle your readers would find genuinely useful.

{gold_hook}. Most gold coverage focuses on London or New York spot prices. What's missing is how that translates to local purchasing power across African markets.

Africa Gold Intelligence publishes a daily briefing with real-time karat pricing in six African currencies:

{africa_snap}

This makes it easy to report on what gold actually costs for consumers and jewellers in Lagos, Accra, Nairobi, Cairo, Casablanca, and Johannesburg — not just what the futures contract says.

I'd love to share our data with {org} for coverage, or explore a data-sharing arrangement. Happy to set up a quick call or provide a sample data export.

Full briefing (free access): {SITE_URL}

Best,
{SENDER_NAME}
{SENDER_TITLE}
{SITE_URL}"""

    # ── Institutional ──
    elif ptype == "institution":
        subject = f"Africa gold market data — partnership inquiry | Africa Gold Intelligence"
        body = f"""Dear {name},

I'm writing to explore a potential data partnership between Africa Gold Intelligence and {org}.

We publish a daily gold market briefing specifically designed for African investors and market participants — covering XAU/USD movements, RSI signals, and real-time karat pricing in ZAR, GHS, NGN, KES, EGP, and MAD.

Today's snapshot ({date_str}):
  {gold_hook}
{africa_snap}

Given {org}'s mandate {'across the African continent' if region == 'Pan-Africa' else f'in {region}'}, we believe our data could complement your market monitoring and stakeholder communications.

I would welcome the opportunity to discuss how we might collaborate — whether through data sharing, co-publishing, or distribution to your network.

Free briefing sample: {SITE_URL}

Best regards,
{SENDER_NAME}
{SENDER_TITLE}
{SITE_URL}"""

    # ── Fintech / Gold Dealer / Mining ──
    else:
        subject = f"Africa Gold Intelligence — partnership opportunity for {org}"
        body = f"""Hi {name.split()[0] if ' ' in name else name},

I'm the founder of Africa Gold Intelligence, a daily gold market briefing built specifically for African markets.

{gold_hook}. We track this daily and translate it into local karat prices across six African currencies — giving your {'customers' if ptype == 'gold_dealer' else 'audience'} the kind of ground-level pricing data that's hard to find anywhere else.

Today's 24K gold per gram:
{africa_snap}

I'd love to explore how we might work together — whether that's {
    'supplying live pricing data to display on your platform' if ptype == 'fintech'
    else 'providing daily pricing context your customers could use' if ptype == 'gold_dealer'
    else 'covering your operations and market activity in our briefings'
}.

Free briefing: {SITE_URL}

Happy to jump on a call whenever works for you.

Best,
{SENDER_NAME}
{SENDER_TITLE}
{SITE_URL}"""

    return {
        "to_name":  name,
        "to_email": partner.get("email", ""),
        "org":      org,
        "type":     ptype,
        "subject":  subject,
        "body":     body.strip(),
        "partner_id": partner.get("id", ""),
    }


# ── Logging ─────────────────────────────────────────────────────────────────────

def log_outreach(drafts: list, today: datetime.datetime):
    """Log drafted emails to outreach_log.jsonl."""
    for d in drafts:
        record = {
            "ts":         today.isoformat(),
            "partner_id": d["partner_id"],
            "to_email":   d["to_email"],
            "org":        d["org"],
            "subject":    d["subject"],
            "status":     "drafted",  # changes to "sent" when confirmed
        }
        try:
            with open(OUTREACH_LOG, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as e:
            print(f"  ⚠️  Outreach log write failed: {e}")


def mark_contacted(partners: list, partner_ids: list, today: datetime.datetime) -> list:
    """Update last_contacted for partners whose drafts were prepared today."""
    for p in partners:
        if p.get("id") in partner_ids:
            p["last_contacted"] = today.isoformat()
    return partners


# ── HTML block for oversight email ─────────────────────────────────────────────

def build_outreach_html_block(drafts: list) -> str:
    """Renders drafted outreach emails as a review block in the operator email."""
    if not drafts:
        return ""

    cards = ""
    for d in drafts:
        safe_body = (d["body"]
                     .replace("&", "&amp;")
                     .replace("<", "&lt;")
                     .replace(">", "&gt;"))
        cards += f"""
        <div style="margin:16px 0;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
          <div style="background:#f9fafb;padding:12px 16px;border-bottom:1px solid #e5e7eb;">
            <p style="margin:0;font-size:13px;font-weight:700;color:#111;">
              ✉️ To: {d['to_name']} — {d['org']}
              <span style="font-weight:400;color:#6b7280;">({d['type']})</span>
            </p>
            <p style="margin:4px 0 0;font-size:12px;color:#374151;">
              <strong>Subject:</strong> {d['subject']}
            </p>
            <p style="margin:4px 0 0;font-size:12px;color:#6b7280;">
              {d['to_email']}
            </p>
          </div>
          <pre style="margin:0;padding:14px 16px;font-size:12px;font-family:monospace;
                      white-space:pre-wrap;color:#111;background:#fff;
                      max-height:300px;overflow-y:auto;">{safe_body}</pre>
        </div>"""

    return f"""
    <h3 style="font-size:14px;color:#374151;margin:24px 0 8px;">
      🤝 Partnership Outreach Drafts — Review &amp; Send Manually
    </h3>
    <p style="font-size:12px;color:#6b7280;margin:0 0 12px;">
      {len(drafts)} email draft(s) prepared today. Copy each and send from your email client
      after reviewing. Contacts won't be approached again for 30 days.
    </p>
    {cards}"""


# ── Main entry point ────────────────────────────────────────────────────────────

def run(data: dict, today: datetime.datetime) -> dict:
    """
    Main entry point — called by orchestrator.py.

    Returns partnership_data dict:
        drafts       — list of email draft dicts
        html_block   — HTML block for operator email
        contacts_due — number of contacts eligible today
    """
    partners     = load_partners()
    selected     = pick_contacts(partners)
    drafts       = []

    if not selected:
        print(f"  ✅ No contacts due for outreach today (all within {COOLDOWN_DAYS}-day cooldown).")
    else:
        print(f"  📋 {len(selected)} contact(s) selected for outreach today:")
        for contact in selected:
            draft = build_outreach_email(contact, data, today)
            drafts.append(draft)
            days = days_since_contacted(contact)
            days_str = "never contacted" if days == 9999 else f"last contact {days}d ago"
            print(f"     → {contact['name']} ({contact['org']}) — {days_str}")

    # Mark as contacted and save (even draft counts — prevents daily re-drafting)
    if drafts:
        drafted_ids = [d["partner_id"] for d in drafts]
        updated     = mark_contacted(partners, drafted_ids, today)
        save_partners(updated)
        log_outreach(drafts, today)

    html_block = build_outreach_html_block(drafts)
    eligible   = len([p for p in partners if days_since_contacted(p) >= COOLDOWN_DAYS])

    return {
        "drafts":       drafts,
        "html_block":   html_block,
        "contacts_due": eligible,
    }


# ── Standalone test ─────────────────────────────────────────────────────────────

def _test():
    today = datetime.datetime.now()
    mock_data = {
        "gold":   {"price": 5205.60, "day_chg_pct": 2.89, "rsi": 68.4},
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

    # Reset last_contacted for test
    if PARTNERS_FILE.exists():
        partners = load_partners()
        for p in partners[:2]:
            p["last_contacted"] = None
        save_partners(partners)

    result = run(mock_data, today)
    print(f"\n{'═'*60}")
    print(f"  Drafts generated: {len(result['drafts'])}")
    for d in result["drafts"]:
        print(f"\n── {d['to_name']} / {d['org']} ──")
        print(f"  Subject: {d['subject']}")
        print(f"  Preview: {d['body'][:200]}...")
    print(f"\n  Log: {OUTREACH_LOG}")
    print(f"  Contacts: {PARTNERS_FILE}\n")


if __name__ == "__main__":
    _test()
