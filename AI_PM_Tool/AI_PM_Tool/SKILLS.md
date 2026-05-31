# SKILLS.md — AI PM Tool Reusable Workflows

This file defines the skills (repeatable multi-step workflows) Claude must follow for this project.
Every skill references `CLAUDE.md` as the quality gate — all generated pages must pass the evaluation
checklist before being considered complete.

**Always read `CLAUDE.md` before executing any skill.**

---

## Skill Index

| Skill | Trigger Phrases | Output |
|-------|----------------|--------|
| [`create-project`](#skill-1-create-project) | "add a new project", "create a project", "new project" | `project-{slug}.html` + updated `projects.html` |
| [`create-week-summary`](#skill-2-create-week-summary) | "create week N summary", "add week N", "build week N" | `Week{N}_Learning_Summary.html` + updated `ai-learning.html` |

---

## Skill 1: create-project

### Trigger Phrases
- "add a new project"
- "create a project"
- "new project"
- "I want to track a project"
- "set up a project"

### Purpose
When a user adds a new project, automatically generate a dedicated status tracker page for it
and wire it into the `projects.html` hub. Every project gets a consistent, dark-themed page
that tracks status, milestones, goals, and progress — all matching the design system in `CLAUDE.md`.

---

### Step 1 — Intake (Ask the User)

Ask the user for the following before generating anything. Collect all answers before proceeding.

| Field | Question | Required? |
|-------|----------|-----------|
| Project Name | "What is the name of your project?" | ✅ Yes |
| One-line Goal | "What is the goal of this project in one sentence?" | ✅ Yes |
| Status | "What is the current status? (Planning / In Progress / On Hold / Complete)" | ✅ Yes |
| Start Date | "When did or will the project start? (e.g. May 2026)" | ✅ Yes |
| Target Date | "What is the target completion date?" | ✅ Yes |
| Key Milestones | "List up to 5 key milestones with their status (Done / In Progress / Upcoming)" | ✅ Yes |
| Description | "Give a brief description of what this project involves (2–3 sentences)" | ✅ Yes |
| Accent Colour | "Pick an accent colour: Blue / Purple / Teal / Amber / Rose / Green" | Optional (default: Blue) |

---

### Step 2 — Read Standards

Before generating the page, read `CLAUDE.md` and confirm:
- The full `:root` CSS variable block to use
- The sticky nav pattern (logo → `default.html`, back → `projects.html`)
- The card, callout, and grid component patterns
- The ambient background glow rule for `body::before`
- The Inter font import

---

### Step 3 — Generate the Status Tracker Page

**File name:** `project-{slug}.html`
Where `{slug}` is the project name lowercased, spaces replaced with hyphens.
Example: "AI Chatbot" → `project-ai-chatbot.html`

**Required page sections (in order):**

1. **Sticky Top Nav**
   - Left: AI PM Tool logo → `default.html`
   - Right: Back button → `projects.html`

2. **Hero Section**
   - Project name as H1
   - One-line goal as subtitle
   - Status badge (colour-coded: green = Complete, blue = In Progress, amber = On Hold, purple = Planning)
   - Start date and target date pills

3. **Progress Overview Card**
   - Visual progress bar (calculate % from milestones: Done milestones ÷ Total milestones × 100)
   - Summary stats row: Total Milestones, Completed, Remaining, Days to Target

4. **Goal & Description Card**
   - Full project description
   - Blue callout with the one-line goal highlighted

5. **Milestones Tracker**
   - One card per milestone
   - Each card shows: milestone name, status badge, brief description (if provided)
   - Status colours: ✅ Done = green, 🔄 In Progress = blue, ⏳ Upcoming = muted

6. **Key Metrics / Notes Card**
   - Placeholder section for tracking decisions, blockers, or notes
   - Pre-filled with 2–3 example placeholder entries in muted text

7. **Footer**
   - "Robin AI Learnings · AI PM Tool"

---

### Step 4 — Self-Evaluate the Generated Page

Before saving the file, run through this checklist. Fix any failures before proceeding.

**Design Standards (from CLAUDE.md)**
- [ ] `body` background is `var(--bg)` (`#0b0f1a`) — NOT white or light grey
- [ ] All CSS colours use the `:root` variable tokens, not hardcoded hex values
- [ ] Inter font is imported from Google Fonts with weights 300–800
- [ ] `body::before` ambient glow is present and uses the correct radial gradients
- [ ] Sticky top nav is present with correct logo and back-button links

**Page Structure**
- [ ] All 7 required sections are present and in the correct order
- [ ] Hero has project name, status badge, and date pills
- [ ] Progress bar percentage is mathematically correct
- [ ] At least 1 milestone card exists
- [ ] Footer credits "Robin AI Learnings"

**Component Compliance**
- [ ] Cards use `background: var(--surface)` and `border: 1px solid var(--border)`
- [ ] Callouts use the correct variant class (`callout-blue`, `callout-green`, etc.)
- [ ] Status badges use colour-coded backgrounds from the design token palette
- [ ] Hover states are defined on all interactive elements

**Navigation**
- [ ] Logo links to `default.html`
- [ ] Back button links to `projects.html`
- [ ] No broken `href="#"` placeholders left in the file

**Code Quality**
- [ ] Everything is in a single `.html` file — no separate CSS or JS files
- [ ] No external frameworks (Bootstrap, Tailwind, React, Vue)
- [ ] No `localStorage` usage
- [ ] File is named correctly: `project-{slug}.html`

---

### Step 5 — Wire Up projects.html

After the tracker page passes evaluation, update `projects.html`:

1. Add a new project card to the grid with:
   - Project name
   - One-line goal
   - Status badge
   - Link: `href="project-{slug}.html"`
   - Accent colour matching the chosen colour

2. Update the stats in the `projects.html` hero section:
   - Increment "Total Projects" count
   - Increment the relevant status count (Active / Planning / Complete)

If `projects.html` does not exist yet, create it before adding the card. It must follow CLAUDE.md
standards — dark theme, sticky nav, ambient glow, and a grid of project cards.

---

### Step 6 — Report

Confirm what was built:
- File created: `project-{slug}.html`
- `projects.html` updated: Yes / No (created if missing)
- Evaluation checklist: All passed / N items fixed
- Link to open: `http://localhost:8080/project-{slug}.html`

---

---

## Skill 2: create-week-summary

### Trigger Phrases
- "create week N summary"
- "add week N"
- "build week N"
- "write the week N learning page"
- "unlock week N"

### Purpose
Scaffold a new weekly learning summary page for the AI Learning Hub, then update
`ai-learning.html` to unlock that week's card, update the progress bar, and update stats.
Every week page must follow the same dark-themed 5-phase structure used in `Week1_Learning_Summary.html`.

---

### Step 1 — Intake (Ask the User)

Ask the user for the following before generating anything.

| Field | Question | Required? |
|-------|----------|-----------|
| Week Number | "Which week number is this? (2–6)" | ✅ Yes |
| Week Title | "What is the title/topic of this week? (e.g. Large Language Models & GenAI)" | ✅ Yes |
| Phase Names | "What are the 5 phase names for this week? (e.g. Phase 1 — Foundation, Phase 2 — Architecture…)" | ✅ Yes |
| Topics | "List all topics covered this week — one line each with the topic name and a brief summary" | ✅ Yes |
| Key Takeaways | "What are the 5 key takeaways — one per phase?" | ✅ Yes |
| Total Topic Count | "How many total topics does this week cover?" | ✅ Yes |

---

### Step 2 — Read Standards

Before generating the page, read `CLAUDE.md` and confirm:
- The week's assigned accent colour from the Week Colour Assignments table
- The sticky nav pattern (back link → `ai-learning.html`)
- The phase divider pattern and pd-badge colour classes
- The section header pattern (icon, section number, heading)
- The Key Takeaways section structure

Also read `Week1_Learning_Summary.html` as the reference template — the new page must match
its structure, component usage, and dark theme exactly.

---

### Step 3 — Generate the Week Summary Page

**File name:** `Week{N}_Learning_Summary.html`
Example: Week 2 → `Week2_Learning_Summary.html`

**Required page structure (in order):**

1. **Sticky Top Nav**
   - Left: AI PM Tool logo → `default.html`
   - Right: Back button → `ai-learning.html`

2. **Hero Section**
   - Badge: "AI [Topic Area] · Week N"
   - H1: Week title with emoji
   - Subtitle describing the learning journey
   - Stats pill: "X Topics · 5 Learning Phases · [Difficulty level]"

3. **Learning Path Nav**
   - 5 phase blocks with phase name and topic links
   - Each phase block styled with the week's accent colour
   - Anchor links to corresponding section IDs

4. **5 Phases of Content**
   Each phase must contain:
   - Phase divider with `pd-badge` in the correct colour class
   - At least 2 topic sections per phase
   - Each topic section: section icon, section number ("Topic N of M"), section heading
   - Mix of: cards, callouts, grids, comparison tables, or code blocks as appropriate
   - At least 1 PM Guide or PM Tip callout per phase (use `callout-amber`)

5. **Key Takeaways Section**
   - Dark gradient background section
   - One takeaway card per phase (5 total)
   - Phase 5 takeaway spans full width
   - Each card has: phase label, bold headline, supporting sentence

6. **Footer**
   - "Week N — [Topic] · Robin AI Learnings · Step-by-Step Guide"

---

### Step 4 — Self-Evaluate the Generated Page

Before saving the file, run through this checklist. Fix any failures before proceeding.

**Design Standards (from CLAUDE.md)**
- [ ] `body` background is `var(--bg)` — dark theme only, no light colours
- [ ] Week accent colour matches the Week Colour Assignments table in CLAUDE.md
- [ ] Inter font imported with weights 300–800
- [ ] `body::before` ambient glow is present
- [ ] Sticky top nav present with correct back link to `ai-learning.html`

**Page Structure**
- [ ] All 6 required sections are present in the correct order
- [ ] Exactly 5 phase dividers are present
- [ ] Every phase has at least 2 topic sections
- [ ] Every topic section has: icon, section number, heading
- [ ] Every phase has at least 1 PM Guide / PM Tip callout
- [ ] Key Takeaways section has exactly 5 cards (Phase 5 spans full width)
- [ ] Footer is present and credits "Robin AI Learnings"

**Component Compliance**
- [ ] Phase divider badges use the correct `pd-N` class and colour for each phase
- [ ] Callouts use correct semantic variant (purple = definition, blue = context, green = tip, amber = PM tip)
- [ ] Cards use `var(--surface)` background and `var(--border)` border
- [ ] Section icons are wrapped in `.section-icon` div

**Content Quality**
- [ ] All topics from the intake are represented in the page
- [ ] All 5 key takeaways from the intake are included in the Key Takeaways section
- [ ] No placeholder text (e.g. "Lorem ipsum", "TODO", "Coming soon") left in the page
- [ ] At least one practical PM-focused callout or guide per phase

**Navigation**
- [ ] Logo links to `default.html`
- [ ] Back button links to `ai-learning.html`
- [ ] Learning path nav anchor links all point to valid section IDs on the page

**Code Quality**
- [ ] Single `.html` file — no separate CSS or JS files
- [ ] No external CSS/JS frameworks
- [ ] File named exactly: `Week{N}_Learning_Summary.html`

---

### Step 5 — Update ai-learning.html

After the summary page passes evaluation, update `ai-learning.html`:

1. **Unlock the week card:**
   - Change the card `<div class="week-card wkN locked">` → `<a class="week-card wkN available" href="Week{N}_Learning_Summary.html">`
   - Change status badge from `badge-soon` → `badge-done` with text "✓ Complete"
   - Update card title, description, and topic pills to match the actual week content
   - Remove `opacity: 0.4` from the CTA and change text from "🔒 Locked" to "View Summary →"
   - Update `card-meta` from "Coming soon" to "N Topics · 5 Phases"

2. **Update the progress bar:**
   - New width = `(completed weeks / 6) * 100%`
   - Example: 2 weeks done → `width: 33.33%`

3. **Update hero stats:**
   - "Weeks Done" count: increment by 1
   - "Topics Covered" count: add this week's topic count to the running total

---

### Step 6 — Report

Confirm what was built:
- File created: `Week{N}_Learning_Summary.html`
- `ai-learning.html` updated: Week N card unlocked, progress bar at X%, stats updated
- Evaluation checklist: All passed / N items fixed
- Link to open: `http://localhost:8080/Week{N}_Learning_Summary.html`

---

## General Rules for All Skills

1. **Always read `CLAUDE.md` first** before generating any file
2. **Never skip the evaluation checklist** — it is a mandatory step, not optional
3. **Fix evaluation failures inline** — do not report failures and move on; fix them before saving
4. **Never leave placeholder content** in generated pages — all content must be real and populated
5. **Update linked pages** — generating a new page always requires updating its parent hub page
6. **Single file output** — all HTML, CSS, and JS goes in one `.html` file per page
7. **Confirm before overwriting** — if a file already exists, tell the user before replacing it
