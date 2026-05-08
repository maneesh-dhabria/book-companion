# AI Comprehension Quiz — Requirements

**Date:** 2026-05-08
**Last updated:** 2026-05-08
**Status:** Draft
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
- **The user can choose between two scopes** before each session: quiz over all summaries (book + every chapter summary) or go deep on a chosen subset of chapters using full chapter content — measured by: both scopes are reachable in ≤2 clicks from the Quiz tab.

### Non-Goals (explicit scope cuts)

- **NOT building a spaced-repetition card system** (Anki/FSRS-style daily review queue) in this iteration — because the immediate need is post-read comprehension testing, not long-term retention curves. Revisit after we see usage signal.
- **NOT scoring open-ended answers numerically** (no 1–5 grade, no "you got 7/10") — because the user wants qualitative feedback only; numeric grading invites gameability and adds LLM-judge bias for marginal value.
- **NOT building a Socratic / coach mode** — because v1 stays simple (direct Q→A→feedback loop). Research shows Socratic prompting can hurt high performers; revisit only with clear signal.
- **NOT exposing the quiz on the Reader (BookDetailView) sidebar** — because the user explicitly wants this anchored to the book overview page, where post-read reflection happens, not the reading flow itself.
- **NOT supporting multi-user accounts, sharing, or leaderboards** — because this is a personal tool.
- **NOT generating questions from book metadata, annotations, or external context** in v1 — because scope is restricted to summaries and chapter content. Defer.

## User Experience Analysis

### Motivation

