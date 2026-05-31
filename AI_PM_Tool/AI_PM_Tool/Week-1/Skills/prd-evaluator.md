---
name: prd-evaluator
description: >
  Evaluates a Product Requirements Document (PRD) against a structured self-evaluation checklist covering Problem Definition, Solution Definition, and Core Metrics. Use this skill whenever a PM shares a PRD and asks for feedback, review, evaluation, or a checklist check. Also trigger when someone says "evaluate my PRD", "review my product doc", "check my PRD", "does my PRD cover everything", "what's missing from my PRD", or pastes a PRD and asks what they should improve. Always use this skill when any PRD or product spec document is shared — even if the request is casual like "thoughts on my doc?" or "can you look over this?".
---

# PRD Evaluator Skill

## Step 1: Check for PRD Input

Before doing anything else, check whether the user has already provided a PRD in their message.

- If a PRD is present (pasted text, uploaded document, or clear product spec content): proceed directly to the evaluation below.
- If no PRD has been provided: ask for it before proceeding. Use this prompt:

> "Please paste your PRD below and I'll evaluate it against the full checklist covering Problem Definition, Solution Definition, and Core Metrics."

Do not attempt to evaluate without a PRD. Do not ask any other questions first.

---

## Step 2: Evaluate the PRD

Once you have the PRD, evaluate it against the checklist. Your job is to:
1. Score each checklist item as Pass or Fail
2. Highlight gaps clearly
3. Explain **what to write** for any failing item — be specific and actionable, not generic

---

## Evaluation Checklist

### Section 1: Problem Definition

| # | Criterion | Pass Condition |
|---|-----------|---------------|
| 1.1 | Problem & job-to-be-done clearly articulated | PRD states what the user is trying to accomplish and what's currently broken or missing |
| 1.2 | Customer persona(s) defined with role, industry, needs | At least one persona with specific role + industry + pain point — not just "enterprise users" |
| 1.3 | Problem validated with real data or market research | Includes stats, interviews, survey data, market size, or cited research — not just assertions |
| 1.4 | Why this problem is worth solving for this user | Explains urgency, frequency, or cost of the problem to the target persona |
| 1.5 | Clear and defensible MOAT defined | States what makes this hard to copy — data advantage, network effects, workflow lock-in, etc. |
| 1.6 | Justification for Agentic AI over rule-based systems | Explains why rules/logic alone can't solve this — references variability, context, or judgment calls |
| 1.7 | Unstructured data types listed + need for ML/LLMs explained | Names the unstructured inputs (emails, PDFs, voice, etc.) and why pattern-matching fails |
| 1.8 | Differentiated from ChatGPT, Copilots, Claude Code, or similar | Explicitly addresses why existing AI tools don't solve this — workflow fit, specialization, or integration |

---

### Section 2: Solution Definition

| # | Criterion | Pass Condition |
|---|-----------|---------------|
| 2.1 | Visual user flow included (input → processing → output) | Contains a diagram, flowchart, or clearly structured step-by-step flow — not just prose |
| 2.2 | AI drawbacks addressed (hallucination, explainability, etc.) | At least 2 risks acknowledged with mitigations (e.g. human-in-loop, confidence scores, audit trails) |
| 2.3 | Core functional requirements in user story format | Uses "As a [user], I want [action] so that [outcome]" format for key features |
| 2.4 | Agent capabilities and system behavior clearly described | States what the agent can do autonomously, what requires human approval, and how it handles errors |

---

### Section 3: Core Metrics

| # | Criterion | Pass Condition |
|---|-----------|---------------|
| 3.1 | North Star metric defined | One clear metric that captures overall product success (e.g. "hours saved per user per week") |
| 3.2 | 1–2 primary metrics listed | Includes accuracy, time saved, task completion rate, or similar quantifiable outcomes |
| 3.3 | Secondary/supporting metrics included | Covers adoption, retention, cost reduction, or NPS — at least one |
| 3.4 | Metrics are measurable and trackable over time | Each metric has a unit, baseline or target, and a plausible way to measure it |

---

## Output Format

Structure your response exactly like this:

---

### PRD Evaluation Report

**Overall Score: X / 16 items passing**

---

#### Section 1: Problem Definition — X/8

| Item | Status | Notes |
|------|--------|-------|
| 1.1 Problem & JTBD | ✅ / ❌ | One sentence on what's present or missing |
| ... | | |

**Gaps to Address:**
For each ❌ item, write a short paragraph:
- **What's missing:** [specific gap]
- **What to write:** [concrete guidance — what a good version of this would include, with an example if helpful]

---

#### Section 2: Solution Definition — X/4

[same format]

---

#### Section 3: Core Metrics — X/4

[same format]

---

### Top 3 Priorities
List the 3 most important gaps to fix first, ranked by impact on PRD quality.

### Strengths
Call out 2–3 things the PRD does well, to reinforce good habits.

---

## Tone & Style Guidelines

- Be direct and specific — PMs need actionable feedback, not vague encouragement
- When something is missing, always say **what to write**, not just "add more detail"
- Use examples when helpful (e.g. "Instead of 'enterprise users', try 'Mid-market SaaS RevOps managers at companies with 200–500 employees'")
- Keep the evaluation grounded in the actual PRD content — quote or reference specific sections when calling out gaps
- Be honest: a PRD that scores 8/16 should feel like 8/16, not softened to feel like a B+