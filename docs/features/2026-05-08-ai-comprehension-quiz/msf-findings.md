# MSF Findings — AI Comprehension Quiz

**Date:** 2026-05-08
**Source doc:** `01_requirements.md` (Tier 3 — Approved)
**Mode:** /msf-req (text-only; no PSYCH scoring)
**Scope:** 2 personas × 2 scenarios each × 3 journeys

---

## Personas

| ID | Name | Context | Scenarios |
|---|---|---|---|
| P1 | Post-Read Reflective | Just finished a non-fiction book; wants a breadth comprehension check | (a) 15-min slot between meetings, casual reflection; (b) prepping for a conversation/meeting where the book's ideas matter |
| P2 | Deep-Dive Studier | Wants depth on specific chapters | (a) drilling a hard chapter (e.g., prospect theory) right after reading it; (b) revisiting a book finished weeks ago for selective depth |

> Both personas are the same single user; treating usage contexts as personas keeps the M/F/S matrix meaningful.

---

## Journeys

| ID | Journey | Scope used | Source |
|---|---|---|---|
| J1 | First quiz session on a freshly-finished book | All Summaries | Doc §"User Journeys → Primary" |
| J2 | Multiple Chapters depth pass | Multiple Chapters (full content) | Doc §"Alternate Journeys → Going deep on specific chapters" |
| J3 | Return visit days/weeks later | Either | Doc §"Primary step 13" + §"Empty States — Returning visit" |

---

## M/F/S Matrix

### J1 — First quiz, All Summaries

**Best-fit personas:** P1a (primary), P1b, P2b. **Misfit:** P2a (would prefer J2; risk of picking J1 by accident).

**Motivation**
- *Job to do:* breadth check — "did the whole arc land?" (P1a) or "be quiz-ready for a conversation about X" (P1b).
- *Importance:* high for P1b (deadline-adjacent, embarrassment cost); moderate for P1a (validate reading-time investment).
- *Urgency:* low for P1a; high for P1b.
- *Alternatives:* re-read summary (passive, weak); AI Chat tab in reader (user must drive); ChatGPT/Claude.ai (no book grounding). Quiz is the only **agent-driven probe** of this book's content. Motivation is strong.
- *Consequences of inaction:* P1a — slow erosion of recall. P1b — possibly going into a meeting under-prepared.

**Friction**
- *Will the user understand the product?* Empty state must explain what each scope feeds the agent. Currently the doc says "All Summaries (book + section summaries)" — copy is fine for the doc, but the user-facing string needs the same disambiguation. **Finding F1.**
- *Decision complexity at start:* two scopes is the right number, but for P1b ("prep me for the meeting on Z") neither scope targets a specific topic. Open Q #6 (session theme) is the missing dimension here. **Finding F2.**
- *Difficulty initiating:* tab is the 6th of 6 — visible, but no progressive disclosure. New-session friction is mostly the **first-question latency**. The `LLMProvider` waits for full subprocess output (no streaming per code research); first question may take 5–15 s on a blank screen. Doc §"Why now" notes "latency on first question matters less" — but for a first-time user with no trust, latency is doubt. **Finding F3 (Must).**
- *Cost of wrong decision:* low — user can switch scope mid-session per D2/Alternate Journey.
- *What else is going on:* P1a has 15 min, can tolerate a 10s wait once they trust the loop, but the *first* time is the trust-building moment.
- *What do they stand to lose?* time, mostly. Pride if the agent makes them look bad on something they thought they understood — but D15 (override) and D12 (self-assessment as authoritative) buffer this.
- *Inconsistent with habits?* Self-assessment buttons (Got it/Partial/Missed) are an unfamiliar interaction pattern after each feedback turn. First-time use needs a one-line tooltip or microcopy. **Finding F4.**
- *Cognitive load before action:* low if scope copy is clear (F1).

**Satisfaction**
- *Fulfilled the job?* Hinges on question quality (Bloom variety, grounding). Goals already track this; no incremental finding here.
- *Lived up to expectations?* For P1a, yes if first 2–3 questions hit non-trivial concepts. For P1b, **no** if the questions don't touch the topic they care about — Finding F2 (theme input) hits here too.
- *Happy hormones?* The first "huh, hadn't thought of that" moment. Cited in doc §"Satisfaction Signals." No new finding.
- *Reassuring?* The self-assessment tally + non-judgmental qualitative feedback (D4, D12) are reassuring **once visible**. First session needs to surface the tally early (turn 2 onward, per the requirements goal). No new finding — already captured.
- *Felt smart?* Risk: if the agent's questions skew to fact recall ("what year was X published"), the user feels patronized, not stretched. Goals already gate this.
- *Skip affordance gap:* If the agent asks an irrelevant question, user can only answer or stop. No skip. P1b is most affected (low patience, focused goal). **Finding F5 (Should).**