- **Job to be done:** "Help me check whether I actually understood this book — quiz me, tell me what I got wrong, and don't ask me the same thing twice."
- **Importance/Urgency:** Important but not urgent. The user usually triggers quizzing in a deliberate, reflective moment — after finishing a book or before a conversation/meeting where the ideas matter. Latency on first question matters less than question quality.
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
| "It asked me the same thing again." | No dedup. | Persist all asked-question stems per book; pass recent N (or all, if budget allows) to the generation prompt as a "do not ask again" list. |
| "It hallucinated a fact that's not in the book." | LLM grounding drift. | Prompt instructs the agent to ground every question in a specific snippet of the provided content. Surface the source snippet with each question (citation). |
| "I gave a half-right open-ended answer and the feedback was vague." | Qualitative-only feedback can be wishy-washy. | Feedback prompt template demands: (a) what was correct, (b) what was missing, (c) the concept's actual answer per the source. |
| "I want to go deeper on chapter 7 but the agent keeps asking surface questions about the whole book." | Scope confusion. | Two explicit scopes: **All Summaries** vs **Multiple Chapters (full content)**. User picks before starting and can switch mid-session. |
| "I closed the tab and lost my progress." | Session state ephemeral. | Quiz history persists per book. Re-opening the tab shows past Q&A and the "next question" continues from where the asked-question dedup left off. |
| "There's no LLM CLI installed." | Tool depends on Claude/Codex on `$PATH`. | Tab disabled with the same banner pattern used by Summarize/Eval features when no provider is detected (CLAUDE.md gotcha #6). |
| "The book has no summaries yet." | Quiz needs source content. | Empty state: "Generate summaries first" with link to the existing summarize flow. For Multiple-Chapters scope, full content is enough — gate accordingly. |

### Satisfaction Signals

- The user finishes a session and can articulate at least one thing they didn't realize they'd missed.
- The user comes back to the same book's quiz tab a second time — i.e., they trusted the loop enough to return.
- After a session, the user types something like "good question, hadn't thought about that" — direct evidence the agent is provoking actual thinking, not parroting summaries.
- The user voluntarily switches scope from "All Summaries" to "Multiple Chapters" — meaning the surface-level pass left them wanting depth.

## Solution Direction

A **Quiz tab** on `BookOverviewView`, sibling to the existing `overview / summary / sections / audio / annotations` tabs. The tab is a **chat-style surface** where the agent asks one question at a time; the user answers; the agent gives feedback; loop continues until the user stops.

User flow at the behavior level (not architecture):

```
[ Quiz tab opens ]
        │
        ▼
  Empty state OR "Resume" panel showing past Q&A for this book
        │
        ▼
  Scope picker:  ( ) All Summaries     ( ) Multiple Chapters → [pick chapters]
                                                 (subject to length cap; user warned if exceeded)
        │
        ▼
  [ Start Quiz ]
        │
        ▼
┌─────────────────────────────────────────────┐
│  Agent asks Question N                       │
│   - shape: MCQ or open-ended (agent picks)   │
│   - shows source citation (chapter / snippet)│
│                                              │
│  User answers (typed text or option click)   │
│                                              │
│  Agent shows qualitative feedback:           │
│   - what was correct                         │
│   - what was missing                         │
│   - the actual answer with reference         │
│                                              │
│  [ Next Question ]   [ Stop ]   [ Override ] │
└─────────────────────────────────────────────┘
        │
        ▼
  Session continues; asked questions accumulate in DB,
  feeding the dedup list for subsequent turns.
```

Question generation uses the existing `LLMProvider` subprocess pattern (`ClaudeCodeCLIProvider` / `CodexCLIProvider`), invoked by a new `QuizService` that mirrors `AIThreadService`. Asked-question stems for the book are passed into every generation prompt as a "do not repeat" constraint.

## User Journeys

### Primary Journey (Happy Path)

1. **User finishes reading** "Thinking, Fast and Slow" and wants to test their grasp.
2. They open the book on the library page → land on `BookOverviewView`.
3. They click the **Quiz** tab (sixth in the top tab bar).
4. **Empty state** explains: "Quiz me on this book. Pick a scope to start." Two options: *All Summaries* (default selected) and *Multiple Chapters*.
5. User leaves *All Summaries* selected and clicks **Start Quiz**.
6. After a brief generation pause, the agent posts: *"System 1 vs System 2 — give me one example, from the book, of System 1 making a snap judgment that System 2 would override on reflection."* (open-ended, with a small "Source: Chapter 1" citation chip).
7. User types an answer.
8. Agent responds with qualitative feedback: what was right, what they missed (citing the priming/anchoring example), and the concept the book actually uses.
9. User clicks **Next Question**. Agent asks an MCQ on a different concept (e.g., loss aversion), with 4 options.
10. User picks. Agent confirms correct/incorrect and explains the reasoning the book gives.
11. User does this for ~10 questions, then clicks **Stop**.
12. Session is saved. Asked-question stems are persisted under this book.
13. Three days later, user reopens the Quiz tab → sees past Q&A history → starts a new session → the agent does **not** repeat any of the prior questions.

### Alternate Journeys

**Going deep on specific chapters.** After a first all-summaries pass, user picks **Multiple Chapters**, selects chapters 6–8 (the parts on prospect theory). The agent now generates questions grounded in the **full content** of those chapters, not the summaries — questions are noticeably more specific (numbers, examples, edge cases the summary compressed away).

**Mid-session scope change.** User starts in *All Summaries*, realizes they want depth on chapter 4. They click a "Change scope" control, switch to *Multiple Chapters → Chapter 4*, and the next generation uses the new scope. Asked-question history continues to accumulate against the same per-book pool.

**Override unfair feedback.** Agent says the user's open-ended answer "missed the role of cognitive ease" — but the user's answer actually addressed it. User clicks **Override** and types a one-line note ("I did mention cognitive ease"). The override is saved with the feedback turn so future review of history shows the disagreement.

### Error Journeys

- **No LLM provider on PATH.** Quiz tab renders but the action area shows the standard "No LLM provider detected — install Claude Code or Codex CLI" banner (pattern reused from existing summarize / eval features). Past history (if any) remains viewable.
- **All-Summaries scope but no summaries exist.** Empty state shows "Generate summaries first" with a CTA linking to the summarize action. Multiple Chapters scope is still offered (uses full content).
- **Multiple Chapters scope but selected chapters exceed length cap.** Inline warning before Start: *"Selected chapters total ~X tokens; cap is Y. Pick fewer chapters or switch to All Summaries."* No silent truncation.
- **LLM subprocess fails or returns malformed JSON.** Toast: "Couldn't generate a question — try again." The failed attempt is not persisted as an asked-question. User can retry without losing session state.
- **Agent generates a question that's clearly already-asked despite dedup** (low-probability LLM drift). User can click a small "Already asked" link on the question to discard it; that signal also appends a stronger negative example to the next prompt.
- **User's typed answer is empty.** Submit button disabled until at least one character is entered for open-ended; for MCQ, an option must be selected.
- **Book deletion or re-import while a session is open.** Session is gracefully ended; if the book is re-imported, prior asked-question history persists (keyed by book id) — same persistence semantics as summaries.

### Empty States & Edge Cases

| Scenario | Condition | Expected Behavior |
|---|---|---|
| First visit to Quiz tab for a book | No `QuizSession` rows exist for this book | Show scope picker + "Start Quiz" CTA. No "Resume" panel. |
| Returning visit | At least one prior `QuizSession` exists | Show collapsible "Past Q&A" panel above scope picker; "Start New Session" reuses scope picker. |
| No LLM provider | `detect_llm_provider() is None` | Tab shows banner; scope picker disabled; past history viewable. |
| Book has zero summaries AND user picks All-Summaries | `book.default_summary` is null AND no section summaries | Inline gating: "Generate summaries first." Multiple-Chapters path remains enabled. |
| Selected chapters exceed length cap | Sum of `BookSection.content_md` lengths > cap | Block start; show overage in tokens/chars; suggest dropping chapter X. |
| User clicks Stop mid-question (after Q, before answering) | Last turn is a posed question with no answer | Session ends; the unanswered question is **not** added to asked-history (so it can be re-generated next time). |
| User reads asked-question history | Browsing past turns | Read-only render of question + answer + feedback; show timestamp and scope used. |
| Concurrent sessions for the same book on different devices | Theoretical — single user but multi-device | Treat newer session's writes as authoritative; no merge conflict UI. (Personal tool — acceptable.) |

## Design Decisions

| # | Decision | Options Considered | Rationale |
|---|---|---|---|
| D1 | Quiz lives as a 6th top-level tab on `BookOverviewView`, not in the reader sidebar | (a) reader sidebar (sibling to AI Chat), (b) book overview top-tab, (c) both surfaces, (d) modal from Summary tab | User explicitly wants quizzing anchored to the post-read reflection moment. The reader sidebar is for in-flow assistance; the overview page is for review. Surface parity with Summary/Sections matches information architecture. Single surface keeps scope tight for v1. |
| D2 | Two scopes only: **All Summaries** vs **Multiple Chapters (full content)** | (a) single-section picker, (b) book-summary only, (c) all-summaries, (d) multi-chapter full content, (e) all of the above | User chose the two-mode shape directly. "All Summaries" covers the breadth pass; "Multiple Chapters" covers depth. Single-chapter and book-summary-only are subsumed by these (one chapter = special case of multi-chapter). Forces a deliberate choice. |
| D3 | Question shape mix: MCQ + open-ended, **agent picks per turn** | (a) user toggles per session, (b) MCQ only, (c) open-ended only, (d) agent picks | Agent variety is more interesting and matches NotebookLM precedent. Concept type drives shape (facts → MCQ; synthesis → open). User can't predict, which forces engagement. |
| D4 | Open-ended answers get **qualitative feedback only**, no numeric score | (a) LLM-judge with 1–5 score, (b) qualitative only, (c) model answer + self-grade | User chose qualitative-only. Avoids LLM-judge bias and gameability. Feedback must still be structured (correct / missing / actual) so it's useful — vagueness is the failure mode. |
| D5 | Asked-question history is **persistent per book** across sessions | (a) ephemeral per-session, (b) per-book persistent, (c) per-book + per-scope | Persistence matches the user's stated need ("don't ask the same thing again"). Single per-book pool is simpler than per-scope and reflects the reality that the underlying concepts overlap across scopes. |
| D6 | Dedup mechanism: pass asked-question stems to the generation prompt as a "do not repeat" list | (a) pass to prompt, (b) embedding similarity dedup at runtime, (c) both | User explicitly asked for "pass to prompt." Embedding-based dedup is more robust but adds an embedding fetch and a similarity step per generation. Defer to v2 if the prompt-list approach starts missing semantic dupes. |
| D7 | Session model: open-ended chat, **questions keep coming until user stops** | (a) fixed N-question session, (b) chat-style continuous, (c) both modes | User chose chat-style. Matches the existing AI Chat metaphor and the "show them one by one" framing. Fixed-N adds end-of-session ceremony but doesn't fit the personal-reflection use case. |
| D8 | Direct quiz mode only; no Socratic / coach mode in v1 | (a) direct only, (b) Socratic only, (c) toggle | User chose direct-only. Research note: Socratic mode can degrade comprehension for high performers (Frontiers in Education, 2025). Revisit only on signal. |
| D9 | LLM provider: reuse existing auto-detected provider; no new subprocess pattern | (a) reuse `LLMProvider` ABC, (b) new streaming-only provider | The summarize and AI-chat features already work this way; building a parallel pattern is overhead without benefit. Streaming token-by-token is a stretch goal — single-question latency is acceptable since the user expects a thinking pause. |
| D10 | Quiz history is shown in the same tab (collapsible "Past Q&A" panel), not a separate route | (a) inline in tab, (b) `/books/:id/quiz/history` route, (c) sidebar drawer | Inline keeps the surface focused and discoverable. Separate route adds navigation cost for a single-user tool. |
| D11 | If the user closes the tab mid-question (before answering), the unanswered question is **not** added to dedup history | (a) drop, (b) keep | Allowing re-generation is the kinder default — the user might reopen the tab fresh and want the same question they didn't get to. |

## Success Metrics

| Metric | Baseline | Target | Measurement |
|---|---|---|---|
| Quiz tab adoption per recently-summarized book | 0 sessions | ≥1 session within 7 days of summarization completing | Count of `QuizSession` rows per book in the week after `Summary` is generated. |
| Question variety across Bloom levels | Unknown — no quizzing today | ≥30% of questions in a session are above "Remember" (Understand / Apply / Analyze / Evaluate / Create) | Manual coding of a sample of generated questions against Bloom's verbs (one-time validation, then prompt-spot-checks). |
| Question repetition rate | N/A | 0 exact-stem duplicates per book; ≤5% near-duplicate (semantic) rate flagged via spot-check | Stem-equality check across `QuizQuestion` rows for a book; spot-check 50 questions per book using embedding cosine similarity ≥0.88 as "near dupe". |
| Feedback usefulness | N/A | ≥80% of feedback turns reference at least one specific concept from the source content | Manual review of a sample. Heuristic check (is at least one source citation chip present?) as proxy. |
| Session completion (qualitative) | N/A | User reaches ≥5 questions before clicking Stop in a typical session | Count `QuizQuestion` rows per `QuizSession`. Below 3 suggests friction. |
| Return rate | N/A | At least 1 in 3 books with a started session has ≥2 sessions over its lifetime | Books with `count(QuizSession) ≥ 2` / books with `count(QuizSession) ≥ 1`. |
| LLM hallucination rate | N/A | <5% of generated questions reference a fact not present in the source content | Spot-check a sample manually; require source citation in every question to make this auditable. |

## Research Sources

| Source | Type | Key Takeaway |
|---|---|---|
| `frontend/src/views/BookOverviewView.vue` | Existing code | Top-tab pattern (`overview/summary/sections/audio/annotations`); add Quiz as the 6th. `BookTab` type union extended; `setTab()` already wired for query-param sync. |
| `frontend/src/components/sidebar/AIChatTab.vue` | Existing code | Reference for chat-style UI with input + message list; we will mirror but not embed. |
| `frontend/src/stores/aiThreads.ts` and `frontend/src/api/aiThreads.ts` | Existing code | Pinia store + API client pattern to mirror as `quizSessions`. |
| `backend/app/services/summarizer/llm_provider.py` | Existing code | `LLMProvider` ABC supports `json_schema` already; reuse for structured question generation. |
| `backend/app/services/summarizer/claude_cli.py` | Existing code | `ClaudeCodeCLIProvider` reads structured output via `--json-schema`; subprocess waits for full output (no streaming). Acceptable for single-question latency in v1. |
| `backend/app/services/ai_thread_service.py` | Existing code | Service-layer pattern for LLM-backed chat features; `QuizService` will mirror this (fetch book + summaries/sections, build prompt, invoke provider, persist). |
| `backend/app/db/models.py` (`AIThread`, `AIMessage`) | Existing code | Schema template for new `QuizSession` and `QuizQuestion` tables (`book_id`, timestamps, role-equivalent fields). |
| `backend/alembic/` migration history | Existing code | Pattern: `render_as_batch=True` for SQLite ALTER TABLE; new tables added via autogenerate. |
| NotebookLM Quizzes | External — https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-app-quizzes-flashcards/ | MCQ + short-answer mix; difficulty toggle; **citation-backed explanations** — strongest precedent for grounding. |
| Readwise Ghostreader / SR | External — https://docs.readwise.io/reader/guides/ghostreader/overview | Highlights → flashcards → daily review with half-life decay. **Out of scope for v1** but informs a v2 SR direction. |
| Anki + FSRS-6 / RemNote FSRS | External — https://faqs.ankiweb.net/what-spaced-repetition-algorithm | Canonical spaced-repetition; informs the eventual v2 retention layer. |
| Bloom-aligned MCQ generation | External — https://arxiv.org/html/2408.04394v1 | Few-shot prompting hits ~78% high-quality, ~65% skill-aligned questions. Use Bloom verbs in system prompt. |
| Production question-gen pipeline | External — https://47billion.com/blog/beyond-prompt-and-pray-building-a-production-grade-ai-question-generation-pipeline/ | Cosine-sim ~0.88 dedup threshold; BM25+embedding+RRF hybrid. **Defer** — v1 uses prompt-based dedup. |
| LLM-as-judge guidance | External — https://www.evidentlyai.com/llm-guide/llm-as-a-judge and HF cookbook | Self-preference bias warning. Reinforces D4 (qualitative feedback, not numeric grading). |
| Socratic AI comprehension study | External — https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2025.1506752/full | Socratic chatbots help low performers, hurt high performers. Reinforces D8 (direct mode only, defer Socratic). |
| `CLAUDE.md` (this repo) | Existing code | Gotcha #6 (LLM provider may be `None`) — reuse the graceful-degradation banner pattern. Gotcha #5 (job completion semantics) — quiz generation jobs follow same partial-failure rules if we make them background tasks. |

## Open Questions

| # | Question |
|---|---|
| 1 | What's the length cap (in tokens or characters) for the **Multiple Chapters (full content)** scope before we block the Start button? Needs a number — guidance from `LLMProvider` per-call context budget vs. typical chapter sizes. |
| 2 | When the asked-question dedup list grows large (e.g., 100+ stems for a heavily-quizzed book), do we pass all of it to the prompt, the most-recent N, or summarize older stems? Affects prompt budget. |
| 3 | Should the user be able to **delete** a past question from history (so it can be re-generated)? Useful for "I want a do-over" but adds UI surface. |
| 4 | Does the source citation appear inline with the question (e.g., chip) or only in feedback after the user answers (to avoid leaking the answer)? Likely the latter for MCQ on facts; the former for synthesis questions. |
| 5 | When a book is re-imported and section IDs change, does asked-question history survive the reseat? (Cross-reference CLAUDE.md gotcha #13 — re-import preserves section IDs by `order_index`, so history should survive — confirm.) |
| 6 | For the **Multiple Chapters** scope, do we offer "All Chapters" as an explicit shortcut, or is that scope intentionally unavailable (since "All Summaries" already covers breadth)? |
| 7 | Is there value in a one-line **session theme** input (e.g., "focus on prospect theory") on top of scope, or does scope alone suffice for v1? |

---

**For UX friction analysis, run `/msf-req` after this doc is committed.**
