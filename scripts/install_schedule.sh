#!/bin/bash
# One-time setup: run weekly_scrape.sh every Sunday at 22:00 (local time) via launchd.
# If the Mac is asleep at that time, launchd runs it once when the Mac wakes.
#   Install:    bash scripts/install_schedule.sh
#   Uninstall:  bash scripts/install_schedule.sh --uninstall
#   Run now:    launchctl kickstart gui/$(id -u)/com.camilowu.portal-scraper.weekly

LABEL="com.camilowu.portal-scraper.weekly"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null
if [ "$1" = "--uninstall" ]; then
  rm -f "$PLIST" && echo "Removed $LABEL" && exit 0
fi

mkdir -p "$HOME/Library/LaunchAgents" "$REPO/logs"
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$REPO/scripts/weekly_scrape.sh</string></array>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>StartCalendarInterval</key>
  <dict><key>Weekday</key><integer>0</integer><key>Hour</key><integer>22</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>$REPO/logs/launchd.out.log</string>
  <key>StandardErrorPath</key><string>$REPO/logs/launchd.err.log</string>
</dict>
</plist>
PLIST

plutil -lint "$PLIST" && launchctl bootstrap "gui/$(id -u)" "$PLIST" \
  && echo "Installed: weekly scrape every Sunday 22:00 → $REPO/logs/" \
  && launchctl print "gui/$(id -u)/$LABEL" | grep -E "state|path" | head -3
