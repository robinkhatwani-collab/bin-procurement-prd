# CLAUDE.md — AI PM Tool Project Standards

This file defines the rules, design system, and conventions Claude must follow when working on this project. Always read this file before creating or editing any file in this project.

---

## Project Overview

**Name:** AI PM Tool  
**Owner:** Robin Khatwani (robin.khatwani@gmail.com)  
**Purpose:** A personal learning and project management dashboard for AI Product Management — hosted locally at `http://localhost:8080`.  
**Stack:** Pure HTML + CSS + vanilla JavaScript (no frameworks, no build tools)  
**Server:** Python HTTP server via `server.py` and `start_server.sh`, port 8080

---

## File Structure

```
AI_PM_Tool/
├── CLAUDE.md                    ← This file (project standards)
├── default.html                 ← Landing page / Dashboard (root "/")
├── ai-learning.html             ← AI Learning Hub (6-week card grid)
├── Week1_Learning_Summary.html  ← Week 1 detailed learning summary
├── server.py                    ← Python HTTP server (custom handler)
├── start_server.sh              ← Shell script to launch server on port 8080
└── Project_Input_BIN_SS.xlsx    ← Source data file (do not delete)
```

### Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Hub / section pages | `kebab-case.html` | `ai-learning.html` |
| Weekly summaries | `Week{N}_Learning_Summary.html` | `Week2_Learning_Summary.html` |
| Assets / scripts | `kebab-case` | `chart-utils.js` |
| CSS files (if split) | `kebab-case.css` | `design-tokens.css` |

**Rules:**
- Never rename `default.html` — it is the server root (`/`)
- Never rename `server.py` or `start_server.sh`
- Weekly summary files must follow `Week{N}_Learning_Summary.html` exactly so the AI Learning hub cards can link to them predictably

---

## Design System

All pages must use this design system consistently. Do not deviate without being explicitly asked.

### Colour Tokens (CSS variables — define in `:root`)

```css
:root {
  /* Backgrounds */
  --bg:           #0b0f1a;   /* page background */
  --surface:      #111827;   /* card / panel background */
  --surface2:     #161d2e;   /* nested element background */
  --surface3:     #1c2540;   /* deepest nested background */

  /* Borders */
  --border:       rgba(255,255,255,0.08);   /* default border */
  --border2:      rgba(255,255,255,0.13);   /* slightly more visible */

  /* Text */
  --text:         #f0f4ff;   /* primary text (alias: --text-primary) */
  --text-muted:   #8b9ab4;   /* secondary / descriptive text */
  --text-dim:     #5a6a84;   /* labels, caps, very subtle text */

  /* Accent colours */
  --primary:      #4f8ef7;   /* blue  — main accent */
  --secondary:    #2dd4bf;   /* teal  — secondary accent */
  --purple:       #9f6ef5;   /* purple */
  --accent:       #f59e0b;   /* amber */
  --green:        #34d399;   /* green */
  --red:          #f87171;   /* red / error */
  --rose:         #f472b6;   /* pink / rose */

  /* Glow variants (use in box-shadow / radial-gradient) */
  --glow-blue:    rgba(79,142,247,0.22);
  --glow-purple:  rgba(159,110,245,0.22);
  --glow-teal:    rgba(45,212,191,0.22);
  --glow-amber:   rgba(245,158,11,0.22);
  --glow-rose:    rgba(244,114,182,0.22);
  --glow-green:   rgba(52,211,153,0.22);

  /* Dim / tinted backgrounds (use inside cards) */
  --primary-dim:  rgba(79,142,247,0.15);
  --purple-dim:   rgba(159,110,245,0.15);
  --secondary-dim:rgba(45,212,191,0.15);
  --accent-dim:   rgba(245,158,11,0.15);
  --green-dim:    rgba(52,211,153,0.15);
  --red-dim:      rgba(248,113,113,0.15);

  /* Shared */
  --radius:  14px;
  --shadow:  0 4px 24px rgba(0,0,0,0.35);
}
```

