#!/usr/bin/env python3
"""
Daily Gold Market Briefing Script
Fetches gold price data + market news and delivers a formatted email each morning.

SETUP — DO THIS ONCE:
  1. Enable 2-Factor Authentication on your Gmail account (if not already on).
  2. Generate a Gmail App Password:
       https://myaccount.google.com/apppasswords
       (Sign in → Search "App passwords" → Select app: Mail → Generate)
  3. Copy the 16-character password (no spaces).
  4. Edit the CONFIG section below OR export environment variables in your shell.

REQUIRED CONFIG:
  GOLD_EMAIL_SENDER   — your Gmail address (jote.taddese@gmail.com)
  GOLD_EMAIL_PASSWORD — your Gmail App Password (16-char, no spaces)

OPTIONAL:
  GOLD_EMAIL_RECIPIENT — recipient address (defaults to SENDER if unset)
"""

import os, smtplib, ssl, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── CONFIG ────────────────────────────────────────────────────────────────────
SENDER    = os.environ.get("GOLD_EMAIL_SENDER",    "jote.taddese@gmail.com")
PASSWORD  = os.environ.get("GOLD_EMAIL_PASSWORD",  "YOUR_APP_PASSWORD_HERE")
RECIPIENT = os.environ.get("GOLD_EMAIL_RECIPIENT", SENDER)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
# ──────────────────────────────────────────────────────────────────────────────

# Tickers (Yahoo Finance)
GOLD_TICKER  = "GC=F"
USD_TICKER   = "DX-Y.NYB"
SP500_TICKER = "^GSPC"
BTC_TICKER   = "BTC-USD"

