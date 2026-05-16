#!/usr/bin/env python3
"""
BIN Procurement local server.
  GET /            → landing page
  GET /bin-tracker → live status tracker (reads Excel on every request, saves Project_StatusTracker.html)
  GET /*           → static file serving
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import os, zipfile, xml.etree.ElementTree as ET, math
from datetime import date, timedelta, datetime

PORT             = 8080
BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
EXCEL_FILENAME   = "Project_Input_BIN_SS.xlsx"
TRACKER_FILENAME = "Project_StatusTracker.html"
LAUNCH_DATE      = date(2026, 10, 10)
AUTO_REFRESH_S   = 60

PARTIES = [
    ("Issuer",    "#1a3a5c", "#e8f0fa"),
    ("Network",   "#0072ce", "#e5f2ff"),
    ("Processor", "#1a7a4a", "#e6f4ed"),
    ("Embosser",  "#e8840f", "#fff4e5"),
]
SEG_COLORS = {"Done": "#1a7a4a", "In Progress": "#0072ce", "ToDo": "#d0daea", "Blocked": "#b83232"}
RAG_COLOR  = {"GREEN": "#1a7a4a", "AMBER": "#e8840f", "RED": "#b83232"}


# ── Excel parsing ──────────────────────────────────────────────────────────────
def _xl_date_str(serial):
    if not serial: return ''
    try:
        n = int(float(serial))
        return (date(1899, 12, 30) + timedelta(days=n)).strftime('%d %b %Y')
    except Exception:
        return serial

def _xl_date_obj(serial):
    if not serial: return None
    try:
        n = int(float(serial))
        return date(1899, 12, 30) + timedelta(days=n)
    except Exception:
        return None

def read_project_data():
    excel_path = os.path.join(BASE_DIR, EXCEL_FILENAME)
    NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    with zipfile.ZipFile(excel_path) as z:
        with z.open('xl/sharedStrings.xml') as f:
            ss_tree = ET.parse(f)
        sst = [''.join(t.text or '' for t in si.iter(f'{{{NS}}}t'))
               for si in ss_tree.findall(f'.//{{{NS}}}si')]
        with z.open('xl/worksheets/sheet1.xml') as f:
            ws_tree = ET.parse(f)

    def cv(c):
        t = c.get('t', '')
        v = c.find(f'{{{NS}}}v')
        if v is None: return ''
        if t == 's': return sst[int(v.text)]
        return v.text or ''

    rows = ws_tree.findall(f'.//{{{NS}}}row')
    r1_cells = rows[0].findall(f'{{{NS}}}c')
    objective = cv(r1_cells[0]).strip() if r1_cells else ''

    steps = []
    for row in rows[4:]:
        cells = {c.get('r', '')[0]: cv(c) for c in row.findall(f'{{{NS}}}c')}
        step_no = cells.get('A', '').strip()
        if not step_no or not step_no.isdigit():
            continue
        steps.append({
            'num':         int(step_no),
            'description': cells.get('B', '').strip(),
            'responsible': cells.get('C', '').strip(),
            'notes':       cells.get('D', '').strip(),
            'status':      cells.get('E', 'ToDo').strip(),
            'est_date':    _xl_date_str(cells.get('F', '')),
            'comp_date':   _xl_date_str(cells.get('G', '')),
            'est_obj':     _xl_date_obj(cells.get('F', '')),
        })
    return objective, steps


# ── Summary + stakeholder stats ────────────────────────────────────────────────
def compute_summary(steps):
    today   = date.today()
    total   = len(steps)
    done    = sum(1 for s in steps if s['status'] == 'Done')
    in_prog = sum(1 for s in steps if s['status'] == 'In Progress')
    blocked = sum(1 for s in steps if s['status'] == 'Blocked')
    todo    = sum(1 for s in steps if s['status'] == 'ToDo')
    overdue = sum(1 for s in steps if s['status'] not in ('Done',)
                  and s['est_obj'] and s['est_obj'] < today)
    upcoming = sum(1 for s in steps if s['status'] == 'ToDo'
                   and s['est_obj'] and 0 <= (s['est_obj'] - today).days <= 14)
    pct      = round(done / total * 100) if total else 0
    days_left = (LAUNCH_DATE - today).days
    rag      = 'GREEN' if overdue == 0 else ('AMBER' if overdue <= 3 else 'RED')
    return dict(total=total, done=done, in_progress=in_prog, blocked=blocked,
                todo=todo, overdue=overdue, upcoming=upcoming, pct=pct,
                days_to_launch=days_left, rag=rag,
                as_of=today.strftime('%d %b %Y'))

def compute_stakeholder_stats(steps):
    stats = []
    for (party, color, bg) in PARTIES:
        mine    = [s for s in steps if party.lower() in s['responsible'].lower()]
        done    = sum(1 for s in mine if s['status'] == 'Done')
        in_prog = sum(1 for s in mine if s['status'] == 'In Progress')
        todo    = sum(1 for s in mine if s['status'] == 'ToDo')
        blocked = sum(1 for s in mine if s['status'] == 'Blocked')
        stats.append(dict(party=party, color=color, bg=bg, total=len(mine),
                          done=done, in_progress=in_prog, todo=todo, blocked=blocked))
    return stats


# ── SVG donut ─────────────────────────────────────────────────────────────────
def _make_donut_svg(segs, cx=50, cy=50, r=34, sw=16):
    circ = 2 * math.pi * r
    total = sum(s[0] for s in segs) or 1
    shapes, offset = [], 0.0
    gap = 0.8
    for count, _, color in segs:
        if count == 0:
            continue
        frac = count / total
        seg_len = max(0.0, frac * circ - gap)
        shapes.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" '
            f'stroke-width="{sw}" '
            f'stroke-dasharray="{seg_len:.2f} 9999" '
            f'stroke-dashoffset="-{offset:.2f}" '
            f'transform="rotate(-90 {cx} {cy})"/>'
        )
        offset += frac * circ
    return '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">' + ''.join(shapes) + '</svg>'

def _stakeholder_charts_html(stats):
    cards = []
    for p in stats:
        color = p['color']
        bg    = p['bg']
        total = p['total']
        segs  = [
            (p['done'],        total, SEG_COLORS['Done']),
            (p['in_progress'], total, SEG_COLORS['In Progress']),
            (p['todo'],        total, SEG_COLORS['ToDo']),
            (p['blocked'],     total, SEG_COLORS['Blocked']),
        ]
        svg = _make_donut_svg(segs)
        pct = round(p['done'] / total * 100) if total else 0
        card = (
            '<div class="sh-card" style="border-top:3px solid ' + color + ';background:' + bg + '">'
            '<div class="sh-title" style="color:' + color + '">' + p['party'] + '</div>'
            '<div class="sh-donut">' + svg +
            '<div class="sh-pct">' + str(pct) + '%</div></div>'
            '<div class="sh-legend">'
            '<span class="leg-dot" style="background:' + SEG_COLORS['Done'] + '"></span>Done: ' + str(p['done']) + ' &nbsp;'
            '<span class="leg-dot" style="background:' + SEG_COLORS['In Progress'] + '"></span>Active: ' + str(p['in_progress']) + ' &nbsp;'
            '<span class="leg-dot" style="background:' + SEG_COLORS['ToDo'] + '"></span>ToDo: ' + str(p['todo']) + ' &nbsp;'
            '</div>'
            '<div class="sh-total">Total steps: ' + str(total) + '</div>'
            '</div>'
        )
        cards.append(card)
    return '<div class="sh-grid">' + '\n'.join(cards) + '</div>'


# ── Tracker HTML ───────────────────────────────────────────────────────────────
def render_tracker(objective, steps, s):
    rag = s['rag']
    rc  = RAG_COLOR[rag]
    pct = s['pct']
    today = date.today()

    ov_segs = [
        (s['done'],        s['total'], SEG_COLORS['Done']),
        (s['in_progress'], s['total'], SEG_COLORS['In Progress']),
        (s['todo'],        s['total'], SEG_COLORS['ToDo']),
        (s['blocked'],     s['total'], SEG_COLORS['Blocked']),
    ]
    ov_svg = _make_donut_svg(ov_segs, r=38, sw=18)
    sh_html = _stakeholder_charts_html(compute_stakeholder_stats(steps))

    # Table rows
    rows_html = []
    for step in steps:
        st = step['status']
        if   st == 'Done':        cls, dot = 'status-done',  '#1a7a4a'
        elif st == 'In Progress': cls, dot = 'status-ip',    '#0072ce'
        elif st == 'Blocked':     cls, dot = 'status-block', '#b83232'
        else:                     cls, dot = 'status-todo',  '#94a3b8'
        overdue_tag = ''
        if st != 'Done' and step['est_obj'] and step['est_obj'] < today:
            overdue_tag = ' <span class="overdue-tag">OVERDUE</span>'
        notes = step['notes'] if step['notes'] and step['notes'] != 's' else ''
        rows_html.append(
            '<tr>'
            '<td class="num-col">' + str(step['num']) + '</td>'
            '<td>' + step['description'] + '</td>'
            '<td>' + step['responsible'] + '</td>'
            '<td><span class="' + cls + '">'
            '<span class="dot" style="background:' + dot + '"></span>' + st + '</span>' + overdue_tag + '</td>'
            '<td>' + step['est_date'] + '</td>'
            '<td>' + (step['comp_date'] or '—') + '</td>'
            '<td class="notes-col">' + notes + '</td>'
            '</tr>'
        )
    table_rows = '\n'.join(rows_html)

    # Executive summary
    days_text = f"{s['days_to_launch']} days" if s['days_to_launch'] > 0 else "LAUNCHED"
    exec_sum = (
        f"The BIN Procurement project is <strong>{pct}% complete</strong> with "
        f"<strong>{s['done']} of {s['total']}</strong> steps finished. "
        f"<strong>{s['in_progress']}</strong> step(s) are actively in progress "
        f"and <strong>{s['todo']}</strong> remain in the queue. "
    )
    if s['overdue'] > 0:
        exec_sum += (f"<strong style='color:{RAG_COLOR['RED']}'>{s['overdue']} step(s) are overdue</strong>"
                     ", requiring immediate attention. ")
    else:
        exec_sum += "All steps are on or ahead of schedule. "
    if s['upcoming'] > 0:
        exec_sum += f"<strong>{s['upcoming']}</strong> step(s) are due within the next 14 days. "
    exec_sum += (
        f"The target card launch is <strong>{LAUNCH_DATE.strftime('%d %b %Y')}</strong> "
        f"— <strong>{days_text}</strong> away. "
        f"Overall health is rated <strong style='color:{rc}'>{rag}</strong>."
    )

    now_str = datetime.now().strftime('%d %b %Y, %H:%M')
    launch_str = LAUNCH_DATE.strftime('%d %b %Y')

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>BIN Procurement — Status Tracker</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial;background:#f0f4f8;color:#1e2d3d;font-size:14px}}
header{{background:linear-gradient(135deg,#1a3a5c 0%,#0d5ca8 100%);color:#fff;padding:22px 36px;display:flex;gap:16px;align-items:center}}
.logo{{width:44px;height:44px;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,.15);border-radius:10px;font-size:22px}}
.header-text h1{{font-size:1.15rem;margin-bottom:3px}}
.header-text p{{font-size:12px;color:rgba(255,255,255,.85)}}
.refresh-info{{margin-left:auto;font-size:11px;color:rgba(255,255,255,.7);text-align:right;line-height:1.8}}
main{{max-width:1120px;margin:24px auto;padding:0 20px 40px}}
.top-cards{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px}}
.card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:20px}}
.card-label{{font-size:11px;font-weight:700;text-transform:uppercase;color:#64748b;margin-bottom:8px;letter-spacing:.5px}}
.card p{{font-size:13px;line-height:1.7;color:#475569}}
.kpi-row{{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:20px}}
.kpi{{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px 12px;text-align:center}}
.kpi-val{{font-size:26px;font-weight:700;line-height:1}}
.kpi-lbl{{font-size:11px;color:#64748b;margin-top:4px;font-weight:600;text-transform:uppercase}}
.kpi-done{{color:#1a7a4a}}.kpi-ip{{color:#0072ce}}.kpi-todo{{color:#94a3b8}}
.kpi-overdue{{color:#b83232}}.kpi-pct{{color:#1a3a5c}}
.overview-row{{display:grid;grid-template-columns:165px 1fr;gap:16px;margin-bottom:20px}}
.donut-card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:18px;display:flex;flex-direction:column;align-items:center;justify-content:center}}
.donut-wrap{{position:relative;width:110px;height:110px}}
.donut-wrap svg{{width:110px;height:110px}}
.donut-center{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;flex-direction:column}}
.donut-pct{{font-size:22px;font-weight:800;color:#1a3a5c}}
.donut-sub{{font-size:10px;color:#64748b;margin-top:2px}}
.ov-legend{{display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:10px}}
.leg-item{{display:flex;align-items:center;gap:5px;font-size:12px;color:#475569}}
.leg-sq{{width:10px;height:10px;border-radius:2px;flex-shrink:0}}
.section-title{{font-size:12px;font-weight:700;text-transform:uppercase;color:#64748b;letter-spacing:.5px;margin-bottom:12px}}
.sh-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px}}
.sh-card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px;text-align:center}}
.sh-title{{font-size:13px;font-weight:700;margin-bottom:10px}}
.sh-donut{{position:relative;width:90px;height:90px;margin:0 auto 10px}}
.sh-donut svg{{width:90px;height:90px}}
.sh-pct{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:800;color:#1a3a5c}}
.sh-legend{{font-size:11px;color:#475569;margin-bottom:6px}}
.leg-dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:2px;vertical-align:middle}}
.sh-total{{font-size:11px;color:#94a3b8;font-weight:600}}
.table-wrap{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden}}
table{{width:100%;border-collapse:collapse}}
th{{background:#f8fafc;font-size:11px;text-transform:uppercase;color:#475569;font-weight:700;padding:10px 12px;text-align:left;border-bottom:1px solid #e2e8f0;white-space:nowrap}}
td{{padding:9px 12px;border-bottom:1px solid #f1f5f9;vertical-align:top;font-size:13px}}
tr:last-child td{{border-bottom:none}}
tr:hover td{{background:#f8fafc}}
.num-col{{color:#94a3b8;font-weight:700;width:36px}}
.notes-col{{color:#64748b;font-style:italic;max-width:180px}}
.status-done{{background:#e6f4ed;color:#1a7a4a;padding:2px 8px;border-radius:20px;font-size:12px;font-weight:600;display:inline-flex;align-items:center;gap:4px;white-space:nowrap}}
.status-ip{{background:#e5f2ff;color:#0072ce;padding:2px 8px;border-radius:20px;font-size:12px;font-weight:600;display:inline-flex;align-items:center;gap:4px;white-space:nowrap}}
.status-todo{{background:#f1f5f9;color:#64748b;padding:2px 8px;border-radius:20px;font-size:12px;font-weight:600;display:inline-flex;align-items:center;gap:4px;white-space:nowrap}}
.status-block{{background:#fde8e8;color:#b83232;padding:2px 8px;border-radius:20px;font-size:12px;font-weight:600;display:inline-flex;align-items:center;gap:4px;white-space:nowrap}}
.dot{{width:6px;height:6px;border-radius:50%;flex-shrink:0}}
.overdue-tag{{background:#b83232;color:#fff;font-size:10px;font-weight:700;padding:1px 5px;border-radius:4px;margin-left:4px}}
footer{{text-align:center;color:#94a3b8;margin-top:24px;font-size:12px;padding-bottom:20px}}
</style>
</head>
<body>
<header>
  <div class="logo">🏦</div>
  <div class="header-text">
    <h1>BIN Procurement — Status Tracker</h1>
    <p>Payments Division · New Card Launch Programme</p>
  </div>
  <div class="refresh-info">
    Last loaded: {now_str}<br>
    <a href="/bin-tracker" style="color:rgba(255,255,255,.85);font-size:11px">↻ Refresh now</a>
    &nbsp;|&nbsp; <span id="cd">{AUTO_REFRESH_S}s</span> auto-refresh
  </div>
</header>

<main>
  <div class="top-cards">
    <div class="card">
      <div class="card-label">📋 Project Objective</div>
      <p>{objective}</p>
    </div>
    <div class="card">
      <div class="card-label">📊 Executive Summary</div>
      <p>{exec_sum}</p>
    </div>
  </div>

  <div class="kpi-row">
    <div class="kpi"><div class="kpi-val kpi-pct">{pct}%</div><div class="kpi-lbl">Complete</div></div>
    <div class="kpi"><div class="kpi-val kpi-done">{s['done']}</div><div class="kpi-lbl">Done</div></div>
    <div class="kpi"><div class="kpi-val kpi-ip">{s['in_progress']}</div><div class="kpi-lbl">In Progress</div></div>
    <div class="kpi"><div class="kpi-val kpi-todo">{s['todo']}</div><div class="kpi-lbl">To Do</div></div>
    <div class="kpi"><div class="kpi-val kpi-overdue">{s['overdue']}</div><div class="kpi-lbl">Overdue</div></div>
    <div class="kpi"><div class="kpi-val" style="font-size:18px;font-weight:800;color:{rc}">{rag}</div><div class="kpi-lbl">Health · {s['days_to_launch']}d left</div></div>
  </div>

  <div class="overview-row">
    <div class="donut-card">
      <div class="card-label" style="text-align:center;margin-bottom:10px">Overall Progress</div>
      <div class="donut-wrap">
        {ov_svg}
        <div class="donut-center">
          <div class="donut-pct">{pct}%</div>
          <div class="donut-sub">done</div>
        </div>
      </div>
      <div class="ov-legend">
        <div class="leg-item"><div class="leg-sq" style="background:#1a7a4a"></div>Done: {s['done']}</div>
        <div class="leg-item"><div class="leg-sq" style="background:#0072ce"></div>Active: {s['in_progress']}</div>
        <div class="leg-item"><div class="leg-sq" style="background:#d0daea"></div>ToDo: {s['todo']}</div>
        <div class="leg-item"><div class="leg-sq" style="background:#b83232"></div>Blocked: {s['blocked']}</div>
      </div>
    </div>
    <div class="card" style="padding:18px 22px">
      <div class="card-label" style="margin-bottom:16px">📅 Timeline Snapshot — as of {s['as_of']}</div>
      <div style="display:flex;gap:28px;flex-wrap:wrap">
        <div><div style="font-size:22px;font-weight:800;color:#1a3a5c">{launch_str}</div><div style="font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;margin-top:3px">Target Launch</div></div>
        <div><div style="font-size:22px;font-weight:800;color:#0072ce">{s['days_to_launch']}</div><div style="font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;margin-top:3px">Days Remaining</div></div>
        <div><div style="font-size:22px;font-weight:800;color:#e8840f">{s['upcoming']}</div><div style="font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;margin-top:3px">Due in 14 Days</div></div>
        <div><div style="font-size:22px;font-weight:800;color:{RAG_COLOR['RED']}">{s['overdue']}</div><div style="font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase;margin-top:3px">Overdue</div></div>
      </div>
    </div>
  </div>

  <div class="section-title">Stakeholder Progress</div>
  {sh_html}

  <div class="section-title">All Steps ({s['total']} total)</div>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th>#</th><th>Description</th><th>Responsible</th>
        <th>Status</th><th>Est. Date</th><th>Completed</th><th>Notes</th>
      </tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </div>
</main>

<footer>BIN Procurement Tracker &middot; {now_str} &middot; Source: {EXCEL_FILENAME}</footer>

<script>
var secs={AUTO_REFRESH_S};
var el=document.getElementById('cd');
function tick(){{secs--;if(secs<=0){{window.location.reload();return;}}if(el)el.textContent=secs+'s';setTimeout(tick,1000);}}
setTimeout(tick,1000);
</script>
</body>
</html>"""


