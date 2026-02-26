#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Africa Gold Intelligence — Daily Post Scheduler Installer
# Run once to set up the 6 AM daily automation on macOS.
# ─────────────────────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_SRC="$SCRIPT_DIR/com.africagoldintelligence.daily-post.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.africagoldintelligence.daily-post.plist"
LABEL="com.africagoldintelligence.daily-post"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   Africa Gold Intelligence — Scheduler Setup         ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Check Beehiiv API key ─────────────────────────────────────────
if [ -z "$BEEHIIV_API_KEY" ]; then
  echo "⚠️  BEEHIIV_API_KEY is not set."
  echo ""
  echo "   Get your API key from: https://app.beehiiv.com/settings/api"
  echo "   Then either:"
  echo "     a) Run:  export BEEHIIV_API_KEY='your_key' && bash install_scheduler.sh"
  echo "     b) Edit $PLIST_SRC and replace REPLACE_WITH_YOUR_API_KEY"
  echo ""
  read -p "   Enter Beehiiv API key now (or press Enter to skip): " INPUT_KEY
  if [ -n "$INPUT_KEY" ]; then
    BEEHIIV_API_KEY="$INPUT_KEY"
  else
    echo "   ⚠️  Skipping API key — you'll need to set it manually in the plist."
  fi
fi

# ── Step 1b: Check Gmail App Password (for operator notifications) ─────────
if [ -z "$NOTIFY_PASSWORD" ]; then
  echo ""
  echo "⚠️  NOTIFY_PASSWORD (Gmail App Password) is not set."
  echo ""
  echo "   The orchestrator emails you when a draft is ready or the pipeline fails."
  echo "   Get a Gmail App Password from: https://myaccount.google.com/apppasswords"
  echo "   (Requires 2-Step Verification to be enabled on your Google account)"
  echo ""
  read -p "   Enter Gmail App Password now (or press Enter to skip): " INPUT_PASS
  if [ -n "$INPUT_PASS" ]; then
    NOTIFY_PASSWORD="$INPUT_PASS"
  else
    echo "   ⚠️  Skipping — email notifications will be disabled until set."
  fi
fi

# ── Step 2: Update plist with credentials ─────────────────────────────────
cp "$PLIST_SRC" "/tmp/agi_plist_tmp.plist"

if [ -n "$BEEHIIV_API_KEY" ]; then
  /usr/bin/plutil -replace EnvironmentVariables.BEEHIIV_API_KEY \
    -string "$BEEHIIV_API_KEY" "/tmp/agi_plist_tmp.plist"
  echo "✅ Beehiiv API key written to plist."
fi

if [ -n "$NOTIFY_PASSWORD" ]; then
  /usr/bin/plutil -replace EnvironmentVariables.NOTIFY_PASSWORD \
    -string "$NOTIFY_PASSWORD" "/tmp/agi_plist_tmp.plist"
  echo "✅ Gmail App Password written to plist."
fi

cp "/tmp/agi_plist_tmp.plist" "$PLIST_DEST"

# ── Step 3: Update script path in plist (always uses orchestrator.py) ──────
SCRIPT_PATH="$SCRIPT_DIR/orchestrator.py"
/usr/bin/plutil -replace ProgramArguments \
  -json "[\"\/usr\/bin\/python3\", \"$SCRIPT_PATH\"]" "$PLIST_DEST" 2>/dev/null || true
echo "✅ Script path set to: $SCRIPT_PATH"

# ── Step 4: Unload existing job if running ─────────────────────────────────
launchctl list | grep -q "$LABEL" && launchctl unload "$PLIST_DEST" 2>/dev/null || true

# ── Step 5: Load the job ───────────────────────────────────────────────────
launchctl load "$PLIST_DEST"
echo "✅ Scheduler loaded."

# ── Step 6: Verify ────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Status:"
launchctl list | grep "$LABEL" || echo "  (not found — check for errors above)"
echo ""
echo "  The script will run automatically every day at 06:00."
echo ""
echo "  ▶  Test run now:   launchctl start $LABEL"
echo "  📋 View logs:      tail -f /tmp/agi_post.log"
echo "  ❌ Uninstall:      launchctl unload $PLIST_DEST"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
