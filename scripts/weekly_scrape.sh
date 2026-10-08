#!/bin/bash
# Weekly scrape: stage 1 (listing IDs) + stage 2 (new detail pages, then details.csv export).
# Run by launchd every Sunday night (see scripts/install_schedule.sh); safe to run by hand.
# Cleaning is NOT done here: a Claude scheduled task does it on Monday after adding the UF value.
#
# Writes:  logs/scrape_<date>.log       full output of the run
#          logs/last_scrape_status.txt  key=value summary read by the Monday task

REGION="metropolitana"

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" || exit 1
mkdir -p logs

STAMP="$(date +%Y-%m-%d_%H%M)"
LOG="logs/scrape_${STAMP}.log"
STATUS="logs/last_scrape_status.txt"
LOCK="logs/.scrape.lock"

notify() {  # macOS notification; ignored if unavailable
  osascript -e "display notification \"$2\" with title \"$1\"" >/dev/null 2>&1 || true
}

# A lock older than 12 hours is left over from a crash or forced shutdown; clear it.
find "$LOCK" -maxdepth 0 -type d -mmin +720 -exec rmdir {} \; 2>/dev/null
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "$(date '+%F %T') another scrape is still running ($LOCK exists); skipping" >> "logs/skipped.log"
  exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

PY="${SCRAPER_PYTHON:-$REPO/.venv/bin/python}"   # SCRAPER_PYTHON overrides (used in tests)
[ -x "$PY" ] || PY="$(command -v python3)"

printf 'status=running\nstarted=%s\nlog=%s\n' "$(date '+%F %T %z')" "$LOG" > "$STATUS"
echo "[$(date '+%F %T')] weekly scrape started (region=$REGION, python=$PY)" >> "$LOG"

# caffeinate -i keeps the Mac from idle-sleeping while the scrape runs.
caffeinate -i "$PY" main.py run --region "$REGION" >> "$LOG" 2>&1
CODE=$?

ROWS="$(tail -n +2 data/details/details.csv 2>/dev/null | wc -l | tr -d ' ')"
FETCHED="$(grep -o '\[STAGE 2\].*' "$LOG" | tail -1)"

if [ $CODE -eq 0 ]; then
  RESULT=ok
  notify "Rental scraper" "Weekly scrape finished. details.csv: $ROWS listings."
else
  RESULT=failed
  notify "Rental scraper" "Weekly scrape FAILED (exit $CODE). See $LOG"
fi
echo "[$(date '+%F %T')] finished: $RESULT (exit $CODE)" >> "$LOG"

printf 'status=%s\nexit_code=%s\nstarted=%s\nfinished=%s\nlog=%s\ndetails_rows=%s\nstage2=%s\n' \
  "$RESULT" "$CODE" "$(sed -n 's/^started=//p' "$STATUS")" "$(date '+%F %T %z')" "$LOG" "$ROWS" "$FETCHED" > "$STATUS.tmp" \
  && mv "$STATUS.tmp" "$STATUS"
exit $CODE