### Typography

- **Font:** `Inter` (Google Fonts) — weights 300, 400, 500, 600, 700, 800
- **Import:** Always include `@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');`
- **Body:** `font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); line-height: 1.7;`
- **Headings:** `font-weight: 700–800`, `letter-spacing: -0.3px to -1.5px` for large headings
- **Labels / caps:** `font-size: 0.72–0.85rem`, `text-transform: uppercase`, `letter-spacing: 1–1.5px`, `font-weight: 700`

### Week Colour Assignments

Each week has a dedicated accent colour used consistently across hub card and summary page:

| Week | Colour | Hex | Glow |
|------|--------|-----|------|
| Week 1 | Blue | `#4f8ef7` | `rgba(79,142,247,0.22)` |
| Week 2 | Purple | `#9f6ef5` | `rgba(159,110,245,0.22)` |
| Week 3 | Teal | `#2dd4bf` | `rgba(45,212,191,0.22)` |
| Week 4 | Amber | `#f59e0b` | `rgba(245,158,11,0.22)` |
| Week 5 | Rose | `#f472b6` | `rgba(244,114,182,0.22)` |
| Week 6 | Green | `#34d399` | `rgba(52,211,153,0.22)` |

---

## Component Patterns

### Standard Card

```html
<div class="card">
  <h3>Card Title</h3>
  <p>Description text in var(--text-muted)</p>
</div>
```

```css
.card {
  background: var(--surface);
  border-radius: var(--radius);
  border: 1px solid var(--border);
  padding: 26px;
  box-shadow: var(--shadow);
  margin-bottom: 20px;
}
```

### Callout / Alert Box

Four variants — always use the right semantic colour:

```html
<div class="callout callout-purple"> <!-- purple = definition / concept -->
<div class="callout callout-blue">   <!-- blue   = explanation / context -->
<div class="callout callout-green">  <!-- green  = tip / insight -->
<div class="callout callout-amber">  <!-- amber  = warning / PM tip -->
```

### Navigation Header (sticky)

Every page must have a sticky top nav with:
- Left: logo linking to `default.html`
- Right: back button linking to the parent page

```html
<nav class="top-nav">
  <a class="nav-logo" href="default.html">...</a>
  <a class="back-btn" href="[parent].html">← [Parent Page Name]</a>
</nav>
```

### Ambient Background Glow

Apply to `body::before` on all pages:
```css
body::before {
  content: '';
  position: fixed; inset: 0;
  background:
    radial-gradient(ellipse 70% 50% at 15% 15%, rgba(79,142,247,.09) 0%, transparent 60%),
    radial-gradient(ellipse 60% 45% at 85% 75%, rgba(159,110,245,.09) 0%, transparent 60%);
  pointer-events: none; z-index: 0;
}
```

### Phase Divider

Used in weekly summary pages to separate learning phases:
```html
<div class="phase-divider">
  <span class="pd-badge pd-1">🟣 Phase 1 — Phase Name</span>
  <div class="pd-line"></div>
</div>
```

---

## Page-Level Rules

### default.html (Landing / Dashboard)
- Three cards: All Project Summary (blue), Add New Project (purple), AI Learning (teal)
- AI Learning card **must** link to `ai-learning.html`
- All Project Summary card **must** link to project summary page (when built)
- Add New Project card **must** link to project creation page (when built)
- Do not add more than 6 cards to this page without being asked

### ai-learning.html (Learning Hub)
- Always shows exactly 6 week cards (Week 1–6)
- Week colours must follow the Week Colour Assignments table above
- Available weeks: full hover effect, link to `Week{N}_Learning_Summary.html`, status badge = "✓ Complete"
- Locked weeks: `opacity: 0.65`, no hover lift, status badge = "Coming Soon", no `href`
- Progress bar width = `(completed weeks / 6) * 100%`
- Update stats (Topics Covered, Weeks Done) when new weeks are unlocked

