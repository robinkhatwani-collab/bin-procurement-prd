#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  AI PM Tool Server — Auto-start Wrapper
#  Called by launchd at every login.  Logs to server.log in the same folder.
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="/Users/robinkhatwani/AI-Learning-Project"
SERVER_PY="$SCRIPT_DIR/AI_PM_Tool/AI_PM_Tool/server.py"
LOG_FILE="$SCRIPT_DIR/server.log"

# ── Locate python3 (covers system, Homebrew Intel, Homebrew Apple Silicon) ──
PYTHON=""
for candidate in \
    /usr/bin/python3 \
    /usr/local/bin/python3 \
    /opt/homebrew/bin/python3; do
    if [ -x "$candidate" ]; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [ERROR] python3 not found — server not started." >> "$LOG_FILE"
    exit 1
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') [START] Using $PYTHON" >> "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') [START] Server starting on http://localhost:8080" >> "$LOG_FILE"

# Hand off to the server; exec replaces this shell so launchd tracks the PID
exec "$PYTHON" "$SERVER_PY" >> "$LOG_FILE" 2>&1
