# MSF + PSYCH Findings — AI Comprehension Quiz Wireframes

Entry context: Medium (40, default). Override by editing this line and re-running.

**Generated:** 2026-05-09
**Wireframes folder:** `docs/features/2026-05-08-ai-comprehension-quiz/wireframes/`
**Parent requirements:** `../01_requirements.md`
**Run mode:** invoked from `/wireframes` Phase 6 with `--apply-edits`.

**Persona (from req doc, section "Who experiences this?"):** the single user of this personal tool — a non-fiction reader who imports books to extract durable knowledge.

**Scenarios analyzed:**
- **S1 — Post-read reflection.** Just finished a book; first-ever quiz on it.
- **S2 — Returning learner.** Days/weeks later, opens the Quiz tab a second/third time on the same book.
- **S3 — Goal-directed prep.** Specific topic in mind (e.g., "prepping a meeting on prospect theory"); uses theme + Specific Chapters.

**Journeys covered:** J1 (first quiz happy path), J2 (returning + warm-up), J3 (specific chapters), J4 (auto-default from recent reading), J5 (in-question controls), J6 (question shape variety), J7 (export), J8 (error/empty states).

---

## Section A — MSF Analysis (Pass A, grounded)

### Scenario S1 — Post-read reflection (J1, J6, J5, J7, J8)