### Week Summary Pages (Week{N}_Learning_Summary.html)
- Must use the dark theme — never revert to a light theme
- Must include the sticky top nav with back link to `ai-learning.html`
- Must follow the 5-phase learning structure with phase dividers
- All content sections must use the standard card, callout, and grid components
- Key Takeaways section must be present at the bottom of every week page
- Footer must credit "Robin AI Learnings"

---

## Interaction & Animation Rules

- Cards get `transform: translateY(-7px) scale(1.01)` on hover
- Use `cubic-bezier(.34,1.56,.64,1)` for spring-like card hover transitions
- Hover transitions: `0.3s` duration
- CTA arrows inside cards animate gap on hover: `gap: 5px` → `gap: 9px`
- Locked/Coming Soon cards: NO hover transform, `cursor: default`
- All interactive elements must have a visible `:hover` state
- Sticky headers use `backdrop-filter: blur(12px)` + semi-transparent background

---

## Server Rules

- Port: **8080** (never change without updating both `server.py` and `start_server.sh`)
- Default page: **`default.html`** (the custom handler maps `/` → `/default.html`)
- Start command: `bash start_server.sh` (run from Terminal in the project folder)
- If port 8080 is already in use, `start_server.sh` kills the existing process first
- Never use `index.html` as the entry point — the project uses `default.html`

---

## Content Rules

### AI Learning Weekly Summaries
- Each week summary must cover a focused AI/PM topic area
- Structure: Hero → Learning Path Nav → Phase Divider → Sections → Key Takeaways → Footer
- Every section must have: section icon, section number ("Topic N of M"), section heading
- Use the RITG framework reference where prompt engineering is discussed
- Use the MOAT framework reference where AI product strategy is discussed
- Always include a "PM Guide" or "PM Tip" callout in each phase

### New Pages
- Every new HTML page must import the Inter font
- Every new page must define the full `:root` CSS variable block
- Every new page must include the ambient background glow on `body::before`
- Every new page must have the sticky top nav with correct back navigation

---

## What NOT To Do

- ❌ Do not use light backgrounds (`#fff`, `#f8fafc`) — this is a dark-theme project
- ❌ Do not use external CSS frameworks (Bootstrap, Tailwind CDN classes)
- ❌ Do not use JavaScript frameworks (React, Vue) — plain JS only
- ❌ Do not create `index.html` — the root is `default.html`
- ❌ Do not change port 8080 without being asked
- ❌ Do not delete or rename `server.py`, `start_server.sh`, or `default.html`
- ❌ Do not add `localStorage` usage — no state persistence needed
- ❌ Do not use emoji in file names
- ❌ Do not create separate CSS or JS files unless explicitly asked — keep everything in a single HTML file per page

---

## Future Pages (Planned)

| Page | File Name | Trigger Card |
|------|-----------|--------------|
| All Project Summary | `projects.html` | default.html → blue card |
| Add New Project | `new-project.html` | default.html → purple card |
| Week 2 Summary | `Week2_Learning_Summary.html` | ai-learning.html → Week 2 card |
| Week 3 Summary | `Week3_Learning_Summary.html` | ai-learning.html → Week 3 card |
| Week 4 Summary | `Week4_Learning_Summary.html` | ai-learning.html → Week 4 card |
| Week 5 Summary | `Week5_Learning_Summary.html` | ai-learning.html → Week 5 card |
| Week 6 Summary | `Week6_Learning_Summary.html` | ai-learning.html → Week 6 card |

When a new week summary is created:
1. Build `Week{N}_Learning_Summary.html` matching the dark theme template
2. Update `ai-learning.html` — change that week's card from `locked` → `available`, update the `href`, change status badge to "✓ Complete", update progress bar and stats

---

## Quick Reference — Page Navigation Flow

```
default.html
├── → ai-learning.html         (AI Learning card)
│   ├── → Week1_Learning_Summary.html   (Week 1 card)
│   ├── → Week2_Learning_Summary.html   (Week 2 card — future)
│   └── ...
├── → projects.html            (All Project Summary — future)
└── → new-project.html         (Add New Project — future)
```
