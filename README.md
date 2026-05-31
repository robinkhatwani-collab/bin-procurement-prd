# Robin Khatwani — AI Learnings & Projects

A personal portfolio of AI-assisted projects and weekly learning notes, hosted locally via a Python server.

---

## 🏦 BIN Procurement — Card Launch Tracker

A **live status tracker** for a 31-step New BIN Procurement process targeting a card launch in October 2026.

### Pages

| Route | Description |
|---|---|
| `http://localhost:8080/` | Landing page — project hub |
| `http://localhost:8080/bin-tracker` | Live BIN Procurement Status Tracker |

### How it works

- `server.py` reads `Project_Input_BIN_SS.xlsx` on every request — no restart needed after updating the spreadsheet.
- The tracker shows: RAG status, KPI tiles, stakeholder donut charts, milestone cards, and a full 31-step table.
- The page auto-refreshes every 60 seconds.

### Run locally

```bash
python3 server.py
```

Then open **http://localhost:8080** in your browser.

**Requirements:** Python 3.8+ (standard library only — no `pip install` needed).

---

## 📄 Project Tracker (Static)

`Project_StatusTracker.html` — a static snapshot of the status tracker that can be opened directly in a browser without running the server.

---

## 📚 Week-1 — AI Learning Notes

Summaries, workflows, and notes from Week 1 of Robin's AI learning journey.

| File | Description |
|---|---|
| `Week-1/Week1_Learning_Summary.html` | Full HTML learning summary for Week 1 |
| `Week-1/n8n-agentworkflow.json` | n8n agent workflow export |
| `Week-1/▶️ My workflow - n8n.html` | n8n workflow visual export |

---

## 🗂 Repository Structure

```
.
├── server.py                    # Python HTTP server (no dependencies)
├── index.html                   # PRD — AI-Powered BIN Procurement Tracker
├── Project_StatusTracker.html   # Static HTML status tracker
├── start_server.sh              # Server startup script
├── Week-1/
│   ├── Week1_Learning_Summary.html
│   ├── n8n-agentworkflow.json
│   └── ▶️ My workflow - n8n.html
└── README.md
```

> **Note:** Data files (`.xlsx`, `.pdf`, `.docx`) are excluded from this repo via `.gitignore` to keep sensitive information private.

---

*Built with Python (stdlib only) · Payments Division · Robin Khatwani, 2026*
