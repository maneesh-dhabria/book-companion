# AI Comprehension Quiz — Requirements

**Date:** 2026-05-08
**Last updated:** 2026-05-08 (Loop 2 — MSF dispositions applied)
**Status:** Approved
**Tier:** 3 — Feature

## Problem

Reading a non-fiction book and getting a summary is not the same as **understanding** it. A user can finish a book, even read its summary twice, and still fail to recall key concepts a week later or apply them in a conversation. Book Companion currently produces high-quality summaries but offers no way for the reader to **test whether the ideas actually landed**. Without an active recall loop, the library becomes a graveyard of consumed-but-not-internalized content.

### Who experiences this?

The single user of this personal tool — a non-fiction reader who imports books to extract durable knowledge. They've already invested in summarization and search; the missing piece is a **comprehension check**. Context: the user has just finished reading a book (or a chapter they want to go deep on) and wants the system to interrogate them, the way a study partner or tutor would.

### Why now?

- Summaries and section content are already in the database; the raw material for question generation exists.
- The Claude Code / Codex CLI subprocess pattern (`LLMProvider`) is already wired and battle-tested for summarization and the AI Chat tab — the same plumbing can drive Q&A generation.
- The user has noticed that re-reading a summary doesn't move comprehension — only recall + feedback does. This is the next obvious upgrade after the summarization pipeline matured (v1.6).

## Goals & Non-Goals

> Goals are observable user outcomes; engineering acceptance criteria belong in `02_spec.md`.

### Goals

- **A user can start a quiz session for any book** from that book's overview page and get questions about its content — measured by: at least one quiz session is started per actively-read book within a week of finishing it.
- **The agent varies question shape (MCQ + open-ended) and depth** so the user is challenged across Bloom levels, not just on fact recall — measured by: spot-check sample of generated questions shows ≥30% above "Remember" level (Understand, Apply, Analyze, Evaluate).
- **The agent does not repeat questions** the user has already been asked for the same book — measured by: zero duplicate question stems across all sessions for any single book in user testing.
- **Open-ended answers receive useful qualitative feedback** that the user can learn from — measured by: feedback text references at least one concept from the source content and identifies what (if anything) was missing.
- **The user has a visible sense of how the session is going** without numeric scoring — measured by: a per-session self-assessment tally (Got it / Partial / Missed) is visible in the tab header from the second question onward.
- **Cumulative learning compounds across sessions** — measured by: a per-book lifetime tally aggregating self-assessments across all prior sessions is visible whenever the Quiz tab is open for a book with prior history.
- **The user can choose between two scopes** before each session: quiz over all summaries (book + every chapter summary) or go deep on a chosen subset of chapters using full chapter content — measured by: both scopes are reachable in ≤2 clicks from the Quiz tab.
- **The user can optionally name a theme** for a session (e.g., "prospect theory") so the agent biases questions toward that topic — measured by: when a theme is provided, ≥70% of questions in the session reference the theme or directly adjacent concepts.

### Non-Goals (explicit scope cuts)

- **NOT building a spaced-repetition card system** (Anki/FSRS-style daily review queue) in this iteration — because the immediate need is post-read comprehension testing, not long-term retention curves. Revisit after we see usage signal.
- **NOT scoring open-ended answers numerically** (no 1–5 grade, no "you got 7/10") — because the user wants qualitative feedback only; numeric grading invites gameability and adds LLM-judge bias for marginal value.
- **NOT building a Socratic / coach mode** — because v1 stays simple (direct Q→A→feedback loop). Research shows Socratic prompting can hurt high performers; revisit only with clear signal.
- **NOT exposing the quiz on the Reader (BookDetailView) sidebar** — because the user explicitly wants this anchored to the book overview page, where post-read reflection happens, not the reading flow itself.
- **NOT supporting multi-user accounts, sharing, or leaderboards** — because this is a personal tool.
- **NOT generating questions from book metadata, annotations, or external context** in v1 — because scope is restricted to summaries and chapter content. Defer.
- **NOT streaming question text token-by-token** — because the existing `LLMProvider` pattern waits for full subprocess output and adding streaming is a stretch goal. The cold-start latency is mitigated with a loading state (D16), not architecture change.

## User Experience Analysis

### Motivation

