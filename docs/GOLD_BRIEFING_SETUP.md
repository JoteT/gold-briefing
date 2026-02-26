# Daily Gold Market Briefing — Setup Guide

Your briefing arrives at **6:00 AM every morning** with gold spot price, related market data, and curated headlines.

---

## Quick Start (2 minutes)

### Step 1 — Save the files
Move all three files to a permanent folder on your Mac, e.g.:
```
~/Documents/GoldBriefing/
```

### Step 2 — Get a Gmail App Password
1. Go to → **https://myaccount.google.com/apppasswords**
2. Sign in with `jote.taddese@gmail.com`
3. Under "App name" type **Gold Briefing** → click **Create**
4. Copy the 16-character password (e.g. `abcd efgh ijkl mnop`)

> Gmail requires an App Password because the script logs in programmatically.
> This is separate from your main Gmail password and can be revoked anytime.

### Step 3 — Run the setup script
Open **Terminal** and run:
```bash
cd ~/Documents/GoldBriefing
bash setup_gold_briefing.sh
```

The script will:
- Install the required Python libraries (`yfinance`, `feedparser`)
- Ask you to paste your App Password (hidden input)
- Register the 6 AM daily schedule with macOS
- Send a **test email right now** so you can confirm everything works

---

## What each file does

| File | Purpose |
|------|---------|
| `gold_market_briefing.py` | Fetches gold price + news, builds and sends the HTML email |
| `com.jote.gold-briefing.plist` | macOS launchd config — triggers the script at 6 AM |
| `setup_gold_briefing.sh` | One-time setup wizard — run this once |

---

## What the email contains

- **Gold spot price (XAU/USD)** — current price, daily change ($ and %), 7-day trend
- **Related markets** — USD Index, S&P 500, Bitcoin
- **Gold & macro headlines** — up to 6 curated stories from Kitco, Reuters, MarketWatch
- **Key drivers to watch** — brief daily reminder of the main factors moving gold

---

## Managing the schedule

**Pause briefings:**
```bash
launchctl unload ~/Library/LaunchAgents/com.jote.gold-briefing.plist
```

**Resume briefings:**
```bash
launchctl load -w ~/Library/LaunchAgents/com.jote.gold-briefing.plist
```

**Change delivery time** — edit `com.jote.gold-briefing.plist`, find `<key>Hour</key>` and update the integer, then reload with the two commands above.

**View logs:**
```bash
tail -f ~/Library/Logs/gold-briefing.log
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Authentication failed" | Re-generate App Password at myaccount.google.com/apppasswords |
| "Less secure app" error | Make sure you're using an **App Password**, not your Gmail password |
| No email at 6 AM | Check `~/Library/Logs/gold-briefing-error.log` |
| Mac was asleep at 6 AM | launchd will run the job next time the Mac wakes — or trigger manually with `python3 gold_market_briefing.py` |
| Price data missing | Yahoo Finance may be temporarily throttled — the script retries automatically |

---

*Data sourced from Yahoo Finance & public RSS feeds. Prices may be delayed up to 20 min. Not financial advice.*
