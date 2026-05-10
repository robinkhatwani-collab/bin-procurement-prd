#!/bin/bash
# ═════════════════════════════════════════════════════════════════════════════
#  BIN Procurement Server — Auto-start Installer
#  Run this script ONCE to enable automatic startup at every login.
#
#  Usage:
#    bash ~/Desktop/Robin\ AI\ Learnings/setup_autostart.sh
#
#  To disable auto-start later, run:
#    bash ~/Desktop/Robin\ AI\ Learnings/setup_autostart.sh --uninstall
# ═════════════════════════════════════════════════════════════════════════════

PROJECT_DIR="/Users/robinkhatwani/Desktop/Robin AI Learnings"
PLIST_NAME="com.robinkhatwani.bintracker.plist"
PLIST_SRC="$PROJECT_DIR/$PLIST_NAME"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME"
WRAPPER="$PROJECT_DIR/start_server.sh"
LABEL="com.robinkhatwani.bintracker"

# ── Colours ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

echo ""
echo "═══════════════════════════════════════════════"
echo "   BIN Procurement Server — Auto-start Setup   "
echo "═══════════════════════════════════════════════"
echo ""

# ── Uninstall mode ────────────────────────────────────────────────────────────
if [ "$1" == "--uninstall" ]; then
    echo -e "${YELLOW}Uninstalling auto-start...${NC}"
    launchctl unload "$PLIST_DST" 2>/dev/null && echo -e "  ${GREEN}✓ Agent stopped and unloaded${NC}" || echo "  (agent was not loaded)"
    rm -f "$PLIST_DST" && echo -e "  ${GREEN}✓ Plist removed from LaunchAgents${NC}"
    echo ""
    echo -e "${GREEN}Done. The server will no longer start automatically.${NC}"
    echo "Your server.py, start_server.sh and plist files in the project folder are unchanged."
    echo ""
    exit 0
fi

# ── Pre-flight checks ─────────────────────────────────────────────────────────
ERRORS=0

if [ ! -f "$PLIST_SRC" ]; then
    echo -e "  ${RED}✗ Plist not found: $PLIST_SRC${NC}"
    ERRORS=$((ERRORS+1))
fi

if [ ! -f "$WRAPPER" ]; then
    echo -e "  ${RED}✗ Wrapper not found: $WRAPPER${NC}"
    ERRORS=$((ERRORS+1))
fi

if [ ! -f "$PROJECT_DIR/server.py" ]; then
    echo -e "  ${RED}✗ server.py not found in: $PROJECT_DIR${NC}"
    ERRORS=$((ERRORS+1))
fi

# Check python3 is available
PYTHON=""
for candidate in /usr/bin/python3 /usr/local/bin/python3 /opt/homebrew/bin/python3; do
    if [ -x "$candidate" ]; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "  ${RED}✗ python3 not found. Please install Python 3 first.${NC}"
    ERRORS=$((ERRORS+1))
else
    echo -e "  ${GREEN}✓ python3 found at: $PYTHON${NC}"
fi

if [ $ERRORS -gt 0 ]; then
    echo ""
    echo -e "${RED}Setup failed — $ERRORS error(s) above must be resolved first.${NC}"
    exit 1
fi

# ── Install ────────────────────────────────────────────────────────────────────

# Make wrapper executable
chmod +x "$WRAPPER"
echo -e "  ${GREEN}✓ start_server.sh marked as executable${NC}"

# Create LaunchAgents directory if missing (rare)
mkdir -p "$HOME/Library/LaunchAgents"

# Unload existing agent if already installed (clean reinstall)
launchctl unload "$PLIST_DST" 2>/dev/null

# Copy plist to LaunchAgents
cp "$PLIST_SRC" "$PLIST_DST"
echo -e "  ${GREEN}✓ Plist installed to ~/Library/LaunchAgents/${NC}"

# Load the agent now (also starts the server immediately)
launchctl load "$PLIST_DST"
if [ $? -eq 0 ]; then
    echo -e "  ${GREEN}✓ Launch agent loaded — server is starting now${NC}"
else
    echo -e "  ${RED}✗ launchctl load failed — check permissions${NC}"
    exit 1
fi

# Brief pause then verify the server is up
sleep 2
if curl -s --max-time 3 http://localhost:8080 > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓ Server confirmed running at http://localhost:8080${NC}"
else
    echo -e "  ${YELLOW}⚠  Server may still be starting — check server.log if needed${NC}"
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅  Auto-start enabled!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo ""
echo "  The server will now start automatically every time"
echo "  this Mac logs in — no manual action needed."
echo ""
echo "  Dashboard:    http://localhost:8080"
echo "  Tracker:      http://localhost:8080/bin-tracker"
echo "  Log file:     $PROJECT_DIR/server.log"
echo "  Error log:    $PROJECT_DIR/server_error.log"
echo ""
echo "  To disable auto-start later:"
echo "  bash ~/Desktop/Robin\\ AI\\ Learnings/setup_autostart.sh --uninstall"
echo ""