# RSS feeds — gold and macro relevant sources
NEWS_FEEDS = [
    ("Kitco News",      "https://www.kitco.com/rss/feed/news.xml"),
    ("Reuters Markets", "https://feeds.reuters.com/reuters/businessNews"),
    ("MarketWatch",     "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ("Investing.com",   "https://www.investing.com/rss/news_301.rss"),
]
MAX_NEWS = 6

GOLD_KEYWORDS = [
    "gold", "xau", "bullion", "precious metal", "silver", "platinum",
    "fed rate", "federal reserve", "inflation", "dollar index", "safe haven",
    "commodity", "treasury yield", "bond yield", "real yield",
]


# ── DATA FETCHING ─────────────────────────────────────────────────────────────

def fetch_price_yfinance(ticker: str) -> dict:
    """Primary price source: Yahoo Finance via yfinance."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        hist = t.history(period="7d", interval="1d")
        if hist.empty:
            return {}
        current  = float(hist["Close"].iloc[-1])
        prev     = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
        week_ago = float(hist["Close"].iloc[0])
        day_chg      = current - prev
        day_chg_pct  = (day_chg / prev * 100) if prev else 0
        week_chg_pct = ((current - week_ago) / week_ago * 100) if week_ago else 0
        return {"price": current, "day_chg": day_chg,
                "day_chg_pct": day_chg_pct, "week_chg_pct": week_chg_pct}
    except Exception as e:
        print(f"  yfinance [{ticker}] failed: {e}")
        return {}


def fetch_gold_fallback() -> dict:
    """Fallback: metals.live free API (no key required)."""
    try:
        import urllib.request, json
        url  = "https://api.metals.live/v1/spot/gold"
        req  = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        # metals.live returns [{"gold": price}]
        price = float(data[0].get("gold", 0)) if isinstance(data, list) else float(data.get("gold", 0))
        if price:
            return {"price": price, "day_chg": None, "day_chg_pct": None, "week_chg_pct": None}
    except Exception as e:
        print(f"  fallback API failed: {e}")
    return {}


def fetch_price(ticker: str, is_gold: bool = False) -> dict:
    d = fetch_price_yfinance(ticker)
    if not d and is_gold:
        print("  Trying fallback gold API...")
        d = fetch_gold_fallback()
    return d


def fetch_news() -> list:
    try:
        import feedparser
    except ImportError:
        print("feedparser not installed — skipping news")
        return []
    items = []
    for source, url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                title   = entry.get("title", "")
                summary = entry.get("summary", "")
                link    = entry.get("link", "#")
                if any(kw in (title + " " + summary).lower() for kw in GOLD_KEYWORDS):
                    items.append({"source": source, "title": title, "link": link})
                if len(items) >= MAX_NEWS:
                    return items
        except Exception as e:
            print(f"  RSS [{source}] failed: {e}")
    return items[:MAX_NEWS]


# ── FORMATTING HELPERS ────────────────────────────────────────────────────────

def arrow(v):  return "▲" if (v or 0) >= 0 else "▼"
def clr(v):    return "#16a34a" if (v or 0) >= 0 else "#dc2626"

def fmt_price(v, prefix="$", dp=2):
    return f"{prefix}{v:,.{dp}f}" if v is not None else "—"

def fmt_chg(v, suffix=""):
    if v is None: return "—"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}{suffix}"

def asset_row(label, d, prefix="$", dp=2):
    if not d: return ""
    p   = fmt_price(d.get("price"), prefix, dp)
    pct = d.get("day_chg_pct")
    chg = fmt_chg(pct, "%")
    c   = clr(pct); a = arrow(pct)
    return f"""
    <tr>
      <td style="padding:9px 14px;border-bottom:1px solid #f3f4f6;color:#374151;font-weight:600;">{label}</td>
      <td style="padding:9px 14px;border-bottom:1px solid #f3f4f6;text-align:right;color:#111827;">{p}</td>
      <td style="padding:9px 14px;border-bottom:1px solid #f3f4f6;text-align:right;color:{c};font-weight:700;">{a} {chg}</td>
    </tr>"""


# ── HTML BUILDER ──────────────────────────────────────────────────────────────

def build_html(gold, usd, sp500, btc, news):
    today = datetime.datetime.now().strftime("%A, %B %d, %Y")

    # Gold headline numbers
    g_price = fmt_price(gold.get("price"))
    g_day   = fmt_chg(gold.get("day_chg"), " USD")
    g_pct   = fmt_chg(gold.get("day_chg_pct"), "%")
    g_week  = fmt_chg(gold.get("week_chg_pct"), "%")
    g_clr   = clr(gold.get("day_chg_pct"))
    g_arr   = arrow(gold.get("day_chg_pct"))

    # Show week-chg only if available
    week_span = (f'&nbsp;&nbsp;<span style="color:#6b7280;font-size:13px;">7-day: {g_week}</span>'
                 if gold.get("week_chg_pct") is not None else "")
    # Show day-change only if available
    day_span = (f'<span style="color:{g_clr};font-weight:700;font-size:17px;">{g_arr} {g_day} ({g_pct})</span>'
                if gold.get("day_chg") is not None
                else '<span style="color:#6b7280;font-size:13px;">Change data unavailable</span>')

    related = asset_row("US Dollar Index", usd,   "", 3) + \
              asset_row("S&amp;P 500",      sp500, "$", 0) + \
              asset_row("Bitcoin (BTC)",   btc,   "$", 0)

    news_rows = ""
    for item in news:
        news_rows += f"""
        <tr>
          <td style="padding:11px 14px;border-bottom:1px solid #f3f4f6;">
            <span style="font-size:10px;color:#9ca3af;font-weight:700;text-transform:uppercase;letter-spacing:.06em;">{item['source']}</span><br>
            <a href="{item['link']}" style="color:#1d4ed8;text-decoration:none;font-size:14px;line-height:1.5;">{item['title']}</a>
          </td>
        </tr>"""
    if not news_rows:
        news_rows = "<tr><td style='padding:12px 14px;color:#9ca3af;font-size:13px;'>No gold-specific headlines found today.</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gold Market Briefing</title></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;">
<tr><td align="center" style="padding:28px 16px;">
<table width="580" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.09);">

  <!-- Header -->
  <tr>
    <td style="background:linear-gradient(135deg,#78350f 0%,#d97706 100%);padding:26px 30px 22px;">
      <p style="margin:0;font-size:11px;color:#fde68a;letter-spacing:.12em;text-transform:uppercase;font-weight:600;">Daily Market Briefing</p>
      <h1 style="margin:5px 0 0;font-size:22px;color:#fff;font-weight:800;letter-spacing:-.3px;">Gold Market Insights</h1>
      <p style="margin:6px 0 0;font-size:12px;color:#fde68a;">{today} &nbsp;·&nbsp; Automated Report</p>
    </td>
  </tr>

  <!-- Gold Spotlight -->
  <tr><td style="padding:22px 30px 10px;">
    <p style="margin:0 0 12px;font-size:11px;font-weight:700;color:#92400e;text-transform:uppercase;letter-spacing:.1em;">XAU/USD — Gold Spot Price</p>
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr><td style="background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:18px 22px;">
        <p style="margin:0;font-size:40px;font-weight:800;color:#111827;letter-spacing:-1px;">{g_price}</p>
        <p style="margin:9px 0 0;">{day_span}{week_span}</p>
      </td></tr>
    </table>
  </td></tr>

  <!-- Related Markets -->
  <tr><td style="padding:18px 30px 6px;">
    <p style="margin:0 0 10px;font-size:11px;font-weight:700;color:#374151;text-transform:uppercase;letter-spacing:.1em;">Related Markets</p>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
      <tr style="background:#f9fafb;">
        <th style="padding:8px 14px;text-align:left;font-size:11px;color:#9ca3af;font-weight:700;">Asset</th>
        <th style="padding:8px 14px;text-align:right;font-size:11px;color:#9ca3af;font-weight:700;">Price</th>
        <th style="padding:8px 14px;text-align:right;font-size:11px;color:#9ca3af;font-weight:700;">1D Change</th>
      </tr>
      {related if related else "<tr><td colspan='3' style='padding:12px;color:#9ca3af;font-size:13px;'>Market data unavailable</td></tr>"}
    </table>
  </td></tr>

  <!-- Gold Headlines -->
  <tr><td style="padding:18px 30px 6px;">
    <p style="margin:0 0 10px;font-size:11px;font-weight:700;color:#374151;text-transform:uppercase;letter-spacing:.1em;">Gold &amp; Macro Headlines</p>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
      {news_rows}
    </table>
  </td></tr>

  <!-- Watch list -->
  <tr><td style="padding:18px 30px 22px;">
    <div style="background:#eff6ff;border-left:4px solid #3b82f6;padding:14px 16px;border-radius:0 8px 8px 0;">
      <p style="margin:0;font-size:11px;color:#1e40af;font-weight:700;text-transform:uppercase;letter-spacing:.06em;">Key Drivers to Watch</p>
      <p style="margin:7px 0 0;font-size:13px;color:#1e3a8a;line-height:1.65;">
        <strong>USD strength</strong> (gold has strong inverse correlation) ·
        <strong>Fed policy &amp; rate expectations</strong> ·
        <strong>10Y real Treasury yields</strong> ·
        <strong>Geopolitical &amp; macro risk events</strong>.
        Gold tends to rally when real yields fall or risk-off sentiment spikes.
      </p>
    </div>
  </td></tr>

  <!-- Footer -->
  <tr><td style="background:#f9fafb;padding:14px 30px;border-top:1px solid #f3f4f6;">
    <p style="margin:0;font-size:11px;color:#9ca3af;text-align:center;">
      Automated briefing · Data via Yahoo Finance &amp; public RSS ·
      Prices may be delayed up to 20 min · Not financial advice.
    </p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


# ── EMAIL ─────────────────────────────────────────────────────────────────────

def send_email(subject, html_body):
    if PASSWORD == "YOUR_APP_PASSWORD_HERE":
        print("\nERROR: Gmail App Password not configured.")
        print("  Edit GOLD_EMAIL_PASSWORD in the script or set the environment variable.")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER
    msg["To"]      = RECIPIENT
    msg.attach(MIMEText(html_body, "html"))
    ctx = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as s:
            s.login(SENDER, PASSWORD)
            s.sendmail(SENDER, RECIPIENT, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Fetching prices...")
    gold  = fetch_price(GOLD_TICKER,  is_gold=True)
    usd   = fetch_price(USD_TICKER)
    sp500 = fetch_price(SP500_TICKER)
    btc   = fetch_price(BTC_TICKER)

    if not gold:
        print("Could not retrieve gold price data. Aborting.")
        return

    print(f"  Gold: ${gold.get('price',0):,.2f} ({fmt_chg(gold.get('day_chg_pct'), '%')})")

    print("Fetching news headlines...")
    news = fetch_news()
    print(f"  Found {len(news)} relevant headlines.")

    today_str = datetime.datetime.now().strftime("%b %d, %Y")
    price_str = f"${gold.get('price', 0):,.2f}"
    chg_str   = fmt_chg(gold.get("day_chg_pct"), "%")
    subject   = f"Gold Briefing {today_str} — {price_str} ({chg_str})"

    html = build_html(gold, usd, sp500, btc, news)

    print(f"Sending to {RECIPIENT}...")
    ok = send_email(subject, html)
    if ok:
        print("Done. Email delivered.")
    else:
        print("Email not sent. Check credentials.")


if __name__ == "__main__":
    main()