# ── Landing page ───────────────────────────────────────────────────────────────
def render_landing(now):
    return f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'/>
<meta name='viewport' content='width=device-width,initial-scale=1'/>
<title>Robin Khatwani Projects</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,"Helvetica Neue",Arial;background:#f0f4f8;color:#1e2d3d}}
  header{{background:linear-gradient(135deg,#1a3a5c 0%,#0d5ca8 100%);color:#fff;padding:28px 40px;display:flex;gap:16px;align-items:center}}
  .logo{{width:48px;height:48px;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,.12);border-radius:10px;font-size:24px}}
  main{{max-width:980px;margin:32px auto;padding:20px}}
  .sect-title{{font-size:12px;color:#64748b;font-weight:700;text-transform:uppercase;margin-bottom:12px}}
  .page-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px}}
  .page-card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:18px;display:flex;flex-direction:column;gap:10px;min-height:140px}}
  .page-card h3{{margin:0;font-size:16px;color:#1a3a5c}}
  .page-card p{{margin:0;color:#5a6e82;font-size:13px}}
  .refresh-row{{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:16px}}
  .btn{{display:inline-flex;align-items:center;gap:8px;background:#0072ce;color:#fff;padding:10px 14px;border-radius:9px;text-decoration:none;font-weight:600}}
  .btn:hover{{background:#005aa5}}
  footer{{text-align:center;color:#94a3b8;margin-top:30px;padding:18px;font-size:12px}}
</style>
</head>
<body>
<header>
  <div class='logo'>🏦</div>
  <div>
    <h1 style='font-size:1.1rem;margin-bottom:4px'>Robin Khatwani Projects</h1>
    <div style='font-size:13px;color:rgba(255,255,255,.9)'>Internal Project Dashboard &middot; Payments Division</div>
  </div>
</header>
<main>
  <div class='refresh-row'>
    <div class='sect-title'>Available Pages</div>
    <a class='btn' style='background:#fff;color:#1a3a5c;border:1px solid #e2e8f0'
       href='/' onclick="event.preventDefault();window.location.href='/?_='+Date.now()">&#x21bb; Refresh</a>
  </div>
  <div class='page-grid'>
    <div class='page-card'>
      <h3>Live Tracker</h3>
      <p>BIN procurement status tracker — reads live data from <strong>{EXCEL_FILENAME}</strong> on every load.</p>
      <div style='margin-top:auto'><a class='btn' href='/Project_StatusTracker.html'>&#x21BA; Open Tracker</a></div>
    </div>
    <div class='page-card'>
      <h3>Site Index</h3>
      <p>Project documentation and product requirements — design notes and specifications.</p>
      <div style='margin-top:auto'><a class='btn' href='/index.html'>Open Site Index</a></div>
    </div>
    <div class='page-card'>
      <h3>Week&#8209;1 Learning Summary</h3>
      <p>Weekly learnings and notes from Week 1 — useful for retrospectives and onboarding.</p>
      <div style='margin-top:auto'><a class='btn' href='/Week-1/Week1_Learning_Summary.html'>Open Week&#8209;1 Summary</a></div>
    </div>
  </div>
</main>
<footer>Robin Khatwani Projects &middot; Last loaded: {now}</footer>
</body>
</html>"""


# ── HTTP handler ───────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split('?')[0]

        # Landing page
        if path in ('/', ''):
            body = render_landing(datetime.now().strftime('%d %b %Y, %H:%M')).encode('utf-8')
            self._send_html(body)
            return

        # Favicon
        if path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return

        # Live tracker
        if path == '/bin-tracker':
            try:
                objective, steps = read_project_data()
                summary = compute_summary(steps)
                html = render_tracker(objective, steps, summary)
                body = html.encode('utf-8')
                # Also save to file so Project_StatusTracker.html stays fresh
                try:
                    out = os.path.join(BASE_DIR, TRACKER_FILENAME)
                    with open(out, 'w', encoding='utf-8') as f:
                        f.write(html)
                except Exception:
                    pass
                self._send_html(body)
            except Exception as e:
                err = f'<h2 style="font-family:sans-serif;padding:40px;color:red">Error: {e}</h2>'.encode()
                self.send_response(500)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(err)))
                self.end_headers()
                self.wfile.write(err)
            return

        # Static files
        fs_path = os.path.join(BASE_DIR, path.lstrip('/'))
        if os.path.isdir(fs_path):
            fs_path = os.path.join(fs_path, 'index.html')
        if os.path.isfile(fs_path):
            try:
                with open(fs_path, 'rb') as f:
                    data = f.read()
                self.send_response(200)
                ct = 'text/html; charset=utf-8' if fs_path.endswith('.html') else 'application/octet-stream'
                self.send_header('Content-Type', ct)
                if fs_path.endswith('.html'):
                    self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                    self.send_header('Pragma', 'no-cache')
                    self.send_header('Expires', '0')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f'Error: {e}'.encode())
            return

        # 404
        body = "<h2 style='font-family:sans-serif;padding:40px'>404 — Page not found</h2>".encode()
        self.send_response(404)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, body):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}]  {fmt % args}")


if __name__ == '__main__':
    server = HTTPServer(('localhost', PORT), Handler)
    print(f"Server running at http://localhost:{PORT}")
    print(f"Tracker:  http://localhost:{PORT}/bin-tracker")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[Stopped] Server shut down.')
