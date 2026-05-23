#!/bin/bash
# AI PM Tool — Start local server on port 8080
cd "$(dirname "$0")"

# Install required Python dependencies (safe on macOS and Linux)
python3 -m pip install openpyxl -q 2>/dev/null || pip3 install openpyxl -q 2>/dev/null

# Kill any existing process on port 8080
lsof -ti:8080 | xargs kill -9 2>/dev/null
sleep 1

# Start the server
python3 server.py
