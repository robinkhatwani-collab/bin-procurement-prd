#!/usr/bin/env python3
"""
AI PM Tool — Local Server
Serves default.html as the landing page on http://localhost:8080
Handles POST /upload-project to generate PRD and Status Tracker from Excel
"""
import http.server
import socketserver
import os
import json
import re
import cgi
import shutil
from datetime import datetime
from pathlib import Path

PORT = 8080
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
PROJECTS_DIR = BASE_DIR / "projects"

# ── helpers ───────────────────────────────────────────────────────────────────

def slugify(text):
    text = str(text).lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text[:60]

def short_title(objective):
    """Extract a clean short title from a full objective string."""
    cleaned = objective.strip()
    # Strip "Project Objective : -" and similar prefixes
    cleaned = re.sub(r'^project\s+objective\s*[:–\-]+\s*', '', cleaned, flags=re.IGNORECASE).strip()
    # Strip "Project Name :- " prefix
    cleaned = re.sub(r'^project\s+name\s*[:–\-]+\s*', '', cleaned, flags=re.IGNORECASE).strip()
    # Strip "To Track/Monitor/Manage progress of "
    cleaned = re.sub(r'^to\s+(track|monitor|manage|oversee|record)\s+(progress\s+of\s+|status\s+of\s+)?', '', cleaned, flags=re.IGNORECASE).strip()
    # Strip remaining leading "of "
    cleaned = re.sub(r'^of\s+', '', cleaned, flags=re.IGNORECASE).strip()
    # Remove trailing punctuation
    cleaned = cleaned.rstrip('.')
    # Capitalise words (preserve short words like "for", "and", "of" in lower unless first)
    words = cleaned.split()
    title = ' '.join(
        w.capitalize() if (i == 0 or w.lower() not in ('for','and','of','to','in','the','a','an','with','by'))
        else w.lower()
        for i, w in enumerate(words)
    )
    if len(title) > 70:
        title = title[:67] + '...'
    return title if title else objective[:70]

def fmt_date(val):
    if val is None:
        return '—'
    if isinstance(val, datetime):
        return val.strftime('%b %d, %Y')
    return str(val)

def status_class(status):
    s = str(status or '').lower().strip()
    if s == 'done':       return 'status-done'
    if s == 'in progress':return 'status-inprogress'
    return 'status-todo'

def status_label(status):
    s = str(status or '').strip()
    if s.lower() == 'done':       return '✅ Done'
    if s.lower() == 'in progress':return '🔄 In Progress'
    return '⏳ To Do'

def parse_excel(filepath):
    import openpyxl
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Excel file is empty")

    # ── Scan metadata rows and locate the header row ──────────────────────
    # Format: early rows are label/value pairs (col A = label, col B = value)
    # The actual step-data header row is identified by col A = "Steps" (or "Step")
    meta       = {}   # lowercase label → value
    header_idx = None

    for i, row in enumerate(rows):
        if not any(cell is not None for cell in row):
            continue
        col_a = str(row[0] or '').strip().lower().rstrip()
        col_b = str(row[1] or '').strip() if row[1] is not None else ''

        # Detect header row (contains column names for step data)
        if col_a in ('steps', 'step', '#', 'no', 'no.'):
            header_idx = i
            break

        # Collect metadata key/value pairs
        if col_a and col_b:
            meta[col_a] = col_b

    if header_idx is None:
        # Fallback: treat row 1 as metadata, row 2 as headers
        header_idx = 1

    # ── Extract project name and objective from metadata ──────────────────
    project_name = (
        meta.get('project name', '') or
        meta.get('project name ', '') or
        meta.get('name', '')
    )
    objective_text = (
        meta.get('project objective', '') or
        meta.get('project objective ', '') or
        meta.get('objective', '') or
        project_name
    )
    if not project_name and not objective_text:
        raise ValueError("Could not find project name or objective in the spreadsheet.")

    title = project_name if project_name else short_title(objective_text)
    slug  = slugify(title)
    # Use objective_text for display; fall back to project name
    display_objective = objective_text if objective_text else project_name

    # ── Parse step rows (rows after the header row) ───────────────────────
    steps       = []
    unique_dris = {}   # name → email

    for row in rows[header_idx + 1:]:
        if not any(cell is not None for cell in row):
            continue
        step_num    = row[0]
        desc        = str(row[1] or '').strip()
        responsible = str(row[2] or '').strip()
        notes       = str(row[3] or '').strip()
        dri         = str(row[4] or '').strip()
        dri_email   = str(row[5] or '').strip()
        dependency  = str(row[6] or '').strip()
        cur_status  = str(row[7] or 'ToDo').strip()
        est_date    = fmt_date(row[8])
        comp_date   = fmt_date(row[9])

        if not desc:
            continue
        # Skip any stray header-lookalike rows
        if desc.lower() in ('description', 'milestone', 'task'):
            continue

        if dri and dri.lower() not in ('dri', 'n/a', 'na', ''):
            unique_dris[dri] = dri_email

        steps.append({
            'num':         step_num,
            'desc':        desc,
            'responsible': responsible,
            'notes':       notes,
            'dri':         dri,
            'dri_email':   dri_email,
            'dependency':  dependency,
            'status':      cur_status,
            'est_date':    est_date,
            'comp_date':   comp_date,
        })

    if not steps:
        raise ValueError("No step data found in spreadsheet.")

    done_count = sum(1 for s in steps if s['status'].lower() == 'done')
    progress   = round((done_count / len(steps)) * 100) if steps else 0

    return {
        'objective':  display_objective,
        'title':      title,
        'slug':       slug,
        'steps':      steps,
        'dris':       [{'name': k, 'email': v} for k, v in unique_dris.items()],
        'done':       done_count,
        'total':      len(steps),
        'progress':   progress,
        'start_date': steps[0]['est_date']  if steps else '—',
        'end_date':   steps[-1]['est_date'] if steps else '—',
    }

# ── project intelligence ─────────────────────────────────────────────────────