### J2 — Multiple Chapters depth pass

**Best-fit personas:** P2a (primary), P2b, P1a (1–2 chapter focused mode).

**Motivation**
- *Job to do:* drill specific concepts at full depth, beyond what summaries compress away.
- *Importance:* high — user has chosen the harder path deliberately.
- *Urgency:* moderate (P2a, while it's fresh) to low (P2b, refresher).
- *Alternatives:* re-read the chapter (passive); take own notes (high-effort). Quiz is again the only agent-driven probe.

**Friction**
- *Will the user understand?* The chapter-picker UX is **not specified** in the requirements. Multi-select with checkboxes? Searchable list? Filter by section type (excluding glossary/appendix)? **Finding F6 (Should).**
- *Length cap visibility:* doc says "Inline warning before Start: 'Selected chapters total ~X tokens; cap is Y. Pick fewer chapters or switch to All Summaries.'" Good. But missing: **which chapter pushed it over** and a running counter while picking. Without this, the user gets a yes/no answer with no actionable signal. **Finding F6 (extends).**
- *Decision complexity:* picking 1 chapter is fine. Picking 5–6 across a long book and learning the cap mid-pick is friction. A live total + per-chapter token count solves this.
- *Difficulty initiating:* longer prompt → longer first-question latency than J1. Same loading-state mitigation applies (F3).
- *What do they stand to lose?* effort spent picking the wrong subset; cap-rejection is annoying mid-flow.
- *Inconsistent with habits?* The "Multiple Chapters" wording implies plural — single-chapter selection should be explicitly allowed; otherwise users may feel forced to pick ≥2. **Finding F7 (Nice).**

**Satisfaction**
- *Fulfilled the job?* Strong satisfaction signal: doc explicitly notes "questions noticeably more specific (numbers, examples, edge cases the summary compressed away)." This is the differentiated value of J2 over J1.
- *Felt smart?* Highest among all journeys when it works — full-content questions can probe Apply / Analyze levels naturally.

### J3 — Return visit days/weeks later

**Best-fit personas:** P1a, P2b (revisits common). All personas can hit this.

**Motivation**
- *Job to do:* continue a comprehension thread; verify retention; cover gaps from prior session.
- *Importance:* moderate — by definition, the user came back, so trust is established.
- *Alternatives:* none meaningful — past Q&A is locked in this tab.

**Friction**
- *Will the user understand?* Past Q&A panel is collapsible (D10) — good. But for a heavily-quizzed book (e.g., 50+ questions over months), pagination/grouping is unspecified. Scrolling 50 turns is overwhelming. **Finding F8 (Nice).**
- *Scope memory:* doc doesn't specify whether the tab remembers the last-used scope per book. Defaulting to "All Summaries" every time forces a re-decision the user may have already made. **Finding F9 (Should).**
- *Cumulative progress visibility:* D12 introduces a *per-session* tally. Cross-session lifetime tally ("23 questions over 3 sessions; 14 Got it / 6 Partial / 3 Missed") is the thing that compounds the "I really know this book" feel. Without it, each session feels disconnected. **Finding F10 (Should).**
- *Dedup transparency:* D13 says older questions get summarized as "themes already covered" — invisible to the user. If the user wants to revisit a theme deliberately, they can't tell what's been covered. **Finding F11 (Nice).**
- *Dedup drift handling:* doc mentions "Already asked" link on questions when LLM dedup fails (low-probability case). First time the user encounters this affordance, they may not understand what it means. Microcopy needed. **Finding F12 (Nice).**

**Satisfaction**
- *Reassuring?* Yes — past Q&A panel + dedup deliver the "the agent remembers me" feeling. Strong.
- *Raised self-esteem?* Cross-session tally (F10) is the lever here. Per-session tally only resets each visit — emotional payoff is muted without aggregation.
- *Felt smart?* Compound learning across sessions is the J3 satisfaction signal — currently not surfaced.

### Cross-cutting (all journeys)

- **"Explain this question" affordance:** if the agent uses a term the user doesn't recognize, they can't ask for clarification before answering. Forces a guess or a stop. **Finding F13 (Should).**
- **No streaming = first-impression risk:** F3 covers J1; same applies on every cold start. Loading-state copy is a near-zero-cost win.
- **Self-assessment ambiguity for "Got it"** when the user partially nailed it but the agent flagged a real gap: do they click Got it (their feel) or Partial (the agent's call)? D12 says the user click is authoritative — **but** the doc doesn't tell the user that explicitly. **Finding F14 (Nice).**

---

## Recommendations

### Must — Critical friction or motivation gaps

| ID | Severity | Recommendation | Affected | Effort |
|---|---|---|---|---|
| R1 | Must | Add an explicit loading state with copy ("Reading the book to draft your question…") for the first-question delay on cold start. Without streaming, blank screens read as "broken." | J1, J2 first turn (all personas) | Low |
| R2 | Must | Make the scope-picker user-facing copy disambiguate what each scope feeds the agent: "All Summaries (book summary + every chapter summary)" vs "Multiple Chapters (full text of selected chapters; ~N tokens)." Don't rely on the doc's terms verbatim. | J1, J2 entry (all personas) | Low |
| R3 | Must | Decide and document: is there a "Skip this question" affordance, or is its absence intentional? Without it, an irrelevant or confusing question forces a stop or a guess that pollutes dedup history. P1b (deadline-adjacent prep) feels this most. | All journeys | Low (decision); Low–Med (UI) |

### Should — Significant UX improvements worth the effort

| ID | Severity | Recommendation | Affected | Effort |
|---|---|---|---|---|
| R4 | Should | Promote Open Q #6 (session theme freeform input) to a v1 feature *or* explicitly defer with a one-line note. P1b ("prep for the meeting on prospect theory") has no scoping handle without it; All Summaries is too broad and Multiple Chapters is the wrong axis. | J1 P1b (high stakes) | Low |
| R5 | Should | Specify the chapter-picker UX for J2: multi-select with a live token-count total, per-chapter token count, and "this chapter would push you over the cap" highlighting. The current spec gives a yes/no rejection with no signal on what to drop. | J2 entry (P2a, P2b) | Med |
| R6 | Should | First-session onboarding microcopy: one-line tooltips on the three self-assessment buttons (especially "your click is authoritative — overrides the agent") and a one-liner on the question pane noting the agent mixes MCQ and open-ended. | J1 first turn | Low |
| R7 | Should | Remember the last-used scope per book between sessions. P2b (revisiting weeks later) shouldn't have to re-pick "Multiple Chapters → these chapters" if that was their last setup. | J3 entry | Low |
| R8 | Should | Add a cross-session lifetime tally to the tab header (e.g., "Lifetime: 23 Q · 14 Got it / 6 Partial / 3 Missed across 3 sessions"). Per-session tally already in D12; lifetime aggregation is the satisfaction lever for J3. | J3 satisfaction | Med |
| R9 | Should | "Explain this question" affordance — let the user ask the agent to clarify a confusing question (term, scope, intent) without committing an answer. Avoids forced-guess pollution of dedup. | All journeys | Med |

### Nice-to-Have — Polish

| ID | Severity | Recommendation | Affected | Effort |
|---|---|---|---|---|
| R10 | Nice | Surface the "themes already covered" summary line from D13 to the user, not just the prompt. Lets the user deliberately revisit a theme that's been compacted into the summary. | J3 transparency | Low |
| R11 | Nice | First-time "Already asked" microcopy: when the affordance first becomes visible, a one-line tooltip explaining its purpose and what clicking it does. | J3 dedup-drift case | Low |
| R12 | Nice | Past Q&A panel grouping/pagination once history exceeds ~20 turns: group by session with collapsible session headers; default to most-recent session expanded. | J3 with heavy history | Med |
| R13 | Nice | Explicitly allow single-chapter selection in the Multiple Chapters scope (and reflect in the UI label, e.g., "Specific Chapters") so users don't feel forced to pick ≥2. | J2 entry | Low |
| R14 | Nice | Make the self-assessment-authority rule visible: a small "your call beats the agent's" microcopy near the buttons, especially during onboarding. | All journeys | Low |

---

## Notes

- This is a single-user personal tool. "Adoption" is binary — the user either reaches for the Quiz tab or doesn't. Most findings target the **first 2–3 sessions** where trust is built.
- The doc is genuinely tight. The Must-tier findings are mostly first-impression mitigations, not structural rework.
- No PSYCH scoring (text-only artifact). For grounded scoring, run `/msf-wf` after wireframes exist.
