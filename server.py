#!/usr/bin/env python3
"""
BIN Procurement — Local Status Server
======================================
Usage:
  1. Make sure this file is in the same folder as Project_Input_BIN_SS.xlsx
  2. Open Terminal and run:  python3 server.py
  3. Open your browser:      http://localhost:8080

The server reads the Excel file fresh on every request.
Update the spreadsheet, save it, then click "Refresh Now" in the browser
to see the latest data instantly.

Press Ctrl+C in Terminal to stop the server.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, date
import os
import math
import traceback

# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────────────────────

PORT           = 8080
EXCEL_FILENAME = "Project_Input_BIN_SS.xlsx"
LAUNCH_DATE    = date(2026, 10, 10)      # Target card launch date
AUTO_REFRESH_S = 60                      # Browser auto-refresh interval (seconds)

# Responsible-party → background colour
PARTY_COLORS = {
    "Issuer":                 "#1a3a5c",
    "Network":                "#0072ce",
    "Processor":              "#1a7a4a",
    "Embosser":               "#e8840f",
    "Network and Processor":  "#7b2d8b",
    "Network and Processor ": "#7b2d8b",
    "Issuer and Processor":   "#b83232",
    "Issuer and Processor ":  "#b83232",
    "Embosser and Processor": "#c47a00",
}

# Step status → (text colour, background colour)
STATUS_STYLES = {
    "ToDo":        ("#64748b", "#f1f5f9"),
    "In Progress": ("#0072ce", "#eef5fd"),
    "Done":        ("#1a7a4a", "#f0faf4"),
    "Blocked":     ("#b83232", "#fdeaea"),
}

# Steps that require elevated security controls
SECURE_STEPS = {9, 10, 11, 12}


# ─────────────────────────────────────────────────────────────────────────────
#  DATA LAYER  —  reads xlsx on every call, no caching
# ─────────────────────────────────────────────────────────────────────────────

def read_project_data():
    """Parse Project_Input_BIN_SS.xlsx and return (objective, steps_list)."""
    base       = os.path.dirname(os.path.abspath(__file__))
    excel_path = os.path.join(base, EXCEL_FILENAME)

    steps     = []
    objective = "Track progress of New BIN procurement for New Card launch."

    with zipfile.ZipFile(excel_path) as z:

        # ── shared strings ──────────────────────────────────────────────────
        with z.open("xl/sharedStrings.xml") as f:
            root = ET.parse(f).getroot()
            ns   = {"n": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            strings = [
                "".join(t.text or "" for t in si.findall(".//n:t", ns))
                for si in root.findall("n:si", ns)
            ]

        # ── worksheet ───────────────────────────────────────────────────────
        with z.open("xl/worksheets/sheet1.xml") as f:
            root = ET.parse(f).getroot()
            ns   = {"n": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

            for row in root.findall(".//n:row", ns):
                cells = {}
                for c in row.findall("n:c", ns):
                    col   = "".join(ch for ch in c.get("r", "") if ch.isalpha())
                    v_el  = c.find("n:v", ns)
                    if v_el is None:
                        continue
                    if c.get("t") == "s":
                        cells[col] = strings[int(v_el.text)]
                    else:
                        try:
                            num = float(v_el.text)
                            # Excel date serial → ISO date string
                            if num > 40000:
                                cells[col] = (
                                    datetime(1899, 12, 30) + timedelta(days=num)
                                ).strftime("%Y-%m-%d")
                            else:
                                cells[col] = v_el.text
                        except Exception:
                            cells[col] = v_el.text

                a_val = cells.get("A", "")

                # Project objective row
                if str(a_val).startswith("Project Objective"):
                    objective = (
                        str(a_val)
                        .replace("Project Objective : - ", "")
                        .strip()
                    )
                else:
                    # Step data row
                    try:
                        step_num = int(str(a_val))
                        steps.append({
                            "step":            step_num,
                            "description":     cells.get("B", ""),
                            "responsible":     (cells.get("C") or "").strip(),
                            "notes":           cells.get("D", ""),
                            "status":          cells.get("E", "ToDo"),
                            "estimated_date":  cells.get("F", ""),
                            "completion_date": cells.get("G", ""),
                        })
                    except (ValueError, TypeError):
                        pass   # skip header / blank rows

    return objective, steps


def _parse_date(s):
    try:
        return date.fromisoformat(s) if s else None
    except Exception:
        return None


def compute_summary(steps):
    """Return a dict of KPIs and the RAG status computed from step data."""
    today = date.today()
    total    = len(steps)
    done     = sum(1 for s in steps if s["status"] == "Done")
    in_prog  = sum(1 for s in steps if s["status"] == "In Progress")
    blocked  = sum(1 for s in steps if s["status"] == "Blocked")
    todo     = total - done - in_prog - blocked

    overdue_steps = [
        s for s in steps
        if s["status"] != "Done"
        and _parse_date(s["estimated_date"])
        and _parse_date(s["estimated_date"]) < today
    ]

    upcoming = [
        s for s in steps
        if s["status"] in ("ToDo", "In Progress")
    ][:3]

    pct            = round(done / total * 100) if total else 0
    days_to_launch = (LAUNCH_DATE - today).days

    if   len(overdue_steps) > 3: rag = "RED"
    elif len(overdue_steps) > 0: rag = "AMBER"
    else:                        rag = "GREEN"

    return {
        "total":         total,
        "done":          done,
        "in_progress":   in_prog,
        "blocked":       blocked,
        "todo":          todo,
        "overdue":       len(overdue_steps),
        "overdue_steps": overdue_steps,
        "upcoming":      upcoming,
        "pct":           pct,
        "days_to_launch": days_to_launch,
        "rag":           rag,
        "as_of":         datetime.now().strftime("%d %b %Y, %H:%M:%S"),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  HTML GENERATOR — LANDING PAGE
# ─────────────────────────────────────────────────────────────────────────────

def render_landing():
    now = datetime.now().strftime("%d %b %Y, %H:%M")

    return (
        "<!DOCTYPE html>\n"
        "<html lang='en'>\n"
        "<head>\n"
        "<meta charset='UTF-8'/>\n"
        "<meta name='viewport' content='width=device-width,initial-scale=1.0'/>\n"
        "<title>Robin Khatwani Projects</title>\n"
        "<style>\n"
        "  *{box-sizing:border-box;margin:0;padding:0}\n"
        "  body{font-family:'Segoe UI',system-ui,sans-serif;background:#f0f4f8;color:#1e2d3d;min-height:100vh}\n"
        "  header{background:linear-gradient(135deg,#1a3a5c 0%,#0d5ca8 100%);color:#fff;padding:36px 60px;display:flex;align-items:center;gap:20px}\n"
        "  .logo{width:56px;height:56px;background:rgba(255,255,255,.18);border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:28px;flex-shrink:0}\n"
        "  header h1{font-size:1.5rem;font-weight:700}\n"
        "  header p{font-size:13px;opacity:.8;margin-top:4px}\n"
        "  main{max-width:920px;margin:48px auto;padding:0 24px 80px}\n"
        "  .sect-title{font-size:12px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-bottom:18px}\n"
        "  .project-card{background:#fff;border:1px solid #d0daea;border-radius:14px;padding:30px 32px;display:flex;align-items:center;justify-content:space-between;gap:24px;box-shadow:0 2px 14px rgba(0,0,0,.06);transition:box-shadow .2s}\n"
        "  .project-card:hover{box-shadow:0 6px 28px rgba(0,0,0,.12)}\n"
        "  .card-left{flex:1}\n"
        "  .card-icon{width:50px;height:50px;background:#eef5fd;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:24px;margin-bottom:14px}\n"
        "  .card-name{font-size:1.05rem;font-weight:700;color:#1a3a5c}\n"
        "  .card-desc{font-size:13px;color:#5a6e82;margin-top:7px;line-height:1.55;max-width:520px}\n"
        "  .chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}\n"
        "  .chip{font-size:12px;background:#f4f7fb;border:1px solid #d0daea;border-radius:20px;padding:3px 12px;color:#5a6e82}\n"
        "  .btn{display:inline-flex;align-items:center;gap:8px;background:#0072ce;color:#fff;text-decoration:none;padding:13px 26px;border-radius:9px;font-size:14px;font-weight:600;transition:background .2s;white-space:nowrap}\n"
        "  .btn:hover{background:#005aa5}\n"
        "  .info-bar{background:#eef5fd;border:1px solid #c5d9f0;border-radius:9px;padding:14px 20px;margin-top:28px;font-size:13px;color:#1a3a5c;display:flex;align-items:flex-start;gap:10px;line-height:1.5}\n"
        "  footer{text-align:center;font-size:12px;color:#94a3b8;margin-top:60px;padding:24px;border-top:1px solid #e2e8f0}\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        "<header>\n"
        "  <div class='logo'>🏦</div>\n"
        "  <div><h1>Robin Khatwani Projects</h1><p>Internal Project Dashboard &nbsp;·&nbsp; Payments Division</p></div>\n"
        "</header>\n"
        "<main>\n"
        "  <div class='sect-title'>Available Projects</div>\n"
        "  <div class='project-card'>\n"
        "    <div class='card-left'>\n"
        "      <div class='card-icon'>💳</div>\n"
        "      <div class='card-name'>New BIN Procurement &mdash; Card Launch Tracker</div>\n"
        "      <div class='card-desc'>31-step milestone tracker covering project initiation, BIN ordering, card key management, settlement setup, tokenization, card fulfillment, and go-live. Tracks Issuer, Network, Processor, and Embosser milestones from Jun&nbsp;&ndash;&nbsp;Oct 2026.</div>\n"
        "      <div class='chips'>\n"
        "        <span class='chip'>&#x1F4CB; 31 Steps</span>\n"
        "        <span class='chip'>&#x1F465; 4 Parties</span>\n"
        "        <span class='chip'>&#x1F4C5; Jun &ndash; Oct 2026</span>\n"
        "        <span class='chip' style='background:#fdeaea;border-color:#f5c0c0;color:#b83232'>&#x1F534; Live Data</span>\n"
        "      </div>\n"
        "    </div>\n"
        "    <a class='btn' href='/bin-tracker'>\n"
        "      <svg width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5'>"
        "<path d='M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6'/>"
        "<polyline points='15 3 21 3 21 9'/><line x1='10' y1='14' x2='21' y2='3'/></svg>\n"
        "      View Live Tracker\n"
        "    </a>\n"
        "  </div>\n"
        "  <div class='info-bar'>\n"
        "    <span style='font-size:18px'>&#x1F504;</span>\n"
        "    <span>The tracker reads live data from <strong>Project_Input_BIN_SS.xlsx</strong> on every click. "
        "Update the spreadsheet, save it, then click <em>View Live Tracker</em> to see the latest status instantly &mdash; no restart needed.</span>\n"
        "  </div>\n"
        "</main>\n"
        "<footer>Robin Khatwani Projects &nbsp;&middot;&nbsp; Last loaded: " + now + " &nbsp;&middot;&nbsp; Source: Project_Input_BIN_SS.xlsx</footer>\n"
        "</body>\n"
        "</html>"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  HTML GENERATOR — STATUS TRACKER
# ─────────────────────────────────────────────────────────────────────────────

def _rag_theme(rag):
    return {
        "GREEN": ("#1a7a4a", "#f0faf4", "🟢 On Track"),
        "AMBER": ("#c47a00", "#fef8ee", "🟡 At Risk"),
        "RED":   ("#b83232", "#fdeaea", "🔴 Delayed"),
    }[rag]


def _step_rows_html(steps, today):
    rows = []
    for st in steps:
        col, bg = STATUS_STYLES.get(st["status"], ("#64748b", "#f1f5f9"))
        pc      = PARTY_COLORS.get(st["responsible"], "#555")
        ed      = _parse_date(st["estimated_date"])

        # Days-left / overdue label
        if st["status"] == "Done":
            days_lbl = "<span style='color:#1a7a4a;font-weight:600'>&#x2713; Complete</span>"
        elif ed:
            delta = (ed - today).days
            if delta < 0:
                days_lbl = f"<span style='color:#b83232;font-weight:700'>&#x26A0; {abs(delta)}d overdue</span>"
            elif delta == 0:
                days_lbl = "<span style='color:#c47a00;font-weight:700'>Due today!</span>"
            elif delta <= 7:
                days_lbl = f"<span style='color:#c47a00;font-weight:600'>{delta}d left</span>"
            else:
                days_lbl = f"<span style='color:#5a6e82'>{delta}d left</span>"
        else:
            days_lbl = "&mdash;"

        # Secure badge for key-management steps
        secure = (
            " <span style='background:#7b2d8b;color:#fff;font-size:10px;"
            "padding:1px 5px;border-radius:3px;vertical-align:middle'>&#x26BF; SECURE</span>"
            if st["step"] in SECURE_STEPS else ""
        )

        rows.append(
            f"<tr>"
            f"<td style='text-align:center;font-weight:700;color:#1a3a5c'>{st['step']}</td>"
            f"<td>{st['description']}{secure}</td>"
            f"<td><span style='background:{pc};color:#fff;font-size:11px;padding:2px 8px;"
            f"border-radius:4px;white-space:nowrap'>{st['responsible'] or '&mdash;'}</span></td>"
            f"<td style='white-space:nowrap'>{st['estimated_date'] or '&mdash;'}</td>"
            f"<td style='white-space:nowrap'>{st['completion_date'] or '&mdash;'}</td>"
            f"<td><span style='background:{bg};color:{col};font-size:11px;padding:3px 10px;"
            f"border-radius:12px;font-weight:600;white-space:nowrap'>{st['status']}</span></td>"
            f"<td>{days_lbl}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def _upcoming_cards_html(upcoming):
    cards = []
    for u in upcoming:
        pc = PARTY_COLORS.get(u["responsible"], "#555")
        cards.append(
            f"<div style='background:#fff;border:1px solid #d0daea;border-radius:9px;"
            f"padding:16px 18px;min-width:200px;flex:1'>"
            f"<div style='font-size:11px;color:#64748b;font-weight:700;margin-bottom:6px'>"
            f"STEP {u['step']}</div>"
            f"<div style='font-size:14px;font-weight:600;color:#1a3a5c;margin-bottom:8px'>"
            f"{u['description']}</div>"
            f"<div style='font-size:12px;color:#5a6e82'>&#x1F4C5; {u['estimated_date']} &nbsp;"
            f"<span style='background:{pc};color:#fff;font-size:11px;padding:1px 7px;"
            f"border-radius:3px'>{u['responsible']}</span></div>"
            f"</div>"
        )
    return "\n".join(cards)


def _overdue_html(overdue_steps):
    if not overdue_steps:
        return ""
    items = "".join(
        f"<li style='padding:5px 0'>Step {o['step']} &mdash; {o['description']} "
        f"<span style='color:#94a3b8'>(was due {o['estimated_date']})</span></li>"
        for o in overdue_steps
    )
    return (
        "<div style='background:#fdeaea;border:1px solid #f5c0c0;border-radius:10px;"
        "padding:18px 24px;margin-top:24px'>"
        "<div style='font-weight:700;color:#b83232;margin-bottom:10px;font-size:14px'>"
        "&#x26A0; Overdue Steps</div>"
        f"<ul style='padding-left:18px;font-size:13px;color:#7a2020;line-height:1'>{items}</ul>"
        "</div>"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  STAKEHOLDER DONUT CHARTS
# ─────────────────────────────────────────────────────────────────────────────

# Party definitions: name, header colour, ring colour
PARTIES = [
    ("Issuer",    "#1a3a5c", "#1a3a5c"),
    ("Network",   "#0072ce", "#0072ce"),
    ("Processor", "#1a7a4a", "#1a7a4a"),
    ("Embosser",  "#e8840f", "#e8840f"),
]

# Segment colours: Done, In Progress, ToDo, Blocked
SEG_COLORS = ["#1a7a4a", "#0072ce", "#d0daea", "#b83232"]


def compute_stakeholder_stats(steps):
    """Return list of per-party dicts with step counts broken down by status."""
    result = []
    for party_name, hdr_color, ring_color in PARTIES:
        # Include steps where this party appears anywhere in the responsible field
        party_steps = [
            s for s in steps
            if party_name.lower() in s["responsible"].lower()
        ]
        total   = len(party_steps)
        done    = sum(1 for s in party_steps if s["status"] == "Done")
        in_prog = sum(1 for s in party_steps if s["status"] == "In Progress")
        blocked = sum(1 for s in party_steps if s["status"] == "Blocked")
        todo    = total - done - in_prog - blocked
        result.append({
            "name":       party_name,
            "color":      hdr_color,
            "ring_color": ring_color,
            "total":      total,
            "done":       done,
            "in_progress": in_prog,
            "blocked":    blocked,
            "todo":       todo,
        })
    return result


def _make_donut_svg(p):
    """Generate an SVG donut chart for one party using stroke-dasharray segments."""
    R   = 38                          # ring radius
    SW  = 18                          # stroke-width (ring thickness)
    C   = 2 * math.pi * R             # circumference ≈ 238.76
    total = p["total"]

    # Background (empty) ring
    bg = (
        f"<circle cx='50' cy='50' r='{R}' fill='none' "
        f"stroke='#e2e8f0' stroke-width='{SW}'/>"
    )

    if total == 0:
        centre = (
            "<text x='50' y='52' text-anchor='middle' "
            "font-size='8' fill='#94a3b8'>No steps</text>"
        )
        return f"<svg viewBox='0 0 100 100' xmlns='http://www.w3.org/2000/svg'>{bg}{centre}</svg>"

    # One circle per segment, offset cumulatively
    segments = [
        (p["done"],        SEG_COLORS[0]),   # green
        (p["in_progress"], SEG_COLORS[1]),   # blue
        (p["todo"],        SEG_COLORS[2]),   # gray
        (p["blocked"],     SEG_COLORS[3]),   # red
    ]

    arcs   = []
    offset = 0.0
    for count, color in segments:
        if count == 0:
            continue
        seg_len = (count / total) * C
        arcs.append(
            f"<circle cx='50' cy='50' r='{R}' fill='none' "
            f"stroke='{color}' stroke-width='{SW}' "
            f"stroke-dasharray='{seg_len:.3f} 9999' "
            f"stroke-dashoffset='-{offset:.3f}' "
            f"transform='rotate(-90 50 50)'/>"
        )
        offset += seg_len

    pct    = round(p["done"] / total * 100)
    centre = (
        f"<text x='50' y='45' text-anchor='middle' dominant-baseline='middle' "
        f"font-size='15' font-weight='800' fill='{p['color']}'>{p['done']}</text>"
        f"<text x='50' y='58' text-anchor='middle' "
        f"font-size='8' fill='#64748b'>of {total} done</text>"
    )

    return (
        f"<svg viewBox='0 0 100 100' xmlns='http://www.w3.org/2000/svg'>"
        f"{bg}{''.join(arcs)}{centre}</svg>"
    )


def _stakeholder_charts_html(stats):
    """Return HTML for a row of 4 donut charts, one per party."""
    cards = []
    for p in stats:
        donut   = _make_donut_svg(p)
        total   = p["total"]
        pct     = round(p["done"] / total * 100) if total > 0 else 0
        color   = p["color"]
        name    = p["name"]
        done    = p["done"]
        in_prog = p["in_progress"]
        todo    = p["todo"]
        blocked = p["blocked"]
        step_lbl = "step" if total == 1 else "steps"

        # Mini legend pills (always show ToDo even if zero)
        pill_data = [
            (done,    SEG_COLORS[0], "Done"),
            (in_prog, SEG_COLORS[1], "In Progress"),
            (todo,    SEG_COLORS[2], "To Do"),
            (blocked, SEG_COLORS[3], "Blocked"),
        ]
        pills = "".join(
            "<div style='display:flex;align-items:center;gap:4px;"
            "font-size:11px;color:#5a6e82'>"
            "<span style='width:8px;height:8px;border-radius:50%;"
            "background:" + col + ";flex-shrink:0'></span>"
            + label + ": <strong>" + str(cnt) + "</strong></div>"
            for cnt, col, label in pill_data
            if cnt > 0 or label == "To Do"
        )

        card = (
            "<div style='flex:1;min-width:180px;max-width:260px;text-align:center;"
            "background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;"
            "padding:20px 16px'>"

            # Party badge
            "<div style='display:inline-block;background:" + color + ";color:#fff;"
            "font-size:11px;font-weight:700;letter-spacing:.7px;padding:3px 14px;"
            "border-radius:20px;margin-bottom:14px;text-transform:uppercase'>"
            + name + "</div>"

            # Donut chart
            "<div style='width:110px;height:110px;margin:0 auto'>" + donut + "</div>"

            # Pct label
            "<div style='font-size:13px;font-weight:700;color:" + color + ";margin-top:10px'>"
            + str(pct) + "% complete</div>"
            "<div style='font-size:11px;color:#94a3b8;margin-bottom:12px'>"
            + str(total) + " " + step_lbl + " assigned</div>"

            # Pills
            "<div style='display:inline-flex;flex-direction:column;gap:4px;"
            "text-align:left'>" + pills + "</div>"

            "</div>"
        )
        cards.append(card)

    return "\n".join(cards)


def render_tracker(objective, steps, s):
    today             = date.today()
    rag_col, rag_bg, rag_label = _rag_theme(s["rag"])
    step_rows         = _step_rows_html(steps, today)
    upcoming_cards    = _upcoming_cards_html(s["upcoming"])
    overdue_block     = _overdue_html(s["overdue_steps"])
    pct               = s["pct"]
    stakeholder_stats = compute_stakeholder_stats(steps)
    donut_charts      = _stakeholder_charts_html(stakeholder_stats)

    # ── CSS (written as one long string to avoid curly-brace escaping) ──────
    css = (
        "*{box-sizing:border-box;margin:0;padding:0}"
        "body{font-family:'Segoe UI',system-ui,sans-serif;background:#f0f4f8;color:#1e2d3d;font-size:15px;line-height:1.6}"
        "header{background:linear-gradient(135deg,#1a3a5c 0%,#0d5ca8 100%);color:#fff;padding:28px 48px}"
        ".back{font-size:13px;opacity:.75;text-decoration:none;color:#fff;margin-bottom:12px;display:inline-flex;align-items:center;gap:6px}"
        ".back:hover{opacity:1}"
        "header h1{font-size:1.35rem;font-weight:700;margin:8px 0 6px}"
        "header p{font-size:13px;opacity:.8;max-width:700px}"
        ".rbar{background:#162e4a;padding:10px 48px;display:flex;align-items:center;justify-content:space-between;border-top:1px solid rgba(255,255,255,.1)}"
        ".rbar span{font-size:12px;color:rgba(255,255,255,.72)}"
        ".rbtn{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.3);color:#fff;font-size:12px;padding:5px 15px;border-radius:6px;cursor:pointer;text-decoration:none;transition:background .2s}"
        ".rbtn:hover{background:rgba(255,255,255,.28)}"
        "main{max-width:1120px;margin:28px auto;padding:0 24px 64px}"
        ".card{background:#fff;border:1px solid #d0daea;border-radius:12px;padding:26px 30px;margin-bottom:22px}"
        ".ctitle{font-size:12px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.8px;margin-bottom:16px}"
        ".kpi-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:14px}"
        ".kpi{text-align:center;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px 10px}"
        ".kpi .v{font-size:2rem;font-weight:800;line-height:1.1;margin-bottom:4px}"
        ".kpi .l{font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.5px}"
        "table{width:100%;border-collapse:collapse;font-size:13.5px}"
        "th{background:#1a3a5c;color:#fff;font-weight:600;padding:10px 14px;text-align:left;font-size:12px;letter-spacing:.3px}"
        "td{padding:9px 14px;border-bottom:1px solid #e8edf4;vertical-align:middle}"
        "tr:last-child td{border-bottom:none}"
        "tr:nth-child(even) td{background:#f8fafc}"
        "tr:hover td{background:#eef5fd!important}"
        "#cd{font-weight:700;color:#fff}"
    )

    js = (
        "let secs=" + str(AUTO_REFRESH_S) + ";"
        "function tick(){"
        "  document.getElementById('cd').textContent=secs+'s';"
        "  if(--secs<0)location.reload();"
        "  else setTimeout(tick,1000);"
        "}"
        "window.onload=tick;"
    )

    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "<meta charset='UTF-8'/>",
        "<meta name='viewport' content='width=device-width,initial-scale=1.0'/>",
        "<meta http-equiv='Cache-Control' content='no-cache,no-store,must-revalidate'/>",
        "<meta http-equiv='Pragma' content='no-cache'/>",
        "<meta http-equiv='Expires' content='0'/>",
        "<title>BIN Procurement Status Tracker</title>",
        f"<style>{css}</style>",
        f"<script>{js}</script>",
        "</head>",
        "<body>",

        # ── Header ──────────────────────────────────────────────────────────
        "<header>",
        "  <a class='back' href='/'>&#8592; Back to Project Hub</a>",
        "  <h1>&#x1F4B3; New BIN Procurement &mdash; Card Launch Status Tracker</h1>",
        f"  <p>{objective}</p>",
        "</header>",

        # ── Refresh bar ─────────────────────────────────────────────────────
        "<div class='rbar'>",
        f"  <span>&#x1F534; Live Data &nbsp;&middot;&nbsp; Last refreshed: "
        f"<strong style='color:#fff'>{s['as_of']}</strong>"
        f" &nbsp;&middot;&nbsp; Auto-refresh in <span id='cd'>{AUTO_REFRESH_S}s</span></span>",
        "  <a class='rbtn' href='/bin-tracker'>&#x21BA; Refresh Now</a>",
        "</div>",

        "<main>",

        # ── Project Objective card ───────────────────────────────────────────
        "<div class='card' style='border-left:5px solid #0072ce'>",
        "  <div class='ctitle'>Project Objective</div>",

        # Objective banner
        f"  <div style='background:#eef5fd;border-radius:8px;padding:16px 20px;margin-bottom:20px;"
        f"font-size:15px;font-weight:600;color:#1a3a5c;line-height:1.5'>"
        f"  &#x1F3AF; {objective}"
        f"  </div>",

        # What is BIN / context
        "  <div style='display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px'>",

        "    <div>",
        "      <div style='font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;"
        "letter-spacing:.6px;margin-bottom:8px'>What is a BIN?</div>",
        "      <div style='font-size:13.5px;color:#1e2d3d;line-height:1.65'>",
        "        A <strong>Bank Identification Number (BIN)</strong> is the first 6&ndash;8 digits of a "
        "payment card number. It uniquely identifies the issuing institution and card programme on the "
        "payment network. Every new card product requires a dedicated BIN to be formally procured, "
        "activated, and configured across all parties before any card can be issued or transacted.",
        "      </div>",
        "    </div>",

        "    <div>",
        "      <div style='font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;"
        "letter-spacing:.6px;margin-bottom:8px'>What We Are Doing</div>",
        "      <div style='font-size:13.5px;color:#1e2d3d;line-height:1.65'>",
        "        We are coordinating a <strong>31-step end-to-end BIN procurement process</strong> for "
        "a new card launch. This includes network project initiation, BIN ordering, cryptographic card "
        "key generation and exchange, settlement endpoint setup, MDES tokenisation enablement, card "
        "personalisation and shipping, transaction validation, and final project closure &mdash; "
        "targeting a live card launch by <strong>10 Oct 2026</strong>.",
        "      </div>",
        "    </div>",
        "  </div>",

        # Stakeholder row
        "  <div style='margin-bottom:8px'>",
        "    <div style='font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;"
        "letter-spacing:.6px;margin-bottom:10px'>Key Stakeholders</div>",
        "    <div style='display:flex;flex-wrap:wrap;gap:10px'>",
        "      <div style='background:#e8edf4;border-radius:8px;padding:10px 16px;min-width:150px'>",
        "        <div style='font-size:10px;color:#64748b;font-weight:700;margin-bottom:4px'>&#x1F3E6; ISSUER</div>",
        "        <div style='font-size:13px;color:#1a3a5c;font-weight:600'>Card-issuing Bank</div>",
        "        <div style='font-size:12px;color:#5a6e82;margin-top:2px'>Project owner &amp; approver</div>",
        "      </div>",
        "      <div style='background:#e3eefc;border-radius:8px;padding:10px 16px;min-width:150px'>",
        "        <div style='font-size:10px;color:#0072ce;font-weight:700;margin-bottom:4px'>&#x1F310; NETWORK</div>",
        "        <div style='font-size:13px;color:#1a3a5c;font-weight:600'>Card Scheme</div>",
        "        <div style='font-size:12px;color:#5a6e82;margin-top:2px'>BIN allocation &amp; network setup</div>",
        "      </div>",
        "      <div style='background:#e6f4ed;border-radius:8px;padding:10px 16px;min-width:150px'>",
        "        <div style='font-size:10px;color:#1a7a4a;font-weight:700;margin-bottom:4px'>&#x2699;&#xFE0F; PROCESSOR</div>",
        "        <div style='font-size:13px;color:#1a3a5c;font-weight:600'>Payment Processor</div>",
        "        <div style='font-size:12px;color:#5a6e82;margin-top:2px'>Card keys &amp; authorisation</div>",
        "      </div>",
        "      <div style='background:#fff0e0;border-radius:8px;padding:10px 16px;min-width:150px'>",
        "        <div style='font-size:10px;color:#e8840f;font-weight:700;margin-bottom:4px'>&#x1F4E6; EMBOSSER</div>",
        "        <div style='font-size:13px;color:#1a3a5c;font-weight:600'>Card Manufacturer</div>",
        "        <div style='font-size:12px;color:#5a6e82;margin-top:2px'>Card fulfilment &amp; shipping</div>",
        "      </div>",
        "    </div>",
        "  </div>",

        "</div>",   # end Project Objective card

        # ── Executive Summary card ───────────────────────────────────────────
        "<div class='card'>",
        "  <div class='ctitle'>Executive Summary</div>",

        # Narrative summary paragraph (generated from live data)
        f"  <div style='background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;"
        f"padding:16px 20px;margin-bottom:20px;font-size:13.5px;color:#1e2d3d;line-height:1.7'>",
        f"    <strong>As of {s['as_of'][:11]},</strong> the New BIN Procurement project is "
        f"    <strong style='color:{rag_col}'>{rag_label}</strong>. "
        f"    {s['done']} of {s['total']} steps have been completed ({pct}%), with "
        f"    {s['in_progress']} step{'s' if s['in_progress'] != 1 else ''} currently in progress and "
        f"    {s['todo']} step{'s' if s['todo'] != 1 else ''} yet to begin. "
        + (
            f"    <span style='color:#b83232;font-weight:600'>{s['overdue']} step{'s are' if s['overdue'] != 1 else ' is'} overdue</span> "
            f"    and require immediate attention to protect the launch timeline. "
            if s['overdue'] > 0 else
            "    No steps are currently overdue. "
        )
        + f"    There are <strong>{s['days_to_launch']} days</strong> remaining to the target card launch date of <strong>10 Oct 2026</strong>.",
        "  </div>",

        "  <div style='display:flex;align-items:center;gap:22px;margin-bottom:22px;flex-wrap:wrap'>",

        # RAG badge
        f"  <div style='background:{rag_bg};border:2px solid {rag_col};border-radius:10px;"
        f"padding:14px 26px;text-align:center;flex-shrink:0'>",
        f"    <div style='font-size:1.55rem;font-weight:900;color:{rag_col}'>{rag_label}</div>",
        f"    <div style='font-size:10px;color:{rag_col};margin-top:4px;font-weight:700;"
        f"letter-spacing:.6px'>OVERALL PROJECT STATUS</div>",
        "  </div>",

        # Progress bar
        "  <div style='flex:1;min-width:240px'>",
        "    <div style='font-size:13px;color:#64748b;margin-bottom:8px'>Overall Completion</div>",
        "    <div style='background:#e2e8f0;border-radius:8px;height:14px;width:100%'>",
        f"      <div style='background:#1a7a4a;width:{pct}%;height:100%;border-radius:8px'></div>",
        "    </div>",
        f"    <div style='font-size:12px;color:#64748b;margin-top:6px'>{s['done']} of {s['total']} steps complete ({pct}%)</div>",
        "  </div>",

        # Days to launch
        "  <div style='text-align:center;min-width:110px'>",
        f"    <div style='font-size:2.4rem;font-weight:800;color:#0072ce;line-height:1'>{s['days_to_launch']}</div>",
        "    <div style='font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;margin-top:4px'>Days to Launch</div>",
        "    <div style='font-size:11px;color:#94a3b8;margin-top:3px'>Target: 10 Oct 2026</div>",
        "  </div>",
        "  </div>",   # close flex row

        # KPI tiles
        "  <div class='kpi-grid'>",
        f"    <div class='kpi'><div class='v' style='color:#1a3a5c'>{s['total']}</div><div class='l'>Total Steps</div></div>",
        f"    <div class='kpi'><div class='v' style='color:#1a7a4a'>{s['done']}</div><div class='l'>Completed</div></div>",
        f"    <div class='kpi'><div class='v' style='color:#0072ce'>{s['in_progress']}</div><div class='l'>In Progress</div></div>",
        f"    <div class='kpi'><div class='v' style='color:#64748b'>{s['todo']}</div><div class='l'>To Do</div></div>",
        f"    <div class='kpi'><div class='v' style='color:#b83232'>{s['overdue']}</div><div class='l'>Overdue</div></div>",
        f"    <div class='kpi'><div class='v' style='color:#c47a00'>{pct}%</div><div class='l'>Complete</div></div>",
        "  </div>",

        overdue_block,
        "</div>",   # end Executive Summary card

        # ── Next Milestones card ─────────────────────────────────────────────
        "<div class='card'>",
        "  <div class='ctitle'>Next Milestones</div>",
        f"  <div style='display:flex;gap:16px;flex-wrap:wrap'>{upcoming_cards}</div>",
        "</div>",

        # ── Stakeholder Donut Charts ──────────────────────────────────────────
        "<div class='card'>",
        "  <div class='ctitle'>Stakeholder Progress Overview</div>",
        "  <div style='font-size:13px;color:#5a6e82;margin-bottom:18px;line-height:1.5'>",
        "    Step completion broken down by responsible party. Steps shared between two parties "
        "(e.g. Network &amp; Processor) are counted for both.",
        "  </div>",
        "  <div style='display:flex;flex-wrap:wrap;gap:16px;justify-content:flex-start'>",
        f"    {donut_charts}",
        "  </div>",
        "  <div style='display:flex;flex-wrap:wrap;gap:16px;margin-top:18px;padding-top:16px;"
        "border-top:1px solid #e2e8f0'>",
        "    <div style='display:flex;align-items:center;gap:6px;font-size:12px;color:#5a6e82'>"
        f"<span style='width:10px;height:10px;border-radius:50%;background:{SEG_COLORS[0]};display:inline-block'></span>Done</div>",
        "    <div style='display:flex;align-items:center;gap:6px;font-size:12px;color:#5a6e82'>"
        f"<span style='width:10px;height:10px;border-radius:50%;background:{SEG_COLORS[1]};display:inline-block'></span>In Progress</div>",
        "    <div style='display:flex;align-items:center;gap:6px;font-size:12px;color:#5a6e82'>"
        f"<span style='width:10px;height:10px;border-radius:50%;background:{SEG_COLORS[2]};display:inline-block'></span>To Do</div>",
        "    <div style='display:flex;align-items:center;gap:6px;font-size:12px;color:#5a6e82'>"
        f"<span style='width:10px;height:10px;border-radius:50%;background:{SEG_COLORS[3]};display:inline-block'></span>Blocked</div>",
        "  </div>",
        "</div>",

        # ── Steps detail table ───────────────────────────────────────────────
        "<div class='card'>",
        "  <div class='ctitle'>All 31 Steps &mdash; Detailed Status</div>",
        "  <div style='overflow-x:auto'>",
        "  <table>",
        "    <thead><tr>",
        "      <th style='width:54px'>Step</th>",
        "      <th>Description</th>",
        "      <th>Responsible</th>",
        "      <th>Est. Date</th>",
        "      <th>Completed</th>",
        "      <th>Status</th>",
        "      <th>Timeline</th>",
        "    </tr></thead>",
        f"    <tbody>{step_rows}</tbody>",
        "  </table>",
        "  </div>",
        "</div>",

        # ── Legend ───────────────────────────────────────────────────────────
        "<div class='card' style='padding:18px 26px'>",
        "  <div class='ctitle'>Legend</div>",
        "  <div style='display:flex;flex-wrap:wrap;gap:14px;font-size:13px;align-items:center'>",
        "    <span><span style='background:#1a3a5c;color:#fff;font-size:11px;padding:2px 8px;border-radius:4px'>Issuer</span></span>",
        "    <span><span style='background:#0072ce;color:#fff;font-size:11px;padding:2px 8px;border-radius:4px'>Network</span></span>",
        "    <span><span style='background:#1a7a4a;color:#fff;font-size:11px;padding:2px 8px;border-radius:4px'>Processor</span></span>",
        "    <span><span style='background:#e8840f;color:#fff;font-size:11px;padding:2px 8px;border-radius:4px'>Embosser</span></span>",
        "    <span><span style='background:#7b2d8b;color:#fff;font-size:11px;padding:2px 8px;border-radius:4px'>Network + Processor</span></span>",
        "    <span><span style='background:#b83232;color:#fff;font-size:11px;padding:2px 8px;border-radius:4px'>Issuer + Processor</span></span>",
        "    <span style='margin-left:8px;color:#5a6e82'>",
        "      <span style='background:#7b2d8b;color:#fff;font-size:10px;padding:1px 5px;border-radius:3px'>&#x26BF; SECURE</span>",
        "      = Elevated security step (Steps 9&ndash;12, AI disabled)",
        "    </span>",
        "  </div>",
        "</div>",

        "</main>",
        f"<footer style='text-align:center;padding:22px;font-size:12px;color:#94a3b8;border-top:1px solid #e2e8f0'>"
        f"BIN Procurement Status Tracker &nbsp;&middot;&nbsp; Source: Project_Input_BIN_SS.xlsx "
        f"&nbsp;&middot;&nbsp; Refreshed: {s['as_of']}</footer>",
        "</body>",
        "</html>",
    ]

    return "\n".join(html_parts)


# ─────────────────────────────────────────────────────────────────────────────
#  HTTP REQUEST HANDLER
# ─────────────────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        # Normalise path (strip query string and trailing slash)
        path = self.path.split("?")[0].rstrip("/") or "/"

        try:
            if path in ("/", ""):
                body = render_landing().encode("utf-8")
            elif path == "/bin-tracker":
                objective, steps = read_project_data()
                summary          = compute_summary(steps)
                body             = render_tracker(objective, steps, summary).encode("utf-8")
            elif path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            else:
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h2 style='font-family:sans-serif;padding:40px'>404 &mdash; Page not found</h2>")
                return

            self.send_response(200)
            self.send_header("Content-Type",   "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control",  "no-cache, no-store, must-revalidate")
            self.send_header("Pragma",         "no-cache")
            self.send_header("Expires",        "0")
            self.end_headers()
            self.wfile.write(body)

        except FileNotFoundError:
            self.send_response(500)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            msg = (
                "<h2 style='font-family:sans-serif;padding:40px;color:#b83232'>"
                "&#x26A0; Excel file not found</h2>"
                f"<p style='font-family:sans-serif;padding:0 40px'>"
                f"Make sure <strong>Project_Input_BIN_SS.xlsx</strong> is in the same folder as server.py."
                f"</p>"
            )
            self.wfile.write(msg.encode("utf-8"))

        except Exception:
            err = traceback.format_exc()
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"Server error:\n\n{err}".encode("utf-8"))
            print(f"[ERROR] {err}")

    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}]  {fmt % args}")


# ─────────────────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    server = HTTPServer(("localhost", PORT), Handler)

    print(f"""
╔══════════════════════════════════════════════════════════╗
║        BIN Procurement  —  Local Status Server           ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  Landing page:   http://localhost:{PORT}                   ║
║  Status tracker: http://localhost:{PORT}/bin-tracker       ║
║                                                          ║
║  Data source: Project_Input_BIN_SS.xlsx                  ║
║  (Must be in the same folder as this script)             ║
║                                                          ║
║  Auto-refresh:  every {AUTO_REFRESH_S} seconds                        ║
║  Press Ctrl+C to stop                                    ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
""")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Stopped]  Server shut down cleanly.")