| Lens | Consideration | Finding (grounded) |
|---|---|---|
| **M** Motivation | What draws them in? | High intrinsic motivation right after finishing the book. The empty-state copy on `01_quiz-empty` ("Quiz me on this book. Pick a scope to start.") matches the user's mental model — the agent is the interrogator, not a passive resource. Default scope = All Summaries reduces the decision burden (D17/D22). |
| **M** | What do they want to feel? | "Did the ideas land?" — they want surprise (concepts they thought they knew but didn't), not validation. The shape variety in W04/W05/W06 + the no-citation-pre-answer rule on MCQ (D14, visible in `07_q-turn-mcq` default state — citation suppressed; "Source revealed after answer" annotation present) preserves that surprise. |
| **F** Friction | First-impression cost | The pre-drafted Q1 (D27) makes the first question instant for the default scope. **But** if the user happens to type a theme on the very first session ever (plausible for S1 if they want to drill into a specific concept they're unsure about), they fall back to the 8–15 s loading state on `07_q-turn-mcq` `loading-draft`. The copy is reassuring ("Reading the book to draft your question…") but the wait is still the worst friction point in S1. |
| **F** | Effort during the loop | After answering an open-ended question, the second loading state ("Reading your answer alongside the book…", `09_q-turn-open` `grading-loading`) lands when the user has just spent effort typing — momentum is fragile here. The reassuring copy mitigates but doesn't eliminate the trust dip. |
| **F** | Decisions per turn | Self-assessment row (`07_q-turn-mcq` `answered-revealed`) presents three buttons — Got it / Partial / Missed — which is the right cardinality (D12). The first-session microcopy ("Your click is authoritative for the session tally") prevents the "what do these buttons even do" friction (D21). |
| **S** Satisfaction | What proves it worked? | The lifetime tally is the long-arc payoff (D23, surfaced on `05_quiz-returning`); for S1 the immediate payoff is the structured feedback (`09_q-turn-open` `feedback`: what was correct / what was missing / the book's answer) + the source citation revealing exactly where in the book the concept lives. |
| **S** | Closing the session | `17_session-end` `end-summary` shows tally + "Concepts revisited" chips. The Export Session action turns the session into a durable artifact (D30). For S1 specifically, the export is meaningful because they may want to share back to their notes app while the book is still fresh in their head. |

### Scenario S2 — Returning learner (J2, J3 or J4, J5)

| Lens | Consideration | Finding (grounded) |
|---|---|---|
| **M** | Why do they come back? | Not the book itself — they come back to *check whether the gaps closed*. The warm-up banner on `15_warm-up` `warm-up-banner` ("Last time you marked **anchoring effect** as Missed and **availability heuristic** as Partial — let's revisit.") is the strongest motivational hook in the entire flow because it names specific concepts. |
| **M** | What kills the return? | If the warm-up always opens with what they got wrong, sessions feel like remediation. Over multiple visits this could drift toward "the tab where I prove I'm not learning fast enough." |
| **F** | Returning recognition cost | `05_quiz-returning` lifetime tally + "Past Q&A" panel grouped by session (D26) is good — most-recent expanded by default. The "Themes covered" panel (D25) is excellent for recognition-not-recall. |
| **F** | Re-orientation | Last-used scope memory (D22) saves a click, and recent-reading auto-default (D31, visible in `03_scope-specific-chapters` `auto-default`) saves more. Strong friction reduction. |
| **F** | Warm-up bypass | The "Skip warm-up" ghost button on `15_warm-up` `warm-up-banner` is correctly placed but visually subordinate. For returning users who don't want remediation, it should be clearly available without feeling like a guilt trip. The current treatment is acceptable. |
| **S** | Compound progress | The lifetime tally trending toward more "Got it" across sessions (Goal: cumulative learning compounds) is the core long-arc satisfaction signal. **The wireframes show the tally but not the trend** — there's no sparkline or "Got it: 60% → 65% → 71% across 3 sessions" line that would make compounding visible. |
| **S** | Concept retirement | A concept the user has marked "Got it" three sessions running could earn a "Mastered" chip — currently invisible. |

### Scenario S3 — Goal-directed prep (J3, J4, J6)

| Lens | Consideration | Finding (grounded) |
|---|---|---|
| **M** | Specific outcome in mind | "I have a meeting on prospect theory tomorrow; quiz me hard on it." Motivation is high but **time-bounded**. They want focused depth, not breadth. |
| **M** | Theme field as the affordance | The optional theme input (`01_quiz-empty` `theme-typed` state, with helper text "Questions will bias toward this theme.") is exactly the right surface — but its discoverability is medium. It's a single line below the scope picker; users who don't read carefully may miss it on first visit. |
| **F** | Picking chapters | `03_scope-specific-chapters` shows ~20 chapter rows with checkboxes + the budget bar. For a user who wants "Part 4: Choices" (8 chapters in Kahneman), there's no batch affordance — that's 8 individual clicks, then watching the budget bar. |
| **F** | Budget bar feedback | The budget bar (D20) is the strongest piece of UX on this screen — it makes the LLM context cap legible. The over-budget state inlines the rejection ("Would exceed budget — deselect a chapter to add.") so the user doesn't lose state. |
| **F** | Theme + budget interaction | If the user types a long theme description, the prompt budget shrinks correspondingly — the wireframes don't surface this. |
| **S** | Did the depth pass land? | The shape variety (MCQ + open + spot-the-error) within a tight chapter scope is the satisfaction lever — questions visibly cite "Source: Chapter 26 — Prospect Theory" (W04, W06 post-answer). For S3 the satisfaction is "the agent quizzed me on the actual content I picked, not the summary I already read." |
| **S** | Export for the meeting | If the user is prepping for a meeting, exporting (`17_session-end`) is the artifact they take into the meeting. The Markdown preview in the export modal sets that expectation well. |

### Cross-scenario MSF observations

- **The scope-picker copy** (D17 verbatim labels: "All Summaries (book summary + every chapter summary)" / "Specific Chapters (full text of selected chapters)") is the single best piece of friction-reducing copy in the flow. It defangs the "what does this actually feed the agent" anxiety.
- **The Override pattern** (D15) is a quiet motivation booster: it tells the user the agent can be wrong AND the user's verdict still counts (`09_q-turn-open` `override-applied`). For S2 specifically (returning user, more confident in the material), this matters — without it, false-negative grading would compound into "the agent doesn't get me" frustration.
- **Skip without dedup penalty** (D18, surfaced on `13_q-controls` `skip-confirmation`) is a friction-pressure-release valve. Critical for S3, where some auto-generated questions will miss the user's actual goal.

---

## Section B — PSYCH Scoring (Pass B)

Default entry context: **Medium (40)**.

PSYCH score is **directional**. Drops below 20 = directional danger zone; below 0 = bounce risk. Only notable elements scored.

### Per-screen scores (selected screens that materially shift the trace)

#### `01_quiz-empty_desktop-web.html` — Scenario S1 entry, default state

Starting PSYCH: 40.

| Element | Score | Running |
|---|---|---|
| Page header "Quiz me on this book. Pick a scope to start." | +4 (clarity, mental-model match) | 44 |
| Two scope radios with explicit helper text (D17) | +5 (decision pre-resolved with sensible default) | 49 |
| First-session onboarding hint (mix of MCQ + open-ended) | +3 (sets expectation, prevents "what is this") | 52 |
| Optional theme field below the picker | +1 (small effort to read placeholder) | 53 |
| "Start Quiz" primary CTA | +5 (clear single action; primary visible) | 58 |
| `no-llm` state — disabled CTA + remediation banner | −4 (motivation killer; no path forward without external action) | 54 (but this isn't on the default trace) |

**Trace finishes at 58. No danger zone.**

#### `03_scope-specific-chapters_desktop-web.html` — S3 entry, partial state (3 chapters checked)

Starting PSYCH: 50 (carrying through from `01_quiz-empty`).

| Element | Score | Running |
|---|---|---|
| Chapter list with ~20 rows of checkboxes | −5 (decision-heavy; Hick's Law) | 45 |
| Budget bar at 58% with clear label | +5 (legibility — Claude-Code-style is familiar) | 50 |
| Real chapter names (e.g., "11. Anchors", "26. Prospect Theory") | +2 (recognition over recall — user reading the book picks the right chapters faster) | 52 |
| 3 chapters checked = 3 + decisions made | −3 (effort bookkeeping) | 49 |
| `over-budget` state: greyed row + inline explanation | +3 (failure feedback is concrete and recoverable, no silent truncation) | 52 |
| `auto-default` banner (D31) | +6 (recognition: "the system already knows what I just read") | strong S2 boost when this fires |

**Trace finishes around 49–52. No danger zone.** Budget bar is the strongest +PSYCH driver on this screen.

#### `07_q-turn-mcq_desktop-web.html` — Core loop, S1/S2/S3 all converge here

Starting PSYCH: 50 (after `Start Quiz` click).

| State / Element | Score | Running |
|---|---|---|
| `loading-draft` state — skeleton + "Reading the book to draft your question…" | −4 (waiting; mitigated by copy + skeleton, not eliminated) | 46 |
| `default` — question stem + 4 options visible, no citation | −1 (decision: pick an option) | 45 |
| `default` — Skip / Explain / Stop visible below | +2 (escape valves) | 47 |
| `answered-revealed` — option marked correct + citation chip appears | +5 ("aha"; surprise about hidden answer source) | 52 |
| `answered-revealed` — feedback panel (3 short lines) | +5 (immediate value — what was right / missing / actual) | 57 |
| `answered-revealed` — self-assessment row + microcopy | +3 (agency; user click is authoritative) | 60 |
| `fatigue-prompt` — appended "Want to keep going or wrap up here?" | +2 (permission to stop without abandonment) | 62 |
| Subsequent question (no D27 pre-draft after Q1) — second `loading-draft` | −3 (repeats wait; momentum dip) | 59 |

**Best single screen on the +PSYCH side. No danger zone.** The post-answer reveal is the biggest motivation moment in the entire flow.

#### `09_q-turn-open_desktop-web.html` — Open-ended question

Starting PSYCH: 50.

| State / Element | Score | Running |
|---|---|---|
| `default` — question + citation chip pre-answer (D14) | +2 (helpful; tells the user where to draw from without giving the answer) | 52 |
| `default` — empty textarea + Submit disabled | −5 (effort — typing a paragraph is the highest friction action in the entire flow) | 47 |
| `typed` — textarea filled | (transition) | 47 |
| `grading-loading` — "Reading your answer alongside the book…" | −3 (waiting after effort spent) | 44 |
| `feedback` — structured 3-line feedback + citation | +6 (high-value structured payback) | 50 |
| `override-applied` — original feedback retained + user note appended | +4 (agency; "the agent doesn't overrule me") | 54 |
| Self-assessment row | +3 | 57 |

**Trace finishes ~57. No danger zone, but the textarea is the steepest single dip.** A "Save draft if you tab away" micro-affordance would smooth this — out of v1 scope.

#### `15_warm-up_desktop-web.html` — S2 entry into a returning session

Starting PSYCH: 50 (S2 baseline; user came back deliberately).

| Element | Score | Running |
|---|---|---|
| Warm-up banner naming concrete concepts ("anchoring effect", "availability heuristic") | +6 (recognition + acknowledgment that the system remembered) | 56 |
| "2 questions, fresh stems. Counted in your tally." subtext | +3 (predictability — bounded scope) | 59 |
| "Skip warm-up" ghost button | +2 (escape valve) | 61 |
| Phase chip "Warm-up · 1 of 2 · concept: anchoring effect" | +2 (orientation in flow) | 63 |
| Q1 fresh-stem MCQ on anchoring | (per W04 trace, peaks ~62) | 62 |

**Strongest opener in the entire feature.** The named concepts make S2 feel respected, not remediated.

#### `17_session-end_desktop-web.html` — Closing screen, all scenarios

Starting PSYCH: variable (50–62 depending on session length). Assume 55 entering.

| Element | Score | Running |
|---|---|---|
| Session tally (`Session: 6 Got it · 3 Partial · 1 Missed (1 skipped)`) | +4 (concrete recap) | 59 |
| Lifetime tally + "across 3 sessions" | +5 (compound progress; satisfies S2/S3) | 64 |
| "Concepts revisited" chips ("anchoring effect — Missed", "availability heuristic — Partial") | +3 (forward-loop signal: tells the user what next session will pick up) | 67 |
| Export Session primary CTA | +5 (durable artifact; satisfies S1's "share to notes" and S3's "into the meeting") | 72 |
| `export-confirmed` toast | +2 (closure feedback) | 74 |
| `export-disabled` (0 questions session) state — disabled CTA + tooltip | −2 (mild dead-end) | drop, but this is a non-default branch |

**Best closing screen. No danger zone.** The export action is the durable-artifact promise paying out.

### Journey rollup (directional)

| Journey | Entry | Lowest point | Closing | Notes |
|---|---|---|---|---|
| **J1 First quiz (S1)** | 40 | ~44 (loading-draft if not pre-drafted) | ~74 (export) | Strong arc; pre-drafted Q1 saves the entry. |
| **J2 Returning + warm-up (S2)** | 50 | ~50 | ~74 | Warm-up banner is the strongest +PSYCH event in the feature. |
| **J3 Specific Chapters (S3)** | 40 | ~45 (chapter list decision burden) | ~72 | Budget bar offsets list-length friction. |
| **J4 Auto-default (S2/S3)** | 50 | ~52 | ~72 | Recent-reading override (D31) saves clicks AND sets context. |
| **J5 In-question controls (cross)** | varies | varies | varies | Skip / Explain / Override are all friction-pressure-release valves; no single-screen danger zone. |
| **J6 Shape variety (cross)** | 50 | ~46 | ~62 | Spot-the-error has the same arc as MCQ; open-ended has the textarea dip. |
| **J7 Export (closing)** | 55 | n/a | ~74 | Closing payoff. |
| **J8 Error states (S1 unhappy)** | 40 | ~30 (no-LLM banner) | recoverable only via external action | Below danger zone; this is acceptable because it's a hard external dependency. The wireframes correctly tell the user what to install. |

**No screens in the bounce-risk zone (PSYCH < 0) on the default trace.** The `no-LLM` state on `01_quiz-empty` drops to ~30 (directional danger zone) but it's a hard environmental gate, not a feature flaw — the wireframes correctly surface the install path.

### Unsurfaced findings

None. All notable scores are surfaced above.

---

## Section C — Recommendations (prioritized)

### Must

_(none)_

### Should

| ID | Finding | Affected screens | Suggested change |
|---|---|---|---|
| R1 | **Compound progress invisible.** Lifetime tally shows current totals but no trend ("Got it: 60% → 65% → 71% across 3 sessions"). For S2 the goal-state is *visible compounding learning* — the bare counters don't deliver this. | `05_quiz-returning` (default + last-used-specific states), `17_session-end` (end-summary state) | Add a one-line trend after the lifetime line on both surfaces. Sparkline is overkill; a single arrow + delta ("Got it 60% → 71% over 3 sessions, ↑ 11pp") is enough. |
| R2 | **Bulk chapter selection missing.** Picking a multi-chapter "Part" (e.g., Part 4: Choices = 8 chapters in Kahneman) is 8 individual clicks. S3 (goal-directed) is the most affected. | `03_scope-specific-chapters` (default, partial states) | Add a "Select Part" / "Select all visible" affordance — either parent-row checkboxes when the book exposes parts (`section_type=part`), or a small "Pick range…" link that opens a chapter-N-to-M shortcut. Keep budget enforcement intact: if "Select Part" would exceed budget, fall back to as-many-as-fit + inline explanation, mirroring D20's existing rejection language. |
| R3 | **First-question pre-draft only covers default scope (D27).** If S1 user types a theme on their very first session, they hit the slow `loading-draft` state — exactly when first impression matters most. | `01_quiz-empty` (theme-typed → start), `07_q-turn-mcq` (loading-draft) | Two options: (a) regenerate the pre-drafted Q1 to bias toward the typed theme on Start (same generation cost moved earlier); (b) make the loading-state copy on `loading-draft` acknowledge the theme: "Reading the book to draft a question on **prospect theory**…" — costs nothing, signals the theme survived the click. Recommend (b) for v1. |

### Nice

| ID | Finding | Affected screens | Suggested change |
|---|---|---|---|
| R4 | **Self-assessment lacks "Not sure".** The 3-button row (Got it / Partial / Missed) forces a verdict. Users uncertain of their own grasp tend to default to Partial, which dilutes the lifetime tally signal. | `07_q-turn-mcq` (answered-revealed onward), `09_q-turn-open` (feedback onward), `15_warm-up` | Add a 4th tally-neutral "Not sure" affordance OR explicitly allow no-click-and-Next (currently the wireframes assume the click is mandatory). Resolve via a Self-assessment FAQ in onboarding microcopy. |
| R5 | **Themes-covered panel is unbounded.** Across many sessions, the "Themes covered" chip list (D25) grows without curation. | `05_quiz-returning` (default, themes-covered states) | Group by recency: top row = "Recent (this month)", second row = "All-time (collapsed)". Or cap to top-N most-recently-asked. |
| R6 | **Concept-mastered signal missing.** A concept Got-it three sessions running has no visible "graduated" state — it stays in the candidate pool for warm-up forever (filtered by D29 not-yet-Got-it logic, but the user doesn't see the graduation). | `05_quiz-returning` (themes-covered), `17_session-end` (concepts-revisited chips) | Add a small "Mastered" green dot on chips that have ≥3 consecutive Got-it across sessions. Doesn't change behavior, just acknowledges retention to the user. |
| R7 | **Loading copy doesn't differentiate first-question from Nth-question.** The same "Reading the book to draft your question…" string runs on every Next-click, not just the cold start. | `07_q-turn-mcq` (loading-draft), `09_q-turn-open` (loading variants) | After Q1, shorten to just "Drafting…" — recognizes user momentum is built. |

---

## Section D — Applied changes

| ID | Disposition | Files edited | Change |
|---|---|---|---|
| R1 | Fix as proposed | `05_quiz-returning_*.html` (×4 instances ea), `17/18_session-end_*.html` (×3 ea) — 14 trend lines total | Trend line "↑ 11pp · Got it 60% → 71% over 3 sessions" added below every canonical lifetime tally line. |
| R2 | Fix as proposed | `03/04_scope-specific-chapters_*.html` | "Pick range…" toolbar above chapter list; per-Part "Select all in Part" link beside every Part header (5 states ea). Budget enforcement preserved with verbatim D20 rejection copy on near/over-budget. |
| R3 | Fix as proposed | `07/08_q-turn-mcq_*.html` | `loading-draft` state now renders TWO sub-blocks side-by-side: no-theme variant + theme-aware variant ("Reading the book to draft a question on **prospect theory**…"). Annotation explains the variance. (W05 open-ended skipped — has no `loading-draft` state by design.) |
| R4 | Fix as proposed | `07/08_q-turn-mcq_*.html`, `09/10_q-turn-open_*.html`, `15/16_warm-up_*.html` (6 files) | 4th tally-neutral "Not sure" pill added to every self-assessment row. Annotation: tally-neutral but concept_label still recorded so D29 warm-up can resurface. |
| R5 | Fix as proposed | `05/06_quiz-returning_*.html` | Themes-covered panel restructured into "Recent (this month)" + "All-time (+N more)" sub-rows. |
| R6 | Fix as proposed | `05/06_quiz-returning_*.html`, `17/18_session-end_*.html` | Green-dot "Mastered" indicator prepended to chips for concepts with 3 consecutive Got it. Applied to "System 1 / System 2", "cognitive ease". |
| R7 | Fix as proposed | `07/08_q-turn-mcq_*.html` | Annotation added on `loading-draft` explaining post-Q1 copy shortens to "Drafting…" (full copy retained on Q1 because cold-start anxiety is highest there). |

All edits spot-checked against `/wireframes` rubric inline; no Phase 4 review-loop re-trigger.

**Outcome:** clean. 7 findings dispositioned, 7 applied.