def _detect_phases(steps, domain):
    """Group steps into intelligent phases based on content analysis."""
    if domain == 'payment_card':
        phase_defs = [
            ('🚀 Initiation & SOW',
             ['request', 'creation', 'assignment', 'sow', 'plan']),
            ('🔑 BIN & Cryptographic Setup',
             ['bin order', 'bin avail', 'key', 'encrypt', 'authori']),
            ('🌐 Network & Settlement',
             ['settlement', 'token', 'mdes', 'block', 'go live', 'non liability', 'file encrypt']),
            ('💳 Card Production & Go-Live',
             ['card', 'fulfillment', 'shipping', 'activat', 'validat', 'verif', 'close', 'account setup']),
        ]
    else:
        n = max(1, len(steps) // 3)
        return [
            ('📋 Phase 1 — Initiation',  steps[:n]),
            ('⚙️  Phase 2 — Execution',   steps[n:n*2]),
            ('✅ Phase 3 — Completion',   steps[n*2:]),
        ]

    assigned = set()
    phases   = []
    for phase_name, keywords in phase_defs:
        phase_steps = []
        for i, s in enumerate(steps):
            if i not in assigned:
                dl = s['desc'].lower()
                if any(kw in dl for kw in keywords):
                    phase_steps.append(s)
                    assigned.add(i)
        if phase_steps:
            phases.append((phase_name, phase_steps))

    # Any unclassified steps go to the last phase
    unassigned = [s for i, s in enumerate(steps) if i not in assigned]
    if unassigned:
        if phases:
            phases[-1] = (phases[-1][0], phases[-1][1] + unassigned)
        else:
            phases.append(('📋 All Steps', unassigned))
    return phases


def analyze_project(data):
    """
    Derive domain context, intelligent phases, and stakeholder breakdowns
    from the parsed Excel data — no external AI API required.
    """
    all_text = (data['objective'] + ' ' +
                ' '.join(s['desc'] for s in data['steps'])).lower()

    # ── domain detection ──────────────────────────────────────────────────
    if any(kw in all_text for kw in
           ['bin', 'card', 'issuer', 'processor', 'embosser', 'mdes', 'token bin',
            'settlement', 'card key', 'card launch']):
        domain = 'payment_card'
        domain_badge   = '💳 Payment Card Network Certification'
        domain_context = (
            'A <strong>Bank Identification Number (BIN)</strong> — also known as an Issuer '
            'Identification Number (IIN) — is the first 6–8 digits of a payment card. It '
            'identifies the card network, issuing bank, card type, and country of issue. '
            'Before a new card product can be launched, the issuer must obtain a unique BIN '
            'from the payment network and complete a structured certification programme involving '
            'four key parties: the <strong>Issuer</strong> (the bank), the <strong>Network</strong> '
            '(Mastercard / Visa), the <strong>Processor</strong> (transaction handler), and the '
            '<strong>Embosser</strong> (card manufacturer).'
        )
        business_problem = (
            'The organisation is launching a new payment card product and requires a dedicated '
            'Bank Identification Number (BIN) to be procured, registered, and technically certified '
            'across all four parties in the payment ecosystem. Without a certified BIN, cards cannot '
            'be issued or transacted on the network — blocking the entire card launch programme.'
        )
        business_value = (
            'Successful BIN procurement enables the organisation to issue cards under its own identity '
            'on the payment network, unlocking new revenue streams, strengthening brand presence, '
            'and delivering a differentiated card product to customers by the target launch date.'
        )
        moscow = {
            'must': [
                'BIN registration and allocation from the payment network',
                'Card key generation and exchange between all parties',
                'Settlement end-point configuration and approval',
                'Account BIN go-live and block removal',
                'Card personalisation, shipping, and activation',
                'UAT — card transaction and settlement validation',
            ],
            'should': [
                'MDES (Mastercard Digital Enablement Service) project enablement',
                'Token BIN assignment and activation',
                'Non-liability letter submission to network',
                'File encryption key exchange',
            ],
            'could': [
                'Accelerated timeline via parallel workstreams where dependencies allow',
                'Automated status notifications to DRIs on milestone completion',
                'Smartsheet direct sync for real-time tracker updates',
            ],
            'wont': [
                'Digital-only (virtual) card launch in this programme — physical card required',
                'Multi-BIN launch in a single programme cycle',
            ],
        }
        risks = [
            ('HIGH',   'Network Delays',         'Payment network SLA for BIN allocation can take 4–8 weeks. Late request to network cascades to all downstream milestones.',            'Submit network request immediately; escalate PM assignment if delayed beyond Step 2 target.'),
            ('HIGH',   'Key Exchange Failure',   'Cryptographic key exchange failures require full re-generation and re-certification — adding 2–3 weeks.',                             'Validate key formats before exchange; conduct dry-run in test environment first.'),
            ('MEDIUM', 'SOW / Plan Approval',    'Delays in SOW or Plan Approval by the Issuer can stall the entire programme as downstream steps have hard dependencies.',             'Engage approvers 1 week in advance; pre-circulate documents for informal review.'),
            ('MEDIUM', 'Embosser Lead Time',     'Card personalisation and fulfillment (Steps 25–27) require 3–4 weeks lead time. Late ordering risks missing launch date.',           'Confirm card ordering by mid-September to preserve Oct 10 target.'),
            ('LOW',    'DRI Turnover',            'If a DRI leaves mid-project, knowledge transfer gaps can delay milestone completion.',                                               'Maintain an updated RACI; cross-train deputies for each DRI role.'),
        ]
    else:
        domain = 'generic'
        domain_badge   = '📋 Project Programme'
        domain_context = ''
        business_problem = data['objective']
        business_value   = 'Successful completion delivers the stated project outcomes on schedule.'
        moscow = {
            'must':   ['Complete all milestones by target date', 'All DRI sign-offs received'],
            'should': ['Zero schedule slippage on critical path'],
            'could':  ['Early completion of non-critical milestones'],
            'wont':   ['Scope expansion in this programme cycle'],
        }
        risks = [
            ('MEDIUM', 'Schedule Slippage', 'Milestones delayed beyond estimated date.', 'Monitor weekly; escalate if >1 week overdue.'),
            ('LOW',    'DRI Changes',       'DRI turnover mid-project.',                 'Maintain RACI and cross-train deputies.'),
        ]

    phases = _detect_phases(data['steps'], domain)

    # ── per-responsible-party breakdown ───────────────────────────────────
    resp_map = {}
    for s in data['steps']:
        for r in re.split(r'\s+and\s+', s['responsible'], flags=re.IGNORECASE):
            r = r.strip()
            if not r or r.lower() in ('responsible',):
                continue
            if r not in resp_map:
                resp_map[r] = {'total': 0, 'done': 0, 'ip': 0, 'todo': 0}
            resp_map[r]['total'] += 1
            st = s['status'].lower()
            if st == 'done':
                resp_map[r]['done'] += 1
            elif st == 'in progress':
                resp_map[r]['ip'] += 1
            else:
                resp_map[r]['todo'] += 1

    return {
        'domain':           domain,
        'domain_badge':     domain_badge,
        'domain_context':   domain_context,
        'business_problem': business_problem,
        'business_value':   business_value,
        'phases':           phases,
        'moscow':           moscow,
        'risks':            risks,
        'resp_map':         resp_map,
    }


def svg_donut(done, ip, todo, total, cx=50, cy=50, r=38, sw=18, pct_label='', sub_label='done'):
    """Generate an SVG donut chart with done / in-progress / todo segments."""
    if total == 0:
        return f'<svg viewBox="0 0 100 100"><circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="rgba(255,255,255,.08)" stroke-width="{sw}"/></svg>'
    circ = 2 * 3.14159 * r
    def arc(count):
        return round((count / total) * circ, 2)
    done_arc = arc(done)
    ip_arc   = arc(ip)
    todo_arc = arc(todo)
    off_done = 0
    off_ip   = -done_arc
    off_todo = -(done_arc + ip_arc)

    segs = ''
    if done > 0:
        segs += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#34d399" stroke-width="{sw}" stroke-dasharray="{done_arc} 9999" stroke-dashoffset="{off_done}" transform="rotate(-90 {cx} {cy})"/>'
    if ip > 0:
        segs += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#4f8ef7" stroke-width="{sw}" stroke-dasharray="{ip_arc} 9999" stroke-dashoffset="{off_ip}" transform="rotate(-90 {cx} {cy})"/>'
    if todo > 0:
        segs += f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="rgba(255,255,255,.1)" stroke-width="{sw}" stroke-dasharray="{todo_arc} 9999" stroke-dashoffset="{off_todo}" transform="rotate(-90 {cx} {cy})"/>'

    label_html = f'<text x="{cx}" y="{cy - 4}" text-anchor="middle" fill="#f0f4ff" font-size="16" font-weight="800" font-family="Inter,sans-serif">{pct_label}</text><text x="{cx}" y="{cy + 14}" text-anchor="middle" fill="#8b9ab4" font-size="9" font-family="Inter,sans-serif">{sub_label}</text>'

    return f'<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">{segs}{label_html}</svg>'


# ── HTML generators ───────────────────────────────────────────────────────────

CSS_VARS = """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #0b0f1a; --surface: #111827; --surface2: #161d2e; --surface3: #1c2540;
      --border: rgba(255,255,255,0.08); --border2: rgba(255,255,255,0.13);
      --text: #f0f4ff; --text-muted: #8b9ab4; --text-dim: #5a6a84;
      --primary: #4f8ef7; --primary-dim: rgba(79,142,247,0.15);
      --secondary: #2dd4bf; --secondary-dim: rgba(45,212,191,0.15);
      --purple: #9f6ef5; --purple-dim: rgba(159,110,245,0.15);
      --accent: #f59e0b; --accent-dim: rgba(245,158,11,0.15);
      --green: #34d399; --green-dim: rgba(52,211,153,0.15);
      --red: #f87171; --red-dim: rgba(248,113,113,0.15);
      --radius: 14px; --shadow: 0 4px 24px rgba(0,0,0,0.35);
    }
    html, body { min-height: 100vh; font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); line-height: 1.7; }
    body::before {
      content: ''; position: fixed; inset: 0;
      background:
        radial-gradient(ellipse 70% 50% at 15% 15%, rgba(79,142,247,.09) 0%, transparent 60%),
        radial-gradient(ellipse 60% 45% at 85% 75%, rgba(159,110,245,.09) 0%, transparent 60%);
      pointer-events: none; z-index: 0;
    }
    .page { position: relative; z-index: 1; min-height: 100vh; display: flex; flex-direction: column; }
    nav {
      position: sticky; top: 0; z-index: 20;
      display: flex; align-items: center; justify-content: space-between;
      padding: 16px 48px; background: rgba(11,15,26,.85);
      backdrop-filter: blur(14px); border-bottom: 1px solid var(--border);
    }
    .nav-logo { display: flex; align-items: center; gap: 10px; text-decoration: none; color: var(--text); }
    .nav-logo-icon { width: 32px; height: 32px; background: linear-gradient(135deg, var(--primary), var(--purple)); border-radius: 8px; display: grid; place-items: center; font-size: 15px; }
    .nav-logo-text { font-size: 15px; font-weight: 700; }
    .nav-logo-text span { color: var(--primary); }
    .back-btn { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; color: var(--text-muted); text-decoration: none; background: rgba(255,255,255,.04); border: 1px solid var(--border); padding: 7px 14px; border-radius: 9px; transition: all .2s; }
    .back-btn:hover { color: var(--text); background: rgba(255,255,255,.07); }
    main { position: relative; z-index: 1; max-width: 1100px; margin: 0 auto; padding: 48px 32px 80px; width: 100%; }
    .card { background: var(--surface); border-radius: var(--radius); border: 1px solid var(--border); padding: 26px; box-shadow: var(--shadow); margin-bottom: 20px; }
    .card h3 { font-size: 1.05rem; font-weight: 700; margin-bottom: 10px; }
    .card p { color: var(--text-muted); font-size: 0.93rem; }
    .grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 18px; }
    .grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 18px; }
    .grid-4 { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; }
    .callout { border-radius: var(--radius); padding: 18px 22px; margin-bottom: 18px; border-left: 4px solid; }
    .callout-blue   { background: rgba(37,99,235,.1);  border-color: var(--primary); }
    .callout-green  { background: rgba(5,150,105,.1);  border-color: var(--green); }
    .callout-amber  { background: rgba(217,119,6,.1);  border-color: var(--accent); }
    .callout-purple { background: rgba(124,58,237,.1); border-color: var(--purple); }
    .callout h4 { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; opacity: .6; font-weight: 700; }
    .callout p { font-size: 0.91rem; color: var(--text-muted); }
    .callout strong { color: var(--text); }
    .tag { border-radius: 999px; padding: 3px 12px; font-size: 0.78rem; font-weight: 600; }
    .tag-blue   { background: var(--primary-dim); color: #93c5fd; }
    .tag-green  { background: var(--green-dim);   color: #6ee7b7; }
    .tag-amber  { background: var(--accent-dim);  color: #fcd34d; }
    .tag-purple { background: var(--purple-dim);  color: #c4b5fd; }
    .tag-red    { background: var(--red-dim);      color: #fca5a5; }
    footer { margin-top: auto; text-align: center; padding: 24px; font-size: 12px; color: var(--text-muted); border-top: 1px solid var(--border); }
"""

def generate_prd(data, project_url_prefix):
    steps        = data['steps']
    dri_set      = data['dris']
    in_progress  = [s for s in steps if s['status'].lower() == 'in progress']
    done_steps   = [s for s in steps if s['status'].lower() == 'done']
    todo_steps   = [s for s in steps if s['status'].lower() not in ('done','in progress')]
    generated_on = datetime.now().strftime('%B %d, %Y at %H:%M')

    intel = analyze_project(data)
    phases        = intel['phases']
    moscow        = intel['moscow']
    risks         = intel['risks']
    resp_map      = intel['resp_map']

    # ── DRI cards ─────────────────────────────────────────────────────────
    COLOURS = ['var(--primary)','var(--purple)','var(--secondary)','var(--accent)','var(--rose, #f472b6)','var(--green)']
    dri_cards = ''
    for i, dri in enumerate(dri_set[:6]):
        col = COLOURS[i % len(COLOURS)]
        initials = ''.join(w[0].upper() for w in dri['name'].split()[:2]) or '?'
        dri_cards += f"""
        <div class="card" style="border-top:3px solid {col};text-align:center;padding:22px 18px;">
          <div style="width:48px;height:48px;border-radius:50%;background:linear-gradient(135deg,{col},rgba(255,255,255,.1));display:grid;place-items:center;margin:0 auto 12px;font-size:1rem;font-weight:800;">{initials}</div>
          <div style="font-size:.93rem;font-weight:700;margin-bottom:4px;">{dri['name']}</div>
          <a href="mailto:{dri['email']}" style="font-size:.75rem;color:var(--primary);text-decoration:none;">{dri['email']}</a>
        </div>"""

    # ── responsible-party ecosystem cards ─────────────────────────────────
    PARTY_META = {
        'Issuer':      ('🏦', 'var(--primary)',    'The card-issuing bank. Owns the customer relationship, submits the BIN request, and approves all SOW and plans.'),
        'Network':     ('🌐', 'var(--purple)',     'The payment network (e.g., Mastercard / Visa). Allocates the BIN, manages certification, and governs settlement endpoints.'),
        'Processor':   ('⚙️',  'var(--secondary)', 'The transaction processing partner. Generates card cryptographic keys and updates internal systems for the new BIN.'),
        'Embosser':    ('💳', 'var(--accent)',     'The card manufacturer. Responsible for personalising, producing, and shipping physical cards to the issuer.'),
    }
    party_cards = ''
    for party, info in resp_map.items():
        meta  = PARTY_META.get(party, ('🏢', 'var(--text-muted)', f'Responsible for {info["total"]} steps in this programme.'))
        icon, col, desc = meta
        pct   = round((info['done'] / info['total']) * 100) if info['total'] else 0
        party_cards += f"""
        <div class="card" style="border-left:4px solid {col};">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
            <span style="font-size:1.4rem;">{icon}</span>
            <div>
              <div style="font-size:.95rem;font-weight:700;">{party}</div>
              <div style="font-size:.72rem;color:var(--text-dim);text-transform:uppercase;letter-spacing:.8px;">{info['total']} Steps · {pct}% Done</div>
            </div>
          </div>
          <p style="font-size:.82rem;color:var(--text-muted);line-height:1.6;">{desc}</p>
        </div>"""

    # ── phase sections ────────────────────────────────────────────────────
    phase_sections = ''
    PHASE_COLS = ['var(--primary)','var(--purple)','var(--secondary)','var(--accent)']
    for pi, (phase_name, phase_steps) in enumerate(phases):
        if not phase_steps:
            continue
        col   = PHASE_COLS[pi % len(PHASE_COLS)]
        items = ''.join(
            f'<li style="margin-bottom:8px;display:flex;align-items:flex-start;gap:8px;">'
            f'<span class="status-badge {status_class(s["status"])}" style="margin-top:1px;flex-shrink:0;">{status_label(s["status"])}</span>'
            f'<span style="font-size:.86rem;color:var(--text);"><strong>{s["desc"]}</strong>'
            f' <span style="color:var(--text-dim);font-size:.78rem;">— {s["responsible"]}</span>'
            f'<span style="color:var(--text-dim);font-size:.75rem;margin-left:6px;">📅 {s["est_date"]}</span>'
            f'</span></li>'
            for s in phase_steps
        )
        p_done = sum(1 for s in phase_steps if s['status'].lower() == 'done')
        p_pct  = round((p_done / len(phase_steps)) * 100) if phase_steps else 0
        phase_sections += f"""
        <div class="card" style="margin-bottom:20px;border-top:3px solid {col};">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
            <h3 style="font-size:1rem;">{phase_name}</h3>
            <span style="font-size:.78rem;font-weight:700;color:{col};">{len(phase_steps)} steps · {p_pct}% done</span>
          </div>
          <div class="progress-track" style="margin-bottom:14px;"><div class="progress-fill" style="width:{p_pct}%;background:{col};box-shadow:none;"></div></div>
          <ul style="list-style:none;padding:0;">{items}</ul>
        </div>"""

    # ── milestone table rows ───────────────────────────────────────────────
    milestone_rows = ''
    for s in steps:
        sc = status_class(s['status'])
        sl = status_label(s['status'])
        milestone_rows += f"""
          <tr>
            <td style="color:var(--text-dim);font-size:.82rem;font-weight:700;">{s['num']}</td>
            <td style="font-weight:600;font-size:.86rem;">{s['desc']}</td>
            <td style="font-size:.83rem;color:var(--text-muted);">{s['responsible']}</td>
            <td style="font-size:.83rem;color:var(--text-muted);">{s['dri']}</td>
            <td><span class="status-badge {sc}">{sl}</span></td>
            <td style="font-size:.8rem;color:var(--text-dim);">{s['est_date']}</td>
          </tr>"""

    # ── MoSCoW ────────────────────────────────────────────────────────────
    def moscow_list(items):
        return ''.join(f'<li>{it}</li>' for it in items)

    moscow_html = f"""
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;">
      <div class="inner-card inner-green"><strong>🟢 Must Have</strong><ul style="margin-top:8px;padding-left:16px;font-size:.83rem;color:var(--text-muted);line-height:1.8;">{moscow_list(moscow['must'])}</ul></div>
      <div class="inner-card inner-blue"><strong>🔵 Should Have</strong><ul style="margin-top:8px;padding-left:16px;font-size:.83rem;color:var(--text-muted);line-height:1.8;">{moscow_list(moscow['should'])}</ul></div>
      <div class="inner-card inner-amber"><strong>🟡 Could Have</strong><ul style="margin-top:8px;padding-left:16px;font-size:.83rem;color:var(--text-muted);line-height:1.8;">{moscow_list(moscow['could'])}</ul></div>
      <div class="inner-card" style="background:rgba(255,255,255,.03);border:1px solid var(--border);"><strong style="color:var(--text-muted);">⚫ Won't Have (Now)</strong><ul style="margin-top:8px;padding-left:16px;font-size:.83rem;color:var(--text-dim);line-height:1.8;">{moscow_list(moscow['wont'])}</ul></div>
    </div>"""

    # ── risk register ─────────────────────────────────────────────────────
    RISK_STYLE = {'HIGH': ('var(--red)', 'var(--red-dim)'), 'MEDIUM': ('var(--accent)', 'var(--accent-dim)'), 'LOW': ('var(--green)', 'var(--green-dim)')}
    risk_rows = ''
    for level, name, desc, mit in risks:
        col, bg = RISK_STYLE.get(level, ('var(--text-muted)', 'rgba(255,255,255,.04)'))
        risk_rows += f"""
          <tr>
            <td><span style="background:{bg};color:{col};border-radius:999px;padding:2px 10px;font-size:.72rem;font-weight:700;">{level}</span></td>
            <td style="font-weight:600;font-size:.86rem;">{name}</td>
            <td style="font-size:.83rem;color:var(--text-muted);">{desc}</td>
            <td style="font-size:.83rem;color:var(--text-muted);">{mit}</td>
          </tr>"""

    prog_pct = data['progress']

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>PRD — {data['title']}</title>
  <style>
{CSS_VARS}
    .hero {{ background: linear-gradient(135deg, #0d1b3e 0%, #1a0f4a 50%, #0a2a3a 100%); border-bottom: 1px solid var(--border); padding: 56px 40px 48px; text-align: center; position: relative; overflow: hidden; }}
    .hero::before {{ content:''; position:absolute; inset:0; background: radial-gradient(ellipse 80% 60% at 50% 0%, rgba(79,142,247,.18) 0%, transparent 70%); pointer-events:none; }}
    .hero .badge {{ position:relative; display:inline-block; background:rgba(79,142,247,.15); border:1px solid rgba(79,142,247,.35); border-radius:999px; padding:5px 16px; font-size:.72rem; letter-spacing:1.5px; text-transform:uppercase; margin-bottom:16px; color:var(--primary); font-weight:700; }}
    .hero h1 {{ position:relative; font-size:clamp(1.7rem,3.5vw,2.5rem); font-weight:800; letter-spacing:-.5px; margin-bottom:10px; }}
    .hero .sub {{ position:relative; font-size:.95rem; color:var(--text-muted); max-width:640px; margin:0 auto 26px; line-height:1.6; }}
    .hero-stats {{ position:relative; display:inline-flex; align-items:center; gap:22px; background:rgba(255,255,255,.06); border:1px solid var(--border2); border-radius:14px; padding:12px 26px; flex-wrap:wrap; justify-content:center; }}
    .stat {{ text-align:center; }}
    .stat .val {{ font-size:1.5rem; font-weight:800; }}
    .stat .lbl {{ font-size:.68rem; color:var(--text-muted); font-weight:500; text-transform:uppercase; letter-spacing:.5px; }}
    .stat-div {{ width:1px; height:30px; background:var(--border2); }}
    .section-head {{ display:flex; align-items:center; gap:14px; margin:48px 0 22px; }}
    .section-head h2 {{ font-size:1.25rem; font-weight:700; }}
    .section-num {{ font-size:.7rem; color:var(--text-dim); text-transform:uppercase; letter-spacing:1.2px; display:block; margin-bottom:2px; }}
    .section-icon {{ width:42px; height:42px; border-radius:12px; background:var(--surface2); border:1px solid var(--border); display:grid; place-items:center; font-size:1.1rem; flex-shrink:0; }}
    .milestone-table {{ width:100%; border-collapse:collapse; font-size:.86rem; border-radius:var(--radius); overflow:hidden; }}
    .milestone-table th {{ padding:12px 14px; text-align:left; font-size:.72rem; text-transform:uppercase; letter-spacing:.8px; background:var(--surface2); color:var(--text-dim); border-bottom:1px solid var(--border2); white-space:nowrap; }}
    .milestone-table td {{ padding:11px 14px; border-top:1px solid var(--border); background:var(--surface); vertical-align:middle; }}
    .milestone-table tr:hover td {{ background:var(--surface2); }}
    .status-badge {{ display:inline-block; font-size:.72rem; font-weight:600; padding:3px 10px; border-radius:999px; white-space:nowrap; }}
    .status-done       {{ background:var(--green-dim);  color:var(--green); }}
    .status-inprogress {{ background:var(--primary-dim);color:var(--primary); }}
    .status-todo       {{ background:rgba(255,255,255,.06); color:var(--text-muted); }}
    .progress-track {{ height:7px; background:rgba(255,255,255,.06); border-radius:99px; overflow:hidden; }}
    .progress-fill  {{ height:100%; background:linear-gradient(90deg,var(--primary),var(--secondary)); border-radius:99px; box-shadow:0 0 10px rgba(79,142,247,.35); }}
    .inner-card {{ border-radius:10px; padding:16px 18px; }}
    .inner-blue   {{ background:rgba(37,99,235,.1);   border:1px solid rgba(37,99,235,.22); }}
    .inner-green  {{ background:rgba(5,150,105,.1);   border:1px solid rgba(5,150,105,.22); }}
    .inner-amber  {{ background:rgba(217,119,6,.1);   border:1px solid rgba(217,119,6,.22); }}
    .inner-purple {{ background:rgba(124,58,237,.1);  border:1px solid rgba(124,58,237,.22); }}
    .inner-card strong {{ display:block; margin-bottom:7px; font-size:.88rem; }}
    .inner-blue   strong {{ color:#93c5fd; }}
    .inner-green  strong {{ color:#6ee7b7; }}
    .inner-amber  strong {{ color:#fcd34d; }}
    .inner-purple strong {{ color:#c4b5fd; }}
    .inner-card ul {{ padding-left:16px; font-size:.83rem; color:var(--text-muted); }}
    .inner-card li {{ margin-bottom:4px; }}
    .risk-table {{ width:100%; border-collapse:collapse; font-size:.86rem; }}
    .risk-table th {{ padding:10px 14px; text-align:left; font-size:.7rem; text-transform:uppercase; letter-spacing:.8px; background:var(--surface2); color:var(--text-dim); border-bottom:1px solid var(--border2); }}
    .risk-table td {{ padding:11px 14px; border-top:1px solid var(--border); background:var(--surface); vertical-align:top; }}
    .risk-table tr:hover td {{ background:var(--surface2); }}
  </style>
</head>
<body>
<div class="page">
  <nav>
    <a class="nav-logo" href="../../default.html">
      <div class="nav-logo-icon">🤖</div>
      <div class="nav-logo-text">AI <span>PM</span> Tool</div>
    </a>
    <a class="back-btn" href="../../projects.html">← All Projects</a>
  </nav>

  <header class="hero">
    <div class="badge">📄 Product Requirements Document</div>
    <h1>{data['title']}</h1>
    <p class="sub">{intel['domain_badge']}</p>
    <div class="hero-stats">
      <div class="stat"><div class="val">{data['total']}</div><div class="lbl">Steps</div></div>
      <div class="stat-div"></div>
      <div class="stat"><div class="val" style="color:var(--green);">{data['done']}</div><div class="lbl">Done</div></div>
      <div class="stat-div"></div>
      <div class="stat"><div class="val" style="color:var(--primary);">{len(in_progress)}</div><div class="lbl">In Progress</div></div>
      <div class="stat-div"></div>
      <div class="stat"><div class="val">{data['progress']}%</div><div class="lbl">Complete</div></div>
      <div class="stat-div"></div>
      <div class="stat"><div class="val">{len(dri_set)}</div><div class="lbl">DRIs</div></div>
      <div class="stat-div"></div>
      <div class="stat"><div class="val">{len(phases)}</div><div class="lbl">Phases</div></div>
    </div>
  </header>

  <main>

    <!-- SECTION 1 — BUSINESS CONTEXT -->
    <div class="section-head">
      <div class="section-icon">🧭</div>
      <div><span class="section-num">Section 1</span><h2>Business Context</h2></div>
    </div>
    <div class="callout callout-blue">
      <h4>What Is This Project?</h4>
      <p>{intel['domain_context']}</p>
    </div>
    <div class="grid-2">
      <div class="inner-card inner-purple">
        <strong>⚠️ The Problem</strong>
        <p style="font-size:.85rem;color:var(--text-muted);line-height:1.65;margin-top:2px;">{intel['business_problem']}</p>
      </div>
      <div class="inner-card inner-green">
        <strong>💡 Business Value</strong>
        <p style="font-size:.85rem;color:var(--text-muted);line-height:1.65;margin-top:2px;">{intel['business_value']}</p>
      </div>
    </div>

    <!-- SECTION 2 — OBJECTIVE & SCOPE -->
    <div class="section-head">
      <div class="section-icon">🎯</div>
      <div><span class="section-num">Section 2</span><h2>Objective &amp; Scope</h2></div>
    </div>
    <div class="callout callout-amber">
      <h4>Project Objective</h4>
      <p>{data['objective']}</p>
    </div>
    <div class="grid-3">
      <div class="inner-card inner-blue">
        <strong>📅 Timeline</strong>
        <p style="font-size:.85rem;color:var(--text-muted);margin-top:4px;">Start: <strong style="color:var(--text);">{data['start_date']}</strong><br/>Target: <strong style="color:var(--text);">{data['end_date']}</strong></p>
      </div>
      <div class="inner-card inner-green">
        <strong>📊 Scope</strong>
        <p style="font-size:.85rem;color:var(--text-muted);margin-top:4px;"><strong style="color:var(--text);">{data['total']}</strong> milestones across <strong style="color:var(--text);">{len(phases)}</strong> phases<br/><strong style="color:var(--text);">{len(resp_map)}</strong> responsible parties</p>
      </div>
      <div class="inner-card inner-amber">
        <strong>📈 Current Status</strong>
        <p style="font-size:.85rem;color:var(--text-muted);margin-top:4px;"><strong style="color:var(--green);">{data['done']} done</strong> · <strong style="color:var(--primary);">{len(in_progress)} active</strong><br/><strong style="color:var(--text-muted);">{len(todo_steps)}</strong> steps remaining</p>
      </div>
    </div>

    <!-- SECTION 3 — STAKEHOLDER ECOSYSTEM -->
    <div class="section-head">
      <div class="section-icon">👥</div>
      <div><span class="section-num">Section 3</span><h2>Stakeholder Ecosystem</h2></div>
    </div>
    <div class="callout callout-purple">
      <h4>Four-Party Payment Ecosystem</h4>
      <p>This programme spans four distinct parties, each with a defined role and accountability. Every milestone is assigned to one or more of these parties and owned by a named DRI.</p>
    </div>
    <div class="grid-2" style="margin-bottom:22px;">{party_cards}</div>
    <div class="section-head" style="margin-top:10px;margin-bottom:16px;">
      <div class="section-icon">🙋</div>
      <div><h2 style="font-size:1.05rem;">Directly Responsible Individuals (DRIs)</h2></div>
    </div>
    <div class="grid-3">{dri_cards}</div>

    <!-- SECTION 4 — PROJECT PHASES -->
    <div class="section-head">
      <div class="section-icon">🗺️</div>
      <div><span class="section-num">Section 4</span><h2>Project Phases &amp; Deliverables</h2></div>
    </div>
    {phase_sections}

    <!-- SECTION 5 — FULL MILESTONE TABLE -->
    <div class="section-head">
      <div class="section-icon">🗂️</div>
      <div><span class="section-num">Section 5</span><h2>Full Milestone Plan ({data['total']} Steps)</h2></div>
    </div>
    <div class="card" style="padding:0;overflow:hidden;">
      <table class="milestone-table">
        <thead><tr><th>#</th><th>Milestone</th><th>Responsible</th><th>DRI</th><th>Status</th><th>Est. Date</th></tr></thead>
        <tbody>{milestone_rows}</tbody>
      </table>
    </div>

    <!-- SECTION 6 — REQUIREMENTS (MOSCOW) -->
    <div class="section-head">
      <div class="section-icon">📐</div>
      <div><span class="section-num">Section 6</span><h2>Requirements — MoSCoW Prioritisation</h2></div>
    </div>
    {moscow_html}

    <!-- SECTION 7 — RISK REGISTER -->
    <div class="section-head">
      <div class="section-icon">⚠️</div>
      <div><span class="section-num">Section 7</span><h2>Risk Register</h2></div>
    </div>
    <div class="card" style="padding:0;overflow:hidden;">
      <table class="risk-table">
        <thead><tr><th>Level</th><th>Risk</th><th>Description</th><th>Mitigation</th></tr></thead>
        <tbody>{risk_rows}</tbody>
      </table>
    </div>

    <!-- SECTION 8 — SUCCESS METRICS & PROGRESS -->
    <div class="section-head">
      <div class="section-icon">📈</div>
      <div><span class="section-num">Section 8</span><h2>Success Metrics &amp; Current Progress</h2></div>
    </div>
    <div class="grid-2" style="margin-bottom:20px;">
      <div class="inner-card inner-green">
        <strong>✅ Primary — Completion &amp; Quality</strong>
        <ul style="margin-top:6px;"><li>100% of {data['total']} milestones marked Done before go-live</li><li>Zero outstanding blockers at card launch date</li><li>All DRI sign-offs and network certifications received</li><li>Successful card transaction &amp; settlement validation</li></ul>
      </div>
      <div class="inner-card inner-blue">
        <strong>🕐 Secondary — Schedule Adherence</strong>
        <ul style="margin-top:6px;"><li>Each milestone completed by its estimated date</li><li>No more than 10% overall schedule slippage</li><li>Critical path milestones (BIN allocation, Key Exchange) on time</li><li>Target card launch: <strong style="color:var(--text);">{data['end_date']}</strong></li></ul>
      </div>
    </div>
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
        <span style="font-size:.9rem;font-weight:700;">Overall Progress</span>
        <span style="font-size:1rem;font-weight:800;color:var(--primary);">{prog_pct}%</span>
      </div>
      <div class="progress-track"><div class="progress-fill" style="width:{prog_pct}%"></div></div>
      <div style="display:flex;gap:14px;margin-top:16px;flex-wrap:wrap;">
        <span class="tag tag-green">✅ Done: {data['done']}</span>
        <span class="tag tag-blue">🔄 In Progress: {len(in_progress)}</span>
        <span style="background:rgba(255,255,255,.06);color:var(--text-muted);border-radius:999px;padding:3px 12px;font-size:.78rem;font-weight:600;">⏳ To Do: {len(todo_steps)}</span>
      </div>
      <div class="callout callout-amber" style="margin-top:18px;margin-bottom:0;">
        <h4>Future Integration</h4>
        <p>Planned: <strong>Smartsheet direct sync</strong> to auto-refresh this PRD on save. Re-upload the Excel at any time to reflect the latest milestone statuses.</p>
      </div>
    </div>

  </main>
  <footer><p>📄 PRD — {data['title']} &nbsp;·&nbsp; Robin AI Learnings &nbsp;·&nbsp; AI PM Tool &nbsp;·&nbsp; {generated_on}</p></footer>
</div>
</body>
</html>"""

def generate_tracker(data, project_url_prefix):
    steps        = data['steps']
    in_progress  = [s for s in steps if s['status'].lower() == 'in progress']
    done_steps   = [s for s in steps if s['status'].lower() == 'done']
    todo_steps   = [s for s in steps if s['status'].lower() not in ('done','in progress')]
    generated_on = datetime.now().strftime('%B %d, %Y')
    generated_ts = datetime.now().strftime('%B %d, %Y at %H:%M')

    intel    = analyze_project(data)
    resp_map = intel['resp_map']

    total = data['total']
    done  = data['done']
    ip    = len(in_progress)
    todo  = len(todo_steps)
    pct   = data['progress']

    # ── overall donut ─────────────────────────────────────────────────────
    overall_donut = svg_donut(done, ip, todo, total, pct_label=f'{pct}%', sub_label='done')

    # ── stakeholder donuts ────────────────────────────────────────────────
    PARTY_COLOURS = {
        'Issuer':    ('#4f8ef7', 'rgba(79,142,247,.15)'),
        'Network':   ('#9f6ef5', 'rgba(159,110,245,.15)'),
        'Processor': ('#2dd4bf', 'rgba(45,212,191,.15)'),
        'Embosser':  ('#f59e0b', 'rgba(245,158,11,.15)'),
    }
    party_donut_cards = ''
    for party, info in resp_map.items():
        col, bg = PARTY_COLOURS.get(party, ('#8b9ab4', 'rgba(255,255,255,.04)'))
        p_pct  = round((info['done'] / info['total']) * 100) if info['total'] else 0
        donut  = svg_donut(info['done'], info['ip'], info['todo'], info['total'],
                           cx=50, cy=50, r=34, sw=14,
                           pct_label=f"{p_pct}%", sub_label='done')
        party_donut_cards += f"""
        <div class="card" style="border-top:3px solid {col};text-align:center;padding:20px 16px;">
          <div style="font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:{col};margin-bottom:12px;">{party}</div>
          <div style="width:90px;height:90px;margin:0 auto 12px;">{donut}</div>
          <div style="font-size:.76rem;color:var(--text-muted);line-height:1.8;">
            <span style="color:var(--green);">✅ {info['done']}</span> &nbsp;
            <span style="color:var(--primary);">🔄 {info['ip']}</span> &nbsp;
            <span style="color:var(--text-dim);">⏳ {info['todo']}</span>
          </div>
          <div style="font-size:.7rem;color:var(--text-dim);margin-top:4px;">{info['total']} total steps</div>
        </div>"""

    # ── health & executive summary ────────────────────────────────────────
    health_colour = 'var(--green)' if pct >= 50 else ('var(--accent)' if pct >= 20 else 'var(--primary)')
    health_label  = 'ON TRACK' if pct >= 20 or todo == total else 'STARTED'

    exec_summary = (
        f'The <strong>{data["title"]}</strong> programme is '
        f'<strong style="color:{health_colour};">{pct}% complete</strong> with '
        f'<strong>{done} of {total}</strong> steps finished. '
        f'<strong>{ip}</strong> step{"s are" if ip != 1 else " is"} actively in progress and '
        f'<strong>{todo}</strong> remain in the queue. '
        f'Target completion: <strong>{data["end_date"]}</strong>. '
        f'Overall health is rated <strong style="color:{health_colour};">{health_label}</strong>.'
    )

    # ── DRI pills ─────────────────────────────────────────────────────────
    COLOURS = ['var(--primary)','var(--purple)','var(--secondary)','var(--accent)','#f472b6','var(--green)']
    dri_pills = ''.join(
        f'<div class="dri-pill">'
        f'<div class="dri-avatar" style="background:linear-gradient(135deg,{COLOURS[i % len(COLOURS)]},rgba(255,255,255,.05));">'
        f'{d["name"][0].upper()}</div>'
        f'<div><div class="dri-name">{d["name"]}</div>'
        f'<a class="dri-email" href="mailto:{d["email"]}">{d["email"]}</a></div></div>'
        for i, d in enumerate(data['dris'][:8])
    )

    # ── step rows (table) ─────────────────────────────────────────────────
    step_rows = ''
    for s in steps:
        sc = status_class(s['status'])
        sl = status_label(s['status'])
        comp_td = s['comp_date'] if s['comp_date'] != '—' else '<span style="color:var(--text-dim);">—</span>'
        step_rows += f"""
          <tr class="{sc}-row">
            <td style="color:var(--text-dim);font-size:.82rem;font-weight:700;width:36px;">{s['num']}</td>
            <td style="font-weight:600;font-size:.86rem;">{s['desc']}</td>
            <td style="font-size:.82rem;color:var(--text-muted);">{s['responsible']}</td>
            <td style="font-size:.82rem;color:var(--text-muted);">{s['dri']}</td>
            <td><span class="status-badge {sc}">{sl}</span></td>
            <td style="font-size:.8rem;color:var(--text-dim);">{s['est_date']}</td>
            <td style="font-size:.8rem;color:var(--green);">{comp_td}</td>
          </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Status Tracker — {data['title']}</title>
  <style>
{CSS_VARS}
    .hero {{ background:linear-gradient(135deg,#071a12 0%,#0a1f2e 50%,#1a0f3a 100%); border-bottom:1px solid var(--border); padding:52px 40px 44px; text-align:center; position:relative; overflow:hidden; }}
    .hero::before {{ content:''; position:absolute; inset:0; background:radial-gradient(ellipse 80% 60% at 50% 0%,rgba(52,211,153,.15) 0%,transparent 70%); pointer-events:none; }}
    .hero .badge {{ position:relative; display:inline-block; background:rgba(52,211,153,.15); border:1px solid rgba(52,211,153,.35); border-radius:999px; padding:5px 16px; font-size:.72rem; letter-spacing:1.5px; text-transform:uppercase; margin-bottom:16px; color:var(--green); font-weight:700; }}
    .hero h1 {{ position:relative; font-size:clamp(1.8rem,3.5vw,2.5rem); font-weight:800; letter-spacing:-.5px; margin-bottom:10px; }}
    .hero p {{ position:relative; font-size:.95rem; color:var(--text-muted); max-width:620px; margin:0 auto 24px; }}
    .hero-kpi {{ position:relative; display:inline-flex; align-items:center; gap:20px; background:rgba(255,255,255,.06); border:1px solid var(--border2); border-radius:14px; padding:12px 24px; flex-wrap:wrap; justify-content:center; }}
    .kstat {{ text-align:center; }}
    .kstat .val {{ font-size:1.5rem; font-weight:800; }}
    .kstat .lbl {{ font-size:.68rem; color:var(--text-muted); font-weight:500; text-transform:uppercase; letter-spacing:.5px; }}
    .kstat-div {{ width:1px; height:28px; background:var(--border2); }}
    .section-head {{ display:flex; align-items:center; gap:12px; margin:40px 0 18px; }}
    .section-head h2 {{ font-size:1.2rem; font-weight:700; }}
    .section-icon {{ width:38px; height:38px; border-radius:10px; background:var(--surface2); border:1px solid var(--border); display:grid; place-items:center; font-size:1rem; flex-shrink:0; }}
    .overview-row {{ display:grid; grid-template-columns:160px 1fr; gap:18px; margin-bottom:20px; }}
    .donut-card {{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:18px; display:flex; flex-direction:column; align-items:center; justify-content:center; }}
    .donut-wrap {{ width:110px; height:110px; margin-bottom:12px; }}
    .donut-legend {{ display:flex; flex-wrap:wrap; gap:6px 14px; justify-content:center; }}
    .leg-item {{ display:flex; align-items:center; gap:5px; font-size:.75rem; color:var(--text-muted); }}
    .leg-dot {{ width:8px; height:8px; border-radius:50%; flex-shrink:0; }}
    .exec-card {{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:20px 24px; }}
    .exec-label {{ font-size:.7rem; font-weight:700; text-transform:uppercase; letter-spacing:1px; color:var(--text-dim); margin-bottom:10px; }}
    .exec-summary {{ font-size:.92rem; color:var(--text-muted); line-height:1.75; margin-bottom:16px; }}
    .timeline-row {{ display:flex; gap:24px; flex-wrap:wrap; margin-top:4px; }}
    .tl-item .tl-val {{ font-size:1.4rem; font-weight:800; }}
    .tl-item .tl-lbl {{ font-size:.7rem; color:var(--text-dim); font-weight:600; text-transform:uppercase; letter-spacing:.5px; margin-top:2px; }}
    .progress-track {{ height:8px; background:rgba(255,255,255,.06); border-radius:99px; overflow:hidden; margin:10px 0; }}
    .progress-fill  {{ height:100%; border-radius:99px; background:linear-gradient(90deg,var(--green),var(--secondary)); box-shadow:0 0 12px rgba(52,211,153,.35); }}
    .kpi-row {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:12px; margin-bottom:20px; }}
    .kpi-card {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:16px 12px; text-align:center; }}
    .kpi-val {{ font-size:1.8rem; font-weight:800; line-height:1; margin-bottom:4px; }}
    .kpi-lbl {{ font-size:.68rem; text-transform:uppercase; letter-spacing:.6px; color:var(--text-dim); font-weight:600; }}
    .party-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:14px; margin-bottom:24px; }}
    .dri-grid {{ display:flex; flex-wrap:wrap; gap:12px; margin-bottom:4px; }}
    .dri-pill {{ display:flex; align-items:center; gap:11px; background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:10px 14px; }}
    .dri-avatar {{ width:34px; height:34px; border-radius:50%; display:grid; place-items:center; font-size:.88rem; font-weight:700; flex-shrink:0; color:white; }}
    .dri-name {{ font-size:.86rem; font-weight:700; }}
    .dri-email {{ font-size:.74rem; color:var(--primary); text-decoration:none; }}
    .dri-email:hover {{ text-decoration:underline; }}
    .steps-table {{ width:100%; border-collapse:collapse; font-size:.86rem; }}
    .steps-table th {{ padding:11px 14px; text-align:left; font-size:.7rem; text-transform:uppercase; letter-spacing:.7px; background:var(--surface2); color:var(--text-dim); border-bottom:1px solid var(--border2); white-space:nowrap; }}
    .steps-table td {{ padding:10px 14px; border-top:1px solid var(--border); background:var(--surface); vertical-align:middle; }}
    .steps-table tr:hover td {{ background:var(--surface2); }}
    .status-badge {{ display:inline-block; font-size:.72rem; font-weight:600; padding:3px 10px; border-radius:999px; white-space:nowrap; }}
    .status-done       {{ background:var(--green-dim);  color:var(--green); }}
    .status-inprogress {{ background:var(--primary-dim);color:var(--primary); }}
    .status-todo       {{ background:rgba(255,255,255,.06); color:var(--text-muted); }}
    .filter-bar {{ display:flex; gap:8px; margin-bottom:16px; flex-wrap:wrap; }}
    .filter-btn {{ background:var(--surface2); border:1px solid var(--border); color:var(--text-muted); padding:6px 14px; border-radius:8px; font-size:.78rem; font-weight:600; cursor:pointer; transition:all .2s; }}
    .filter-btn:hover,.filter-btn.active {{ background:rgba(52,211,153,.12); border-color:rgba(52,211,153,.35); color:var(--green); }}
  </style>
</head>
<body>
<div class="page">
  <nav>
    <a class="nav-logo" href="../../default.html">
      <div class="nav-logo-icon">🤖</div>
      <div class="nav-logo-text">AI <span>PM</span> Tool</div>
    </a>
    <a class="back-btn" href="../../projects.html">← All Projects</a>
  </nav>

  <header class="hero">
    <div class="badge">📊 Live Status Tracker</div>
    <h1>{data['title']}</h1>
    <p>Payments Division · New Card Launch Programme</p>
    <div class="hero-kpi">
      <div class="kstat"><div class="val" style="color:var(--primary);">{pct}%</div><div class="lbl">Complete</div></div>
      <div class="kstat-div"></div>
      <div class="kstat"><div class="val" style="color:var(--green);">{done}</div><div class="lbl">Done</div></div>
      <div class="kstat-div"></div>
      <div class="kstat"><div class="val" style="color:var(--primary);">{ip}</div><div class="lbl">In Progress</div></div>
      <div class="kstat-div"></div>
      <div class="kstat"><div class="val" style="color:var(--text-muted);">{todo}</div><div class="lbl">To Do</div></div>
      <div class="kstat-div"></div>
      <div class="kstat"><div class="val" style="color:var(--red);">0</div><div class="lbl">Overdue</div></div>
      <div class="kstat-div"></div>
      <div class="kstat"><div class="val" style="font-size:1rem;color:{health_colour};">{health_label}</div><div class="lbl">Health</div></div>
    </div>
  </header>

  <main>

    <!-- OVERVIEW ROW -->
    <div class="overview-row">
      <div class="donut-card">
        <div style="font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--text-dim);margin-bottom:10px;text-align:center;">Overall Progress</div>
        <div class="donut-wrap">{overall_donut}</div>
        <div class="donut-legend">
          <div class="leg-item"><div class="leg-dot" style="background:var(--green);"></div>Done: {done}</div>
          <div class="leg-item"><div class="leg-dot" style="background:var(--primary);"></div>Active: {ip}</div>
          <div class="leg-item"><div class="leg-dot" style="background:rgba(255,255,255,.15);"></div>ToDo: {todo}</div>
        </div>
      </div>
      <div class="exec-card">
        <div class="exec-label">📋 Executive Summary</div>
        <p class="exec-summary">{exec_summary}</p>
        <div class="progress-track"><div class="progress-fill" style="width:{pct}%"></div></div>
        <div class="timeline-row">
          <div class="tl-item"><div class="tl-val" style="color:var(--primary);">{data['end_date']}</div><div class="tl-lbl">Target Launch</div></div>
          <div class="tl-item"><div class="tl-val" style="color:var(--text-muted);">{total}</div><div class="tl-lbl">Total Steps</div></div>
          <div class="tl-item"><div class="tl-val" style="color:var(--green);">{done}</div><div class="tl-lbl">Completed</div></div>
          <div class="tl-item"><div class="tl-val" style="color:var(--text-dim);">0</div><div class="tl-lbl">Overdue</div></div>
        </div>
        <div style="font-size:.72rem;color:var(--text-dim);margin-top:12px;">🔄 Last updated: {generated_ts} &nbsp;·&nbsp; Re-upload Excel to refresh</div>
      </div>
    </div>

    <!-- STAKEHOLDER PROGRESS -->
    <div class="section-head">
      <div class="section-icon">🏢</div>
      <div><h2>Stakeholder Progress</h2></div>
    </div>
    <div class="party-grid">{party_donut_cards}</div>

    <!-- DRI TEAM -->
    <div class="section-head">
      <div class="section-icon">👥</div>
      <div><h2>DRI Team</h2></div>
    </div>
    <div class="dri-grid">{dri_pills}</div>

    <!-- ALL STEPS TABLE -->
    <div class="section-head" style="margin-top:40px;">
      <div class="section-icon">🗂️</div>
      <div><h2>All Steps ({total} total)</h2></div>
    </div>
    <div class="filter-bar">
      <button class="filter-btn active" onclick="filterRows('all',this)">All ({total})</button>
      <button class="filter-btn" onclick="filterRows('status-inprogress',this)">🔄 In Progress ({ip})</button>
      <button class="filter-btn" onclick="filterRows('status-done',this)">✅ Done ({done})</button>
      <button class="filter-btn" onclick="filterRows('status-todo',this)">⏳ To Do ({todo})</button>
    </div>
    <div class="card" style="padding:0;overflow:hidden;">
      <table class="steps-table" id="stepsTable">
        <thead><tr>
          <th>#</th><th>Description</th><th>Responsible</th><th>DRI</th>
          <th>Status</th><th>Est. Date</th><th>Completed</th>
        </tr></thead>
        <tbody>{step_rows}</tbody>
      </table>
    </div>

  </main>
  <footer><p>📊 Status Tracker — {data['title']} &nbsp;·&nbsp; Robin AI Learnings &nbsp;·&nbsp; AI PM Tool &nbsp;·&nbsp; {generated_ts}</p></footer>
</div>
<script>
  function filterRows(cls, btn) {{
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('#stepsTable tbody tr').forEach(row => {{
      row.style.display = (cls === 'all' || row.classList.contains(cls + '-row')) ? '' : 'none';
    }});
  }}
</script>
</body>
</html>"""

# ── projects.html generator ───────────────────────────────────────────────────

def load_project_registry():
    registry_path = BASE_DIR / "projects" / "registry.json"
    if registry_path.exists():
        with open(registry_path) as f:
            return json.load(f)
    return []

def save_project_registry(registry):
    registry_path = BASE_DIR / "projects" / "registry.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with open(registry_path, 'w') as f:
        json.dump(registry, f, indent=2)

def rebuild_projects_hub():
    registry = load_project_registry()
    if not registry:
        cards_html = """
        <div style="text-align:center;padding:60px 20px;color:var(--text-dim);">
          <div style="font-size:3rem;margin-bottom:16px;">📭</div>
          <div style="font-size:16px;font-weight:600;color:var(--text-muted);">No projects yet</div>
          <div style="font-size:13px;margin-top:6px;">Upload your first project to get started</div>
          <a href="new-project.html" style="display:inline-block;margin-top:20px;background:var(--purple-dim);color:var(--purple);border:1px solid rgba(159,110,245,.3);padding:10px 24px;border-radius:10px;text-decoration:none;font-size:13px;font-weight:600;">+ Add New Project</a>
        </div>"""
    else:
        cards_html = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:24px;">'
        COLOURS = ['#4f8ef7','#9f6ef5','#2dd4bf','#f59e0b','#f472b6','#34d399']
        for i, proj in enumerate(registry):
            colour = COLOURS[i % len(COLOURS)]
            prog   = proj.get('progress', 0)
            cards_html += f"""
            <div style="background:var(--surface);border:1px solid var(--border);border-radius:20px;padding:28px;position:relative;overflow:hidden;transition:transform .3s cubic-bezier(.34,1.56,.64,1),box-shadow .3s ease;">
              <div style="position:absolute;top:0;left:0;right:0;height:3px;background:{colour};opacity:.8;border-radius:20px 20px 0 0;"></div>
              <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;">
                <div style="width:46px;height:46px;border-radius:12px;background:rgba(79,142,247,.12);border:1px solid rgba(79,142,247,.2);display:grid;place-items:center;font-size:1.3rem;">📊</div>
                <span style="font-size:11px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;padding:4px 10px;border-radius:20px;background:rgba(52,211,153,.12);color:var(--green);border:1px solid rgba(52,211,153,.25);">{prog}% Done</span>
              </div>
              <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:{colour};margin-bottom:8px;">Project</div>
              <h2 style="font-size:18px;font-weight:700;letter-spacing:-.3px;margin-bottom:10px;">{proj['title']}</h2>
              <p style="font-size:13px;color:var(--text-muted);line-height:1.6;margin-bottom:18px;">{proj.get('objective','')[:120]}{'...' if len(proj.get('objective','')) > 120 else ''}</p>
              <div style="height:5px;background:rgba(255,255,255,.06);border-radius:99px;overflow:hidden;margin-bottom:16px;">
                <div style="height:100%;width:{prog}%;background:{colour};border-radius:99px;"></div>
              </div>
              <div style="display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap;">
                <span style="font-size:11px;font-weight:500;background:rgba(255,255,255,.05);border:1px solid var(--border);color:var(--text-muted);padding:3px 10px;border-radius:8px;">{proj.get('total',0)} milestones</span>
                <span style="font-size:11px;font-weight:500;background:rgba(255,255,255,.05);border:1px solid var(--border);color:var(--text-muted);padding:3px 10px;border-radius:8px;">{proj.get('dris',0)} DRIs</span>
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
                <a href="projects/{proj['slug']}/prd.html" style="display:flex;align-items:center;justify-content:center;gap:6px;padding:9px;background:var(--primary-dim);border:1px solid rgba(79,142,247,.3);border-radius:10px;text-decoration:none;color:var(--primary);font-size:12px;font-weight:600;transition:all .2s;">📄 PRD</a>
                <a href="projects/{proj['slug']}/status-tracker.html" style="display:flex;align-items:center;justify-content:center;gap:6px;padding:9px;background:var(--green-dim);border:1px solid rgba(52,211,153,.3);border-radius:10px;text-decoration:none;color:var(--green);font-size:12px;font-weight:600;transition:all .2s;">📊 Tracker</a>
              </div>
            </div>"""
        cards_html += '</div>'

    total   = len(registry)
    updated = datetime.now().strftime('%b %d, %Y %H:%M')

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>All Projects — AI PM Tool</title>
  <style>
{CSS_VARS}
    .hero {{ text-align:center; padding:56px 24px 36px; position:relative; z-index:1; }}
    .eyebrow {{ display:inline-flex;align-items:center;gap:8px;font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--primary);margin-bottom:16px; }}
    .eyebrow::before,.eyebrow::after {{ content:'';display:block;width:22px;height:1px;background:var(--primary);opacity:.5; }}
    .hero h1 {{ font-size:clamp(28px,4vw,46px);font-weight:800;letter-spacing:-1.2px;background:linear-gradient(135deg,#fff 30%,var(--primary) 65%,var(--purple));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:12px; }}
    .hero p {{ font-size:15px;color:var(--text-muted);max-width:440px;margin:0 auto 24px; }}
    .hero-stats {{ display:inline-flex;align-items:center;gap:22px;background:rgba(255,255,255,.04);border:1px solid var(--border);border-radius:12px;padding:11px 22px; }}
    .hstat .val {{ font-size:1.4rem;font-weight:800; }}
    .hstat .lbl {{ font-size:.68rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px; }}
    .hdiv {{ width:1px;height:26px;background:var(--border2); }}
    .add-btn {{ display:inline-flex;align-items:center;gap:7px;background:linear-gradient(135deg,var(--purple),var(--primary));color:#fff;border:none;padding:11px 22px;border-radius:11px;font-size:13px;font-weight:700;text-decoration:none;cursor:pointer;box-shadow:0 4px 18px rgba(159,110,245,.3);transition:opacity .2s,transform .2s; }}
    .add-btn:hover {{ opacity:.9;transform:translateY(-1px); }}
    main {{ position:relative;z-index:1;max-width:1100px;margin:0 auto;padding:16px 40px 80px; }}
    .toolbar {{ display:flex;justify-content:space-between;align-items:center;margin-bottom:24px; }}
    .toolbar-left {{ font-size:13px;color:var(--text-muted); }}
  </style>
</head>
<body>
<div class="page">
  <nav>
    <a class="nav-logo" href="default.html">
      <div class="nav-logo-icon">🤖</div>
      <div class="nav-logo-text">AI <span>PM</span> Tool</div>
    </a>
    <a class="back-btn" href="default.html">← Dashboard</a>
  </nav>
  <section class="hero">
    <div class="eyebrow">Project Hub</div>
    <h1>All Projects</h1>
    <p>Track every project's PRD, milestones, and DRIs in one place.</p>
    <div style="display:flex;flex-direction:column;align-items:center;gap:16px;">
      <div class="hero-stats">
        <div class="hstat"><div class="val">{total}</div><div class="lbl">Projects</div></div>
        <div class="hdiv"></div>
        <div class="hstat"><div class="val">{sum(p.get('total',0) for p in registry)}</div><div class="lbl">Milestones</div></div>
        <div class="hdiv"></div>
        <div class="hstat"><div class="val">{sum(p.get('done',0) for p in registry)}</div><div class="lbl">Completed</div></div>
      </div>
      <a href="new-project.html" class="add-btn">✨ Add New Project</a>
    </div>
  </section>
  <main>
    <div class="toolbar">
      <div class="toolbar-left">{total} project{'s' if total != 1 else ''} &nbsp;·&nbsp; Last updated {updated}</div>
    </div>
    {cards_html}
  </main>
  <footer><p>📊 All Projects &nbsp;·&nbsp; Robin AI Learnings &nbsp;·&nbsp; AI PM Tool</p></footer>
</div>
</body>
</html>"""

    with open(BASE_DIR / "projects.html", 'w') as f:
        f.write(html)

# ── HTTP handler ──────────────────────────────────────────────────────────────

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def do_GET(self):
        if self.path == "/" or self.path == "":
            self.path = "/default.html"
        return super().do_GET()

    def do_POST(self):
        if self.path == "/upload-project":
            self.handle_upload()
        else:
            self.send_error(404)

    def handle_upload(self):
        try:
            ctype, pdict = cgi.parse_header(self.headers.get('Content-Type', ''))
            if 'boundary' in pdict:
                pdict['boundary'] = pdict['boundary'].encode('utf-8')
            pdict['CONTENT-LENGTH'] = int(self.headers.get('Content-Length', 0))

            form = cgi.parse_multipart(self.rfile, pdict)

            file_data   = form.get('file', [None])[0]
            gen_prd     = form.get('genPrd',     [b'true'])[0]
            gen_tracker = form.get('genTracker', [b'true'])[0]
            overwrite   = form.get('overwrite',  [b'true'])[0]

            if file_data is None:
                raise ValueError("No file received")

            # Save uploaded file to temp
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
                tmp.write(file_data if isinstance(file_data, bytes) else file_data.encode())
                tmp_path = tmp.name

            # Parse Excel
            data = parse_excel(tmp_path)
            os.unlink(tmp_path)

            # Create project directory
            proj_dir = PROJECTS_DIR / data['slug']
            proj_dir.mkdir(parents=True, exist_ok=True)

            prd_path     = proj_dir / "prd.html"
            tracker_path = proj_dir / "status-tracker.html"
            url_prefix   = f"projects/{data['slug']}"

            # Generate pages
            should_prd     = str(gen_prd).lower() in ('true', "b'true'", '1')
            should_tracker = str(gen_tracker).lower() in ('true', "b'true'", '1')

            if should_prd:
                with open(prd_path, 'w', encoding='utf-8') as f:
                    f.write(generate_prd(data, url_prefix))

            if should_tracker:
                with open(tracker_path, 'w', encoding='utf-8') as f:
                    f.write(generate_tracker(data, url_prefix))

            # Update registry
            registry = load_project_registry()
            existing = next((i for i, p in enumerate(registry) if p['slug'] == data['slug']), None)
            entry = {
                'slug':      data['slug'],
                'title':     data['title'],
                'objective': data['objective'],
                'total':     data['total'],
                'done':      data['done'],
                'progress':  data['progress'],
                'dris':      len(data['dris']),
                'updated':   datetime.now().isoformat(),
            }
            if existing is not None:
                registry[existing] = entry
            else:
                registry.append(entry)
            save_project_registry(registry)

            # Rebuild projects hub
            rebuild_projects_hub()

            # Send response
            resp = json.dumps({
                'success':     True,
                'projectName': data['title'],
                'slug':        data['slug'],
                'prdUrl':      f"/{url_prefix}/prd.html",
                'trackerUrl':  f"/{url_prefix}/status-tracker.html",
                'stepsCount':  data['total'],
                'dris':        [d['name'] for d in data['dris']],
            })
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(resp.encode())

        except Exception as e:
            err = json.dumps({'error': str(e)})
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(err.encode())

    def log_message(self, format, *args):
        print(f"  {self.address_string()} → {args[0]}")


if __name__ == "__main__":
    # Ensure openpyxl is available
    try:
        import openpyxl
    except ImportError:
        print("Installing openpyxl...")
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "pip", "install", "openpyxl", "-q"],
            capture_output=True
        )
        if result.returncode != 0:
            subprocess.run(["pip3", "install", "openpyxl", "-q"])
        print("openpyxl installed — ready.")

    # Build initial projects hub if it doesn't exist
    if not (BASE_DIR / "projects.html").exists():
        rebuild_projects_hub()

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.allow_reuse_address = True
        print(f"\n🚀  AI PM Tool server running at http://localhost:{PORT}")
        print(f"📁  Serving from: {BASE_DIR}")
        print(f"🌐  Landing page: default.html")
        print(f"📤  Upload endpoint: POST /upload-project")
        print(f"\n   Press Ctrl+C to stop.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n✅  Server stopped.")
