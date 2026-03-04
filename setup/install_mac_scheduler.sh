#!/bin/bash
# install_mac_scheduler.sh
# Sets up the AGI daily briefing pipeline as a macOS LaunchAgent.
# Run once from Terminal: bash ~/Documents/GoldBriefing/setup/install_mac_scheduler.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

PLIST_SRC="$HOME/Documents/GoldBriefing/setup/com.agi.daily-briefing.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.agi.daily-briefing.plist"
LABEL="com.agi.daily-briefing"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AGI Daily Briefing · Mac Scheduler Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. Unload existing job if present (suppress errors if not loaded)
launchctl unload "$PLIST_DST" 2>/dev/null || true

# 2. Copy plist to LaunchAgents
mkdir -p "$HOME/Library/LaunchAgents"
cp "$PLIST_SRC" "$PLIST_DST"
echo "  ✅ Plist installed → $PLIST_DST"

# 3. Load the job
launchctl load "$PLIST_DST"
echo "  ✅ LaunchAgent loaded (runs daily at 6:00 AM)"

# 4. Verify it's registered
if launchctl list | grep -q "$LABEL"; then
    echo "  ✅ Job registered: $LABEL"
else
    echo "  ⚠️  Job not found in launchctl list — check for plist errors"
fi

# 5. Quick smoke test — dry run to confirm Python + dependencies work
echo ""
echo "  Running a quick dry run to verify the setup..."
echo ""
cd "$HOME/Documents/GoldBriefing"
python3 orchestrator.py --dry-run 2>&1 | grep -E "Started|Mode|Gold:|Dry run|ERROR|FAILED|env override" | head -20

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Setup complete. The pipeline will run"
echo "  automatically every day at 6:00 AM."
echo ""
echo "  Monitor logs:"
echo "    tail -f ~/Documents/GoldBriefing/logs/launchd.log"
echo ""
echo "  Run manually now:"
echo "    cd ~/Documents/GoldBriefing && make run"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
