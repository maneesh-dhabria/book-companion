# Creativity Analysis — AI Comprehension Quiz

**Date:** 2026-05-08
**Source:** `docs/features/2026-05-08-ai-comprehension-quiz/01_requirements.md` (Loop 2 / Approved)
**Personas:** P1 Post-Read Reflective, P2 Deep-Dive Studier
**Journeys:** J1 first quiz, J2 Specific Chapters, J3 return visit

Tier 1 techniques applied with depth; Tier 2 quick pass. 0 ideas from a technique is fine — no padding.

---

## Tier 1 Findings

| # | Technique | Idea | Affected | Effort | Tier |
|---|---|---|---|---|---|
| C1 | Remove friction | **Pre-generate a question queue on summary completion.** When `Summary` is generated for a book, kick off a background job that drafts the first 10–20 candidate questions for the default scope (All Summaries) and stores them. Quiz tab serves the first question instantly from the queue; the agent still tops up the queue in the background as the user proceeds. Eliminates cold-start latency for the most common path. | J1 first turn (P1, P2) | Med–High | Should |
| C2 | Reduce anxiety | **Reassuring loading copy during feedback generation.** Right after the user submits an answer, the LLM-grading round-trip is another blank-screen moment with extra anxiety ("did I bomb that?"). Show "Reading your answer alongside the book…" loading copy. Pairs with D16 but covers the second latency point. | All journeys, every answer turn | Low | Should |
| C3 | Solve unexpressed need | **Re-surface 'Missed' concepts at the start of the next session.** The user wants to *retain* the book, not just check it once. SR is a Non-Goal — but a lite version is cheap: when a session starts and the prior session has any "Missed" or "Partial" turns, the agent opens with a 1–2 question warm-up on those concepts (using fresh questions, not repeats). Closes the retention gap without building FSRS. | J3 (return visit) | Med | Must |
| C4 | Reframe | **Quiz session = exportable study notes.** Reframe each session as a co-authored study artifact. Add a "Export this session" action that compiles the Q&A + feedback + the user's self-assessment + override notes into a Markdown doc (reusing the existing export infrastructure). Turns a transient quiz into a durable artifact and lets the user revisit their own thinking. | All journeys, post-session | Med | Should |
| C5 | Make it unnecessary | **Auto-default scope based on recent reading activity.** The repo has `/reading-state` tracking. If the user just finished reading chapters 6–8, the Quiz tab defaults to Specific Chapters with those chapters pre-selected (overrides D22's "last-used" default). One less decision; agrees with the user's actual context. | J1, J2 entry | Low | Should |
| C6 | Do the opposite | **"Spot the error" question shape.** Adds a third question shape alongside MCQ and open-ended: agent presents a *deliberately-wrong* restatement of a concept and asks the user to identify the flaw. Forces Apply / Analyze Bloom levels naturally; agent variety expands. Low marginal effort because it slots into D3's agent-picks-shape decision. | All journeys | Med | Should |

## Tier 2 Findings

| # | Technique | Idea | Affected | Effort | Tier |
|---|---|---|---|---|---|
| C7 | Combine unrelated | **Annotation-seeded questions.** The user already creates annotations on passages they found important. When generating questions, bias toward annotated content for the selected scope. The user has self-signaled what matters; we should test on it. | J1, J2 (any book with annotations) | Low | Must |

## Considered & Dropped

- **Reframe "Quiz" → "Conversation with the book"** (positioning copy change). Considered; not actionable as a requirements change. Note for spec UI copy if it resonates.
- **Cross-book quizzing** ("quiz me on all behavioral econ books"). Genuinely interesting but Non-Goal-adjacent and out of scope for v1.
- **Concept-graph-driven question targeting** (existing concepts feature). Powerful but overengineered for v1; keep for v2 backlog.
- **Time-boxed "5-min review" mode.** Contradicts D7 chat-style.
- **Voice input for answers.** Heavy.
- **Random "fun question" easter-egg button on the overview tab.** Cute but distracting.
- **One-question-a-day push card.** Too far from current scope.

---

## Per-Journey Summary

| Journey | Strongest ideas |
|---|---|
| J1 (first quiz) | C1 (pre-generate queue), C5 (auto-default scope), C7 (annotation seeding), C2 (answer-grading loading copy) |
| J2 (Specific Chapters) | C5, C7, C6 ("Spot the error") |
| J3 (return visit) | C3 (Missed warm-up), C4 (export session), C2 |

---

## Open Questions

- C1: should the pre-generated queue be invalidated when the user picks a non-default scope? Likely yes — the queue is scope-specific. Spec to decide.
- C3: what counts as a "fresh question" on a Missed concept — must the stem differ verbatim, or is dedup-against-prior-session-only enough?
- C7: when annotations exist but the user asks for a non-annotation-overlap scope (e.g., a chapter with no annotations), do we bias toward annotations across the whole book or stay strict to scope?
