#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  Gold Market Briefing — macOS Setup Script
#  Run this once from the folder where you saved the files.
#  Usage:  bash setup_gold_briefing.sh
# ═══════════════════════════════════════════════════════════════════

set -e

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${GREEN}[✓]${NC} $1"; }
warn()    { echo -e "${YELLOW}[!]${NC} $1"; }
error()   { echo -e "${RED}[✗]${NC} $1"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIEFING_SCRIPT="$SCRIPT_DIR/gold_market_briefing.py"
PLIST_SRC="$SCRIPT_DIR/com.jote.gold-briefing.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.jote.gold-briefing.plist"
LOG_FILE="$HOME/Library/Logs/gold-briefing.log"

echo ""
echo "  ┌─────────────────────────────────────────┐"
echo "  │   Gold Market Briefing — Setup Wizard   │"
echo "  └─────────────────────────────────────────┘"
echo ""

# ── 1. Check Python ──────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    error "python3 not found. Install it from https://www.python.org/downloads/"
fi
info "Python 3 found: $(python3 --version)"

# ── 2. Install dependencies ──────────────────────────────────────
echo ""
warn "Installing Python dependencies (yfinance, feedparser, requests)..."
python3 -m pip install --quiet yfinance feedparser requests 2>&1 | tail -2
info "Dependencies installed."

# ── 3. Get Gmail App Password ────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
warn "You need a Gmail App Password to send emails."
echo ""
echo "  Steps to get one (takes ~2 minutes):"
echo "  1. Go to → https://myaccount.google.com/apppasswords"
echo "  2. Sign in to jote.taddese@gmail.com"
echo "  3. Under 'App name', type: Gold Briefing"
echo "  4. Click Create — copy the 16-character password shown."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

read -rsp "  Paste your App Password here (hidden): " APP_PASS
echo ""

if [ ${#APP_PASS} -lt 16 ]; then
    error "Password looks too short. Please re-run and paste the full 16-character app password."
fi
info "Password accepted (${#APP_PASS} chars)."

# ── 4. Update the plist with real paths & password ───────────────
mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$HOME/Library/Logs"

sed \
  -e "s|SCRIPT_PATH_PLACEHOLDER|$BRIEFING_SCRIPT|g" \
  -e "s|HOME_PATH_PLACEHOLDER|$HOME|g" \
  -e "s|YOUR_APP_PASSWORD_HERE|$APP_PASS|g" \
  "$PLIST_SRC" > "$PLIST_DEST"

info "Scheduler config written to: $PLIST_DEST"

# ── 5. Register with launchd ─────────────────────────────────────
# Unload if already loaded (ignore errors)
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load -w "$PLIST_DEST"
info "Scheduled task registered with macOS launchd."

# ── 6. Send a test email now ─────────────────────────────────────
echo ""
warn "Sending a test email to jote.taddese@gmail.com..."
GOLD_EMAIL_SENDER="jote.taddese@gmail.com" \
GOLD_EMAIL_PASSWORD="$APP_PASS" \
GOLD_EMAIL_RECIPIENT="jote.taddese@gmail.com" \
python3 "$BRIEFING_SCRIPT"

echo ""
echo "  ┌─────────────────────────────────────────┐"
echo "  │         Setup complete!                 │"
echo "  │                                         │"
echo "  │  • Briefings sent daily at 6:00 AM      │"
echo "  │  • Logs: ~/Library/Logs/gold-briefing.log │"
echo "  └─────────────────────────────────────────┘"
echo ""
echo "  To stop the briefings at any time, run:"
echo "  launchctl unload ~/Library/LaunchAgents/com.jote.gold-briefing.plist"
echo ""
echo "  To re-enable:"
echo "  launchctl load -w ~/Library/LaunchAgents/com.jote.gold-briefing.plist"
echo ""