- **Job to be done:** "Help me check whether I actually understood this book — quiz me, tell me what I got wrong, and don't ask me the same thing twice."
- **Importance/Urgency:** Important but not urgent. The user usually triggers quizzing in a deliberate, reflective moment — after finishing a book or before a conversation/meeting where the ideas matter. Latency on first question matters less than question quality, but blank-screen waits during cold-start undermine first-impression trust.
- **Alternatives the user has today:**
  - Re-read the summary (passive — doesn't reveal blind spots).
  - Talk to the existing AI Chat tab in the reader (open-ended dialogue, but the user has to drive — the agent doesn't probe).
  - Talk to ChatGPT/Claude.ai about the book (lacks book-specific grounding; hallucinates).
  Quiz is the only option where the **agent is the interrogator** and is grounded in *this* book's actual content.

### Friction Points

| Friction Point | Cause | Mitigation |
|---|---|---|
| "I don't know where to start a quiz." | New surface; user might miss the tab. | Quiz is a top-level tab on the book overview page, visually equal to Summary/Sections/etc. Empty state explains scope choice in one screen. |
| "It just keeps asking me trivia." | LLM defaults to fact recall. | Prompt explicitly requests Bloom-level variety; system prompt names higher-order verbs (Apply, Analyze, Evaluate). |
| "It asked me the same thing again." | No dedup. | Persist all asked-question stems per book; pass recent N stems + themed summary of older to the generation prompt as a "do not ask again" list (D13). |
| "It hallucinated a fact that's not in the book." | LLM grounding drift. | Prompt instructs the agent to ground every question in a specific snippet of the provided content. Surface the source snippet with each question (citation), per D14's shape-conditional rules. |
| "I gave a half-right open-ended answer and the feedback was vague." | Qualitative-only feedback can be wishy-washy. | Feedback prompt template demands: (a) what was correct, (b) what was missing, (c) the concept's actual answer per the source. |
| "I have no idea how I'm doing in this session." | No score, no progress signal — a known motivation-collapse failure mode. | One-click self-assessment after each feedback turn (Got it / Partial / Missed); per-session running tally + per-book lifetime tally shown in the tab header. Qualitative, not numeric. |
| "It's MCQ — and the citation chip on the question already tells me the answer." | Citation visibility leaks the answer for fact-recall MCQs. | Citation appears **after** the user answers for MCQ; appears **with** the question for open-ended (where it helps the user know which content to draw from). |
| "I want to go deeper on chapter 7 but the agent keeps asking surface questions about the whole book." | Scope confusion. | Two explicit scopes: **All Summaries** vs **Specific Chapters (full content)**. User picks before starting and can switch mid-session. |
| "I closed the tab and lost my progress." | Session state ephemeral. | Quiz history persists per book. Re-opening the tab shows past Q&A and the "next question" continues from where the asked-question dedup left off. |
| "There's no LLM CLI installed." | Tool depends on Claude/Codex on `$PATH`. | Tab disabled with the same banner pattern used by Summarize/Eval features when no provider is detected (CLAUDE.md gotcha #6). |
| "The book has no summaries yet." | Quiz needs source content. | Empty state: "Generate summaries first" with link to the existing summarize flow. For Specific-Chapters scope, full content is enough — gate accordingly. |
| "The first question takes forever and I'm staring at a blank screen." | LLM subprocess waits for full output (no streaming) — cold-start can be 5–15s. Blank screens read as broken. | Explicit loading state with copy that signals work in progress (D16) — e.g., "Reading the book to draft your question…". |
| "I don't know what 'All Summaries' actually feeds the agent." | Generic scope labels under-explain what content the agent sees. | User-facing scope-picker copy names what each scope feeds the agent: "All Summaries (book summary + every chapter summary)" vs "Specific Chapters (full text of selected chapters)" (D17). |
| "This question is irrelevant or confusing — I don't want to answer but I don't want to stop the session either." | No skip affordance forces user to answer or quit. | Per-turn **Skip** control ends the turn without recording an answer; skipped questions are NOT added to dedup history so they can return later (D18). |
| "I want to be quizzed specifically on prospect theory, not the whole book." | Scope alone is too coarse for goal-oriented prep. | Optional one-line **theme** input on session start; passed to the prompt as a soft topical constraint (D19). |
| "I picked too many chapters and I don't know which one tipped me over." | Cap rejection without signal is annoying mid-flow. | Chapter picker shows a running **% of token budget consumed** bar (Claude-Code-style); user sees the budget fill as they pick and can deselect to free room (D20). |
| "What do these three buttons after feedback even do?" | Self-assessment buttons are an unfamiliar pattern; semantics not obvious on first encounter. | First-session onboarding microcopy on the buttons + a one-liner that the agent will mix MCQ and open-ended (D21). |
| "I forgot which scope I last used for this book." | Defaulting to "All Summaries" each visit forces re-decision. | Tab remembers the last-used scope (and chapter selection if Specific Chapters) per book; new sessions default to that (D22). |
| "Each session feels disconnected from the last one." | Per-session tally resets each visit; no cross-session aggregation. | Cross-session **lifetime tally** in the tab header for any book with prior history (D23). |
| "I don't understand the question — what does the agent mean by 'X'?" | A confusing term or unclear scope forces a guess that pollutes dedup. | Per-question **Explain** control: agent clarifies the question (term, scope, intent) without revealing the answer; user still has to answer (D24). |
| "I want to go back to a topic the agent told me it 'already covered' weeks ago." | D13's themed-summary rollup is invisible to the user. | Past-Q&A panel shows a "Themes covered" section reflecting the agent-summarized themes; user can deliberately revisit (D25). |
| "The agent asked something it should have known I already covered." | LLM dedup drift; user sees an "Already asked" link with no context on what it does. | First time the link appears in a session, a one-line tooltip explains what clicking it does. |
| "My past Q&A panel is overwhelming — 60+ turns." | Flat history list does not scale. | Past-Q&A panel groups by session with collapsible session headers; default expansion = most-recent session only (D26). |
| "Did the agent's verdict overrule my self-assessment?" | Override and self-assessment-authority rules are non-obvious. | Persistent (not just first-session) microcopy near the self-assessment buttons makes it explicit that the user's click is authoritative. |

### Satisfaction Signals

- The user finishes a session and can articulate at least one thing they didn't realize they'd missed.
- The user comes back to the same book's quiz tab a second time — i.e., they trusted the loop enough to return.
- After a session, the user types something like "good question, hadn't thought about that" — direct evidence the agent is provoking actual thinking, not parroting summaries.
- The user voluntarily switches scope from "All Summaries" to "Specific Chapters" — meaning the surface-level pass left them wanting depth.
- The lifetime tally for a book trends toward more "Got it" over sessions — visible compound progress.

## Solution Direction

A **Quiz tab** on `BookOverviewView`, sibling to the existing `overview / summary / sections / audio / annotations` tabs. The tab is a **chat-style surface** where the agent asks one question at a time; the user answers; the agent gives feedback; loop continues until the user stops.

User flow at the behavior level (not architecture):

```
[ Quiz tab opens ]
        │
        ▼
  Lifetime tally (if any) + Past Q&A panel (collapsible, grouped by session)
        │
        ▼
  Scope picker:  ( ) All Summaries
                 ( ) Specific Chapters → [ pick 1+ chapters ]
                                           [▓▓▓▓▓░░░░] 52% of budget used
  Optional theme input: [ "focus on prospect theory" ]
  (Defaults reflect last-used scope for this book.)
        │
        ▼
  [ Start Quiz ]
        │
        ▼
  ─── Loading: "Reading the book to draft your question…" ──
        │
        ▼
┌─────────────────────────────────────────────┐
│  Agent asks Question N                       │
│   - shape: MCQ or open-ended (agent picks)   │
│   - source citation per D14 rules            │
│   - [Explain]   ← clarify w/o revealing ans  │
│                                              │
│  User answers (typed text or option click)   │
│  OR clicks [Skip]   (not added to dedup)     │
│                                              │
│  Agent shows qualitative feedback:           │
│   - what was correct                         │
│   - what was missing                         │
│   - the actual answer with reference         │
│                                              │
│  Self-assessment: [ Got it ] [ Partial ]     │
│                   [ Missed ]   (your call    │
│                    is authoritative)         │
│                                              │
│  [ Next Question ]   [ Stop ]   [ Override ] │
└─────────────────────────────────────────────┘
        │
        ▼
  Session continues. Asked questions accumulate in DB,
  feeding the dedup list. Per-session + lifetime tallies update.
```

Question generation uses the existing `LLMProvider` subprocess pattern (`ClaudeCodeCLIProvider` / `CodexCLIProvider`), invoked by a new `QuizService` that mirrors `AIThreadService`. Asked-question stems for the book are passed into every generation prompt as a "do not repeat" constraint.

## User Journeys

### Primary Journey (Happy Path)

1. **User finishes reading** "Thinking, Fast and Slow" and wants to test their grasp.
2. They open the book on the library page → land on `BookOverviewView`.
3. They click the **Quiz** tab (sixth in the top tab bar). The empty state explains: "Quiz me on this book. Pick a scope to start." Two options: *All Summaries (book + every chapter summary)* (default) and *Specific Chapters (full text of selected chapters)*. An optional theme field is shown.
4. User leaves *All Summaries* selected, leaves the theme field blank, and clicks **Start Quiz**.
5. A loading state appears: "Reading the book to draft your question…". After ~8 s, the agent posts: *"System 1 vs System 2 — give me one example, from the book, of System 1 making a snap judgment that System 2 would override on reflection."* (open-ended, with a small "Source: Chapter 1" citation chip — pre-answer per D14).
6. User types an answer.
7. Agent responds with qualitative feedback: what was right, what they missed (citing the priming/anchoring example), and the concept the book actually uses.
8. User clicks **Partial** in the self-assessment, then **Next Question**. The header counter ticks to "Session: 1 partial · Lifetime: 1 partial".
9. Agent asks an MCQ on a different concept (e.g., loss aversion), with 4 options. No citation chip yet — it would leak the answer.
10. User picks. Agent confirms correct/incorrect and reveals the source citation alongside the explanation. User clicks **Got it**.
11. The next question feels off-topic. User clicks **Skip** — turn ends without an answer; the question is not added to dedup history. Agent generates the next question.
12. User does this for ~10 questions, then clicks **Stop**. The session header reads: "Session: 6 Got it · 3 Partial · 1 Missed (1 skipped) · Lifetime: same".
13. Session is saved with self-assessment tallies. Asked-question stems (excluding skipped) are persisted under this book. The tab remembers "All Summaries" as the last-used scope.
14. Three days later, user reopens the Quiz tab → sees past Q&A history grouped by session (most recent expanded) + lifetime tally → scope picker pre-selects *All Summaries* → starts a new session → the agent does **not** repeat any prior questions.

### Alternate Journeys

**Going deep on specific chapters.** After a first all-summaries pass, user picks **Specific Chapters**. The chapter picker shows a list of all chapters; as the user checks chapters 6–8, a budget bar fills to ~58%. They could add chapter 9 (would push to ~76%) but stop at 8. They optionally type the theme "prospect theory" and click **Start Quiz**. The agent now generates questions grounded in the **full content** of chapters 6–8 with a topical bias — questions are noticeably more specific (numbers, examples, edge cases the summary compressed away).

**Single-chapter selection.** Specific Chapters allows one chapter. User picks just chapter 4; budget bar shows ~14%. Quiz proceeds with that scope.

**Mid-session scope change.** User starts in *All Summaries*, realizes they want depth on chapter 4. They click a "Change scope" control, switch to *Specific Chapters → Chapter 4*, and the next generation uses the new scope. Asked-question history continues to accumulate against the same per-book pool.

**Explain a confusing question.** Agent asks: *"How does the affect heuristic interact with the availability cascade in policy debate?"* User isn't sure what "availability cascade" means here. They click **Explain**. The agent clarifies the term and the scope of the question without revealing the answer. User then types an answer; flow continues normally.

**Theme-driven session.** User is prepping for a meeting on a specific topic. They open the Quiz tab, type "endowment effect" into the theme field, leave *All Summaries* selected, and click **Start**. The agent biases its questions toward endowment-effect-adjacent material across the book.

**Override unfair feedback.** Agent says the user's open-ended answer "missed the role of cognitive ease" — but the user's answer actually addressed it. User clicks **Override** and types a one-line note ("I did mention cognitive ease"). The note is appended to the feedback turn; the original agent feedback **stays visible** (not deleted); the turn is flagged in history so the disagreement is preserved. No re-grading happens — the user's self-assessment click (Got it / Partial / Missed) is the authoritative signal for the session and lifetime tallies. A small persistent microcopy near the buttons reinforces this.

### Error Journeys

- **No LLM provider on PATH.** Quiz tab renders but the action area shows the standard "No LLM provider detected — install Claude Code or Codex CLI" banner (pattern reused from existing summarize / eval features). Past history (if any) remains viewable.
- **All-Summaries scope but no summaries exist.** Empty state shows "Generate summaries first" with a CTA linking to the summarize action. Specific-Chapters scope is still offered (uses full content).
- **Specific Chapters: budget bar at 100%.** Adding another chapter is blocked inline; the would-be addition is shown greyed-out with "Would exceed budget — deselect a chapter to add." No silent truncation.
- **LLM subprocess fails or returns malformed JSON.** Toast: "Couldn't generate a question — try again." The failed attempt is not persisted as an asked-question. User can retry without losing session state. The loading state ends; the previous question state (if any) is preserved.
- **Agent generates a question that's clearly already-asked despite dedup** (low-probability LLM drift). User can click a small "Already asked" link on the question to discard it; first time the link is visible in a session, a one-line tooltip explains what clicking it does. The signal also appends a stronger negative example to the next prompt.
- **User's typed answer is empty.** Submit button disabled until at least one character is entered for open-ended; for MCQ, an option must be selected. Skip remains available.
- **User clicks Explain repeatedly.** Each Explain re-prompts the agent for clarification on the same question; no answer-leakage check is bypassed. (No hard cap in v1; revisit if abuse is observed.)
- **Book deletion or re-import while a session is open.** Session is gracefully ended; if the book is re-imported, prior asked-question history persists (keyed by book id) — same persistence semantics as summaries.

### Empty States & Edge Cases

| Scenario | Condition | Expected Behavior |
|---|---|---|
| First visit to Quiz tab for a book | No `QuizSession` rows exist for this book | Show scope picker + theme field + "Start Quiz" CTA. No "Past Q&A" panel. No lifetime tally. Onboarding microcopy on self-assessment buttons + question-mix hint shown on the first question of the first session. |
| Returning visit | At least one prior `QuizSession` exists | Show lifetime tally + collapsible "Past Q&A" panel (grouped by session, most recent expanded) above scope picker. Scope picker pre-selects last-used scope. |
| No LLM provider | `detect_llm_provider() is None` | Tab shows banner; scope picker disabled; past history + lifetime tally still viewable. |
| Book has zero summaries AND user picks All-Summaries | `book.default_summary` is null AND no section summaries | Inline gating: "Generate summaries first." Specific-Chapters path remains enabled. |
| Specific Chapters: nothing selected | User clicks Start without any chapter checked | Start button disabled; helper text "Pick at least one chapter." |
| Specific Chapters: selection exceeds budget | Sum exceeds cap | Adding more chapters is blocked inline; existing selection retained. |
| User clicks Stop mid-question (after Q, before answering) | Last turn is a posed question with no answer | Session ends; the unanswered question is **not** added to asked-history (so it can be re-generated next time). |
| User clicks Skip on a question | Skip pressed instead of answering | Turn ends without answer; question is **not** added to dedup history. Self-assessment is not requested. Tally records "(N skipped)" alongside the main counts. |
| User reads asked-question history | Browsing past turns | Read-only render of question + answer + feedback + self-assessment + (if any) override note; show timestamp and scope used. Skipped turns appear with a "skipped" badge. |
| Themes-covered panel | Past-Q&A view | Shows the agent-summarized themes from D13 rollup; user can click a theme to seed a new session's theme field. |
| Concurrent sessions for the same book on different devices | Theoretical — single user but multi-device | Treat newer session's writes as authoritative; no merge conflict UI. (Personal tool — acceptable.) |

## Design Decisions

| # | Decision | Options Considered | Rationale |
|---|---|---|---|
| D1 | Quiz lives as a 6th top-level tab on `BookOverviewView`, not in the reader sidebar | (a) reader sidebar (sibling to AI Chat), (b) book overview top-tab, (c) both surfaces, (d) modal from Summary tab | User explicitly wants quizzing anchored to the post-read reflection moment. The reader sidebar is for in-flow assistance; the overview page is for review. Surface parity with Summary/Sections matches information architecture. Single surface keeps scope tight for v1. |
| D2 | Two scopes only: **All Summaries** vs **Specific Chapters (full content)** (renamed from "Multiple Chapters" — single chapter allowed) | (a) single-section picker, (b) book-summary only, (c) all-summaries, (d) specific-chapters full content, (e) all of the above | User chose the two-mode shape directly. "All Summaries" covers the breadth pass; "Specific Chapters" covers depth (one or more chapters). Renamed from "Multiple Chapters" to remove the implication that ≥2 chapters are required. |
| D3 | Question shape mix: MCQ + open-ended, **agent picks per turn** | (a) user toggles per session, (b) MCQ only, (c) open-ended only, (d) agent picks | Agent variety is more interesting and matches NotebookLM precedent. Concept type drives shape (facts → MCQ; synthesis → open). User can't predict, which forces engagement. |
| D4 | Open-ended answers get **qualitative feedback only**, no numeric score | (a) LLM-judge with 1–5 score, (b) qualitative only, (c) model answer + self-grade | User chose qualitative-only. Avoids LLM-judge bias and gameability. Feedback must still be structured (correct / missing / actual) so it's useful — vagueness is the failure mode. |
| D5 | Asked-question history is **persistent per book** across sessions | (a) ephemeral per-session, (b) per-book persistent, (c) per-book + per-scope | Persistence matches the user's stated need ("don't ask the same thing again"). Single per-book pool is simpler than per-scope and reflects the reality that the underlying concepts overlap across scopes. |
| D6 | Dedup mechanism: pass asked-question stems to the generation prompt as a "do not repeat" list | (a) pass to prompt, (b) embedding similarity dedup at runtime, (c) both | User explicitly asked for "pass to prompt." Embedding-based dedup is more robust but adds an embedding fetch and a similarity step per generation. Defer to v2 if the prompt-list approach starts missing semantic dupes. |
| D7 | Session model: open-ended chat, **questions keep coming until user stops** | (a) fixed N-question session, (b) chat-style continuous, (c) both modes | User chose chat-style. Matches the existing AI Chat metaphor and the "show them one by one" framing. Fixed-N adds end-of-session ceremony but doesn't fit the personal-reflection use case. |
| D8 | Direct quiz mode only; no Socratic / coach mode in v1 | (a) direct only, (b) Socratic only, (c) toggle | User chose direct-only. Research note: Socratic mode can degrade comprehension for high performers (Frontiers in Education, 2025). Revisit only on signal. |
| D9 | LLM provider: reuse existing auto-detected provider; no new subprocess pattern | (a) reuse `LLMProvider` ABC, (b) new streaming-only provider | The summarize and AI-chat features already work this way; building a parallel pattern is overhead without benefit. Streaming token-by-token is a stretch goal — single-question latency is acceptable and is mitigated with a loading state (D16). |
| D10 | Quiz history is shown in the same tab (collapsible "Past Q&A" panel), not a separate route | (a) inline in tab, (b) `/books/:id/quiz/history` route, (c) sidebar drawer | Inline keeps the surface focused and discoverable. Separate route adds navigation cost for a single-user tool. |
| D11 | If the user closes the tab mid-question (before answering), the unanswered question is **not** added to dedup history | (a) drop, (b) keep | Allowing re-generation is the kinder default — the user might reopen the tab fresh and want the same question they didn't get to. |
| D12 | One-click self-assessment after every feedback turn: **Got it / Partial / Missed**; per-session running tally visible in the tab header. The user's click is authoritative (overrides the agent's feedback for tally purposes). | (a) numeric score (excluded by D4), (b) qualitative-only with no signal, (c) one-click self-assessment | Restores a progress signal without reintroducing scoring. Self-assessment is authoritative (cheaper and less biased than LLM-judging the user's answer). Tally seeds the v2 retention layer if/when SR is added. |
| D13 | Dedup mechanism caps at the most-recent ~50 asked-question stems (verbatim) plus an agent-summarized "themes already covered" line for older ones | (a) pass everything (breaks at scale), (b) recent N only (loses older coverage), (c) hybrid: recent N verbatim + themed summary of older | Pure recent-N drops semantic awareness of older questions; a themed summary line is cheap, keeps the dedup signal alive at scale, and is surfaced to the user via D25. The exact N is set in `02_spec.md` based on prompt budget. |
| D14 | Source citation appears **after** the user answers for MCQ; **with** the question for open-ended | (a) always pre-answer, (b) always post-answer, (c) shape-conditional | MCQ pre-citation leaks the answer for any fact-grounded question. Open-ended pre-citation tells the user which content to draw from without giving the answer (the synthesis is still on them). Different shapes need different visibility rules. |
| D15 | **Override** appends a free-text user note to the feedback turn; the original agent feedback stays visible; the turn is flagged in history. Override does NOT change the self-assessment tally. | (a) replace feedback with note, (b) append note + flag, (c) defer | Preserving the disagreement (rather than deleting it) is the right call for a personal tool — the user may want to revisit "why I disagreed with the agent here" later. Self-assessment authority stays user-driven (D12). |
| D16 | **Cold-start loading state:** the Quiz UI shows an explicit loading state with copy ("Reading the book to draft your question…") whenever a generation request is in flight. Triggers on first question of every session and on every "Next Question" click. | (a) silent spinner only, (b) copy + spinner, (c) skeleton question shape | Without streaming, generation may take 5–15 s on cold start. A blank screen reads as broken; a labeled loading state preserves trust and explains the wait. |
| D17 | **Scope-picker disambiguation copy:** user-facing labels read "All Summaries (book summary + every chapter summary)" and "Specific Chapters (full text of selected chapters)". Helper text under each option spells out what the agent receives. | (a) terse labels, (b) labels + helper text, (c) tooltip-only | Generic scope labels under-explain what the agent sees and lead to wrong-mode selections. Inline disambiguation is cheap and prevents silent misuse. |
| D18 | **Skip affordance:** every question turn has a Skip control alongside Submit. Skipping ends the turn without recording an answer; **skipped questions are NOT added to dedup history** (so they may return in a later turn). Self-assessment is not requested for skipped turns. | (a) no skip (force answer or stop), (b) skip + add to dedup, (c) skip + retain in pool | Forcing a guess on irrelevant questions pollutes dedup with low-quality signals; forcing a stop is a too-blunt exit. Retaining skipped questions in the pool means a later turn (with different agent context) may surface them again productively. |
| D19 | **Optional session theme:** session-start UI includes a single freeform text field ("focus on prospect theory"). When non-empty, the value is passed to the generation prompt as a soft topical constraint. | (a) no theme input (Open Q from Loop 1), (b) optional freeform field, (c) tag-based picker | P1b-style use cases ("prep me for the meeting on X") need a sub-scope handle that neither scope alone provides. Freeform text is the cheapest implementation; tags would require curation infrastructure. |
| D20 | **Chapter-picker UX with budget bar:** Specific Chapters scope shows a multi-select chapter list and a running **% of token budget consumed** progress bar (Claude-Code-style). Adding a chapter that would exceed 100% is blocked inline; the button shows "Would exceed budget — deselect a chapter to add." | (a) yes/no rejection on Start, (b) per-chapter token cost inline, (c) overall budget bar | Per-chapter token costs are noisy and don't help the user decide. A single budget bar is a familiar metaphor (matches Claude Code's context indicator) and gives continuous feedback during selection. |
| D21 | **First-session onboarding microcopy:** on the first session of a book, the UI shows one-liners on (a) the self-assessment buttons explaining authority, (b) the question pane noting the agent will mix MCQ and open-ended. Copy fades after the first session. | (a) no onboarding, (b) tooltip on hover, (c) inline microcopy on first session | The Got it / Partial / Missed pattern and the unannounced shape mix are unfamiliar; first-session inline microcopy avoids hover-discovery friction without permanent visual noise. |
| D22 | **Last-used-scope memory:** the Quiz tab remembers, per book, the last-used scope mode AND (if Specific Chapters) the chapter selection. New sessions default to that. | (a) always default to All Summaries, (b) remember mode only, (c) remember mode + chapter selection | Re-picking chapters on every visit is friction P2b (revisits) feels acutely. Remembering both mode and chapter selection is the kinder default; user can change in one click. |
| D23 | **Cross-session lifetime tally:** the tab header shows a per-book lifetime aggregation of self-assessments (e.g., "Lifetime: 23 Q · 14 Got it / 6 Partial / 3 Missed across 3 sessions") whenever prior history exists for the book. Per-session tally remains visible alongside. | (a) per-session only, (b) lifetime only, (c) both | Per-session tally is in-the-moment; lifetime tally is the satisfaction lever for J3. Showing both gives an immediate progress signal AND a compounding learning narrative. |
| D24 | **Explain-this-question affordance:** every question turn includes an Explain control. Clicking sends a follow-up to the agent asking it to clarify the question (term, scope, intent) WITHOUT revealing the answer. The user must still answer (or Skip). | (a) no explain (force answer/skip), (b) explain with answer-leakage guard | Forcing a guess on a confusing question pollutes dedup with low-signal answers. The leakage guard is enforced via the explain prompt template (system instruction: "explain without giving the answer"). |
| D25 | **Themes-already-covered visibility:** the past-Q&A panel includes a "Themes covered" section listing the agent-summarized themes from D13's rollup. Clicking a theme seeds the next session's theme field. | (a) internal-only (D13), (b) display-only, (c) display + click-to-seed | Surfacing the rollup gives the user transparency into what dedup considers covered AND a one-click path to deliberately revisit a theme — closing the loop with D19. |
| D26 | **Past-Q&A grouping & pagination:** the panel groups history by `QuizSession`, with collapsible per-session headers. Default: most-recent session expanded, all older sessions collapsed. | (a) flat list, (b) grouped + most-recent expanded, (c) infinite scroll | Heavily-quizzed books accumulate dozens to hundreds of turns; a flat list is overwhelming. Session grouping mirrors the natural mental model of "what did I work on each visit." |

## Success Metrics

| Metric | Baseline | Target | Measurement |
|---|---|---|---|
| Quiz tab adoption per recently-summarized book | 0 sessions | ≥1 session within 7 days of summarization completing | Count of `QuizSession` rows per book in the week after `Summary` is generated. |
| Question variety across Bloom levels | Unknown — no quizzing today | ≥30% of questions in a session are above "Remember" (Understand / Apply / Analyze / Evaluate / Create) | Manual coding of a sample of generated questions against Bloom's verbs (one-time validation, then prompt-spot-checks). |
| Question repetition rate | N/A | 0 exact-stem duplicates per book; ≤5% near-duplicate (semantic) rate flagged via spot-check | Stem-equality check across `QuizQuestion` rows for a book; spot-check 50 questions per book using embedding cosine similarity ≥0.88 as "near dupe". |
| Feedback usefulness | N/A | ≥80% of feedback turns reference at least one specific concept from the source content | Manual review of a sample. Heuristic check (is at least one source citation chip present?) as proxy. |
| Session completion (qualitative) | N/A | User reaches ≥5 questions before clicking Stop in a typical session | Count `QuizQuestion` rows per `QuizSession` (excluding skipped). Below 3 suggests friction. |
| Self-assessment recorded | N/A | ≥90% of non-skipped feedback turns receive a Got it / Partial / Missed click before the user moves to the next question | Count of feedback turns with non-null self-assessment / total non-skipped feedback turns per session. Below 70% suggests the click is friction or invisible. |
| Lifetime tally trend | N/A | For books with ≥3 sessions, share of "Got it" rises across sessions (any positive slope) | Linear regression of "Got it %" per session ordinal per book. Negative or flat slope across most books would indicate the loop isn't producing learning. |
| Theme bias on themed sessions | N/A | When a theme is provided, ≥70% of questions in the session reference the theme or directly adjacent concepts | Manual review on themed sessions. |
| Skip rate | N/A | <15% of generated questions are skipped | Skipped turns / total turns per session. >25% suggests prompt quality or scope mismatch. |
| Return rate | N/A | At least 1 in 3 books with a started session has ≥2 sessions over its lifetime | Books with `count(QuizSession) ≥ 2` / books with `count(QuizSession) ≥ 1`. |
| LLM hallucination rate | N/A | <5% of generated questions reference a fact not present in the source content | Spot-check a sample manually; require source citation in every question to make this auditable. |

## Research Sources

| Source | Type | Key Takeaway |
|---|---|---|
| `frontend/src/views/BookOverviewView.vue` | Existing code | Top-tab pattern (`overview/summary/sections/audio/annotations`); add Quiz as the 6th. `BookTab` type union extended; `setTab()` already wired for query-param sync. |
| `frontend/src/components/sidebar/AIChatTab.vue` | Existing code | Reference for chat-style UI with input + message list; we will mirror but not embed. |
| `frontend/src/stores/aiThreads.ts` and `frontend/src/api/aiThreads.ts` | Existing code | Pinia store + API client pattern to mirror as `quizSessions`. |
| `backend/app/services/summarizer/llm_provider.py` | Existing code | `LLMProvider` ABC supports `json_schema` already; reuse for structured question generation. |
| `backend/app/services/summarizer/claude_cli.py` | Existing code | `ClaudeCodeCLIProvider` reads structured output via `--json-schema`; subprocess waits for full output (no streaming). Acceptable for single-question latency in v1, mitigated by D16 loading state. |
| `backend/app/services/ai_thread_service.py` | Existing code | Service-layer pattern for LLM-backed chat features; `QuizService` will mirror this (fetch book + summaries/sections, build prompt, invoke provider, persist). |
| `backend/app/db/models.py` (`AIThread`, `AIMessage`) | Existing code | Schema template for new `QuizSession` and `QuizQuestion` tables (`book_id`, timestamps, role-equivalent fields). |
| `backend/alembic/` migration history | Existing code | Pattern: `render_as_batch=True` for SQLite ALTER TABLE; new tables added via autogenerate. |
| Claude Code context-budget bar | UI precedent | The user's preferred pattern for showing % of a token budget consumed during selection (D20). |
| NotebookLM Quizzes | External — https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-app-quizzes-flashcards/ | MCQ + short-answer mix; difficulty toggle; **citation-backed explanations** — strongest precedent for grounding. |
| Readwise Ghostreader / SR | External — https://docs.readwise.io/reader/guides/ghostreader/overview | Highlights → flashcards → daily review with half-life decay. **Out of scope for v1** but informs a v2 SR direction. |
| Anki + FSRS-6 / RemNote FSRS | External — https://faqs.ankiweb.net/what-spaced-repetition-algorithm | Canonical spaced-repetition; informs the eventual v2 retention layer. |
| Bloom-aligned MCQ generation | External — https://arxiv.org/html/2408.04394v1 | Few-shot prompting hits ~78% high-quality, ~65% skill-aligned questions. Use Bloom verbs in system prompt. |
| Production question-gen pipeline | External — https://47billion.com/blog/beyond-prompt-and-pray-building-a-production-grade-ai-question-generation-pipeline/ | Cosine-sim ~0.88 dedup threshold; BM25+embedding+RRF hybrid. **Defer** — v1 uses prompt-based dedup. |
| LLM-as-judge guidance | External — https://www.evidentlyai.com/llm-guide/llm-as-a-judge and HF cookbook | Self-preference bias warning. Reinforces D4 (qualitative feedback, not numeric grading). |
| Socratic AI comprehension study | External — https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2025.1506752/full | Socratic chatbots help low performers, hurt high performers. Reinforces D8 (direct mode only, defer Socratic). |
| `CLAUDE.md` (this repo) | Existing code | Gotcha #6 (LLM provider may be `None`) — reuse the graceful-degradation banner pattern. Gotcha #5 (job completion semantics) — quiz generation jobs follow same partial-failure rules if we make them background tasks. |
| `msf-findings.md` (this folder) | Existing artifact | MSF analysis surfacing R1–R14; all 14 dispositioned and folded into D16–D26 (or Friction-row notes) in Loop 2. |

## Open Questions

| # | Question |
|---|---|
| 1 | What's the length cap (in tokens or characters) for the **Specific Chapters (full content)** scope before the budget bar reads 100%? Needs a number — guidance from `LLMProvider` per-call context budget vs. typical chapter sizes. (Spec to pin.) |
| 2 | What is the exact verbatim-stem cap N for D13's dedup hybrid (recent N + themed summary)? Spec to pin based on per-call prompt budget. |
| 3 | Should the user be able to **delete** a past question from history (so it can be re-generated)? Useful for "I want a do-over" but adds UI surface. |
| 4 | When a book is re-imported and section IDs change, does asked-question history survive the reseat? (Cross-reference CLAUDE.md gotcha #13 — re-import preserves section IDs by `order_index`, so history should survive — confirm.) |
| 5 | Is there a hard cap on consecutive Explain clicks per question (D24)? v1 has no cap; revisit if abuse is observed. |
| 6 | Does the Specific Chapters mode permit selecting non-content sections (e.g., glossary, notes, appendix) or filter them out? Spec to decide based on `BookSection.section_type`. |

---

## Review Log

| Loop | Findings | Changes Made |
|---|---|---|
| 1 | (a) No progress signal in session (motivation-collapse risk). (b) Dedup overflow behavior unspecified. (c) Citation timing was an Open Question — should be a Decision (MCQ leak risk). (d) Override behavior under-specified. (e) Tab discoverability not addressed. | (a) Added Goal + Friction row + D12 + Success Metric for one-click self-assessment counter. (b) Added D13: hybrid dedup (recent N verbatim + themed summary of older). (c) Added D14: shape-conditional citation timing (post-answer MCQ; pre-answer open-ended). (d) Added D15: override appends note, feedback stays, turn flagged. (e) Skipped — single-user personal tool; the user knows where the tab is. |
| 2 | MSF findings R1–R14 surfaced via `/msf-req`: cold-start loading risk, scope-copy ambiguity, no skip affordance, missing session-theme handle, chapter-picker UX, onboarding microcopy, scope memory, lifetime tally gap, no Explain affordance, themes-covered hidden, already-asked microcopy, history pagination, single-chapter rename, self-assessment authority visibility. | All 14 applied. Added D16 (loading state), D17 (scope copy), D18 (Skip), D19 (optional theme), D20 (chapter-picker w/ budget bar), D21 (first-session onboarding microcopy), D22 (last-used scope memory), D23 (lifetime tally), D24 (Explain), D25 (themes-covered visibility), D26 (Past-Q&A grouping). Renamed scope from "Multiple Chapters" to "Specific Chapters" + allow single-chapter selection. Added 2 new Goals (lifetime + theme), 1 Non-Goal (no streaming), 13 new Friction rows, 4 new Success Metrics (lifetime trend, theme bias, skip rate, lifetime tally), updated journey + ASCII flow + empty-state table. Open Q #6 (theme) resolved into D19; replaced with new Open Qs on Explain cap and section-type filtering. |

---

**MSF analysis already applied (see Loop 2). Next: `/spec` to translate into the technical specification.**
