# Book Companion Web Interface — PSYCH Framework Analysis

**Date:** 2026-04-10
**Framework:** [PSYCH Framework](https://andrewchen.com/psychd-funnel-conversion/) by Darius Contractor
**Analyzed against:** [V1.1 Web Interface Requirements](../requirements/2026-04-10_web_interface_v1_requirements.md)
**Companion analysis:** [MSF Analysis](2026-04-10_web_interface_msf_analysis.md)

---

## Scoring Methodology

Every UI element is scored as **+Psych** (adds motivation) or **-Psych** (drains motivation), with values from 1-10. A running total is tracked across each screen in a journey.

| Zone | Psych Level | Meaning |
|------|-------------|---------|
| Safe | > 40 | User is engaged, will push through minor friction |
| Caution | 20-40 | User is wavering, one bad element could cause abandonment |
| Danger | < 20 | High bounce risk, user is looking for exit |

**Starting Psych by entry context:**

| Context | Starting Score | Applied To |
|---------|---------------|------------|
| High-intent (user chose to act) | 60 | Search / Knowledge Retrieval |
| Medium-intent (exploring) | 40 | Reading + Annotation, AI Chat |
| Low-intent (casual/first-time) | 25-30 | First Upload, Mobile Reading |

---

## Journey Scorecard Summary

| Journey | Persona | Start | End | Net | Lowest Point | Danger Zone? |
|---------|---------|-------|-----|-----|-------------|-------------|
| **Search** | Knowledge Retriever | 60 | 125 | +65 | 60 (start) | Never |
| **Reading + Annotation** | Active Learner | 40 | 89 | +49 | 50 (eval detail) | Never |
| **AI Chat** | Active Learner | 40 | 76 | +36 | 40 (start) | Never |
| **Mobile Reading** | Mobile Reader | 30 | 74 | +44 | 26 (LAN setup) | Near (26) |
| **First-time Upload** | First-Upload User | 25 | 46 | +21 | 28 (5-step stepper) | Near (28) |

**Key finding:** No journey enters the danger zone (< 20), but two journeys dip into the caution zone: Mobile LAN setup (26) and first-time upload step indicator (28). Both involve low-intent users encountering unexpected complexity.

---

## Journey 1: First-Time Upload

**Persona:** First-Upload User | **Start: 25** | **End: 46**

### Screen-by-Screen Scoring

**Screen 1: Empty Library (25 → 31)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| "Welcome to Book Companion" headline | + | +2 | 27 | Warm, not intimidating |
| 3-step "how it works" illustration | + | +4 | 31 | Value preview in 3 seconds |
| "Upload Your First Book" CTA | + | +2 | 33 | Single clear action |
| "0 books" counter in header | - | -1 | 32 | Emptiness reminder |
| Search bar visible (useless with 0 books) | - | -1 | 31 | Dead control |

**Screen 2: Upload Step 1 — Drag-Drop (31 → 35)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| 5-step progress stepper | - | -3 | 28 | User sees 5 steps ahead — intimidating for low-intent |
| Large drag-drop zone | + | +3 | 31 | Zero decisions, familiar pattern |
| Format list (EPUB, MOBI, PDF) | - | -1 | 30 | "Do I have the right format?" |
| File selected, parsing progress (64%) | + | +3 | 33 | Immediate response, something is happening |
| "Extracting chapters and metadata" status | + | +2 | 35 | Transparency builds trust |

**Screen 3: Quick Upload Fork (35 → 48)** -- PEAK

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| Green checkmark, "14 sections detected" | + | +4 | 39 | First reward — tool understands the book |
| Extracted metadata (title, author) | + | +3 | 42 | Proof of competence |
| **"Start with Recommended Settings" CTA** | **+** | **+5** | **47** | **Peak moment. Eliminates 3 steps. Respects low-intent user.** |
| "Customize metadata, structure & preset" link | + | +1 | 48 | Escape hatch without pressure |

**Screen 4-5: Metadata + Structure Review (48 → 51, Customize path)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| Pre-filled metadata from parsing | + | +2 | 50 | Less work than expected |
| Form fields to review/edit | - | -2 | 48 | Physical effort, decisions |
| "All sections look well-structured" banner | + | +3 | 51 | Auto-skip signal |
| Merge/split tools visible | - | -2 | 49 | Decisions user didn't ask for |
| Prominent "Next" button in banner | + | +2 | 51 | Clear escape |

**Screen 6: Preset Selection (51 → 44)** -- LOWEST DIP ON CUSTOMIZE PATH

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| "Recommended" badge on Balanced preset | + | +3 | 54 | Removes decision anxiety |
| 4 preset choices | - | -3 | 51 | Choice overload for first-timer |
| Expandable facets (Style, Audience, Compression) | - | -2 | 49 | Jargon: "Compression level?" |
| "+ Create Custom Preset" | - | -1 | 48 | More options = more cognitive load |
| **Cost estimate ("~8 min, ~$1.50")** | **-** | **-4** | **44** | **Surprise cost discovery. User didn't know this costs money.** |
| "Run eval" / "Auto-retry" checkboxes | - | -2 | 42 | Technical jargon — "eval" means nothing to new users |
| "Start Summarizing" button | + | +2 | 44 | Clear finish line |

**Screen 7: Processing Progress (44 → 46)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| Non-blocking bottom bar | + | +3 | 47 | Freedom, not trapped |
| "5/14 sections" progress | + | +2 | 49 | Granular, predictable |
| ~8 minute wait | - | -3 | 46 | Long wait with no intermediate value preview |

### Interventions Needed

| Priority | Intervention | Current Score Impact | Expected Impact |
|----------|-------------|---------------------|----------------|
| **Critical** | Move cost indication to empty library or Step 1 — surprise cost at Step 6 is -4 | -4 at Step 6 | -1 earlier (expected, not surprising) |
| **High** | Hide "Run eval" / "Auto-retry" under "Advanced" disclosure | -2 at Step 6 | 0 (invisible to new users) |
| **High** | Show first completed section summary during processing wait | -3 at Step 7 | +3 (converts wait into "aha") |
| **Medium** | Reduce visible stepper to 3 steps (Upload / Configure / Process) | -3 at Step 1 | -1 (less intimidating) |

---

## Journey 2: Reading + Annotation

**Persona:** Active Learner | **Start: 40** | **End: 89**

### Screen-by-Screen Scoring

**Screen 1: Book Detail Landing (40 → 54)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| Breadcrumb navigation | + | +3 | 43 | Instant orientation |
| Chapter dropdown with eval dots | + | +4 | 47 | Progress-at-a-glance across whole book |
| Prev/Next arrows | + | +2 | 49 | Effortless navigation |
| Original/Summary toggle | + | +3 | 52 | Clear binary, no jargon |
| "38% compression" metadata | - | -1 | 51 | System jargon |
| Centered reading column (680px) | + | +3 | 54 | Feels like a reading experience, not a dashboard |

**Screen 2: Summary View (54 → 60)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| Eval banner (14/16 passed) | + | +2 | 56 | Trust signal |
| Eval detail expansion (5 categories) | - | -3 | 53 | QA dashboard, not a study tool |
| Failed assertion reasoning | - | -2 | 51 | Pulls attention from studying |
| Re-evaluate button | - | -1 | 50 | Unclear when useful |
| **Concept chips** | **+** | **+5** | **55** | **Best element — key ideas surfaced visually** |
| Concept tooltip (definition + cross-refs) | + | +4 | 59 | Cross-referencing is exactly what deep study needs |
| Summary version picker | - | -2 | 57 | Decision: which version am I reading? |
| Key Quotes blockquote | + | +3 | 60 | Curated quotes feel like distilled wisdom |

**Screen 3: Text Selection (60 → 64)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| Floating toolbar on select | + | +4 | 64 | Zero-effort, appears when needed |
| 5 toolbar options | - | -2 | 62 | "Link" unclear on first encounter |
| Ask AI in purple accent | + | +2 | 64 | Visual distinction, signals capability |

**Screen 4: Creating Highlight/Note (64 → 65)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| One-click highlight | + | +3 | 67 | Minimal friction |
| Cross-view annotation indicators | + | +2 | 69 | Reassurance annotations persist |
| Annotation Link Dialog (full modal) | - | -4 | 65 | Heavy modal interrupts study flow |

**Screen 5: Annotations Sidebar (65 → 75)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| Sidebar with two tabs | + | +2 | 67 | Manageable |
| Annotation cards with quotes + notes | + | +3 | 70 | Own notes alongside source — satisfying |
| Edit/Link/More actions | - | -1 | 69 | "Link" again raises confusion |
| "Add a note" input at bottom | + | +2 | 71 | Low-effort freeform notes |
| Badge count on collapsed icon | + | +2 | 73 | "I've done work here" — motivating |
| Collapsible to full-width | + | +2 | 75 | Flexibility without decisions |

**Screen 6: Reader Settings (75 → 89)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| **Visual preset cards** | **+** | **+5** | **80** | **Outstanding — actual background + font rendering** |
| Named sizes (Small/Medium/Large) | + | +3 | 83 | Words > numbers |
| Manual stepper alongside presets | + | +1 | 84 | Power users can fine-tune |
| 8 font choices | - | -2 | 82 | Paradox of choice — 4-5 would suffice |
| Background swatches with names | + | +2 | 84 | Named options cover 95% of needs |
| **Live preview with book text** | **+** | **+4** | **88** | **Eliminates guesswork entirely** |
| Settings summary line | + | +1 | 89 | Confirms choices, reassuring |

### Interventions Needed

| Priority | Intervention | Current Impact | Expected Impact |
|----------|-------------|---------------|----------------|
| **High** | Collapse eval detail to single trust badge (green/yellow/red) | -6 (expansion + detail) | -1 (just a badge) |
| **High** | Lighten Link Dialog — move full version to sidebar | -4 (modal) | -1 (inline quick link) |
| **Medium** | Auto-select latest summary version, bury history | -2 (version picker) | 0 (no decision) |
| **Low** | Reduce fonts from 8 to 4-5 with "All fonts" expansion | -2 | -1 |

---

## Journey 3: Search

**Persona:** Knowledge Retriever | **Start: 60** | **End: 125**

### Screen-by-Screen Scoring

**Screen 1: Command Palette — Empty (60 → 72)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| Cmd+K shortcut | + | +6 | 66 | Zero-navigation access, muscle memory |
| "Search books, sections, concepts..." placeholder | + | +2 | 68 | Signals broad scope |
| Recent searches list | + | +5 | 73 | May already see what they need |
| Quick Actions | - | -1 | 72 | Mild distraction |

**Screen 2: Command Palette — With Results (72 → 90)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| Instant grouped results (4 categories) | + | +7 | 79 | Answers appear before finishing typing |
| Bold match highlighting | + | +3 | 82 | Eye jumps to relevance |
| Concept result with definition snippet | + | +5 | 87 | Could be enough for the meeting |
| Annotation result with personal note | + | +4 | 91 | Seeing own thinking is deeply satisfying |
| 4 category headers | - | -2 | 89 | Scanning cost |
| Keyboard shortcut footer | + | +2 | 91 | Confidence in fast navigation |
| No relevance scores in palette | - | -1 | 90 | Slight uncertainty |

**Screen 3: Full Results Page (90 → 103)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| Grouped by book with match counts | + | +4 | 94 | Know which book to focus on |
| Color-coded type badges | + | +3 | 97 | Fast visual scanning |
| Relevance score (0.92) | + | +2 | 99 | Builds trust in ranking |
| Snippets with bold highlights | + | +3 | 102 | Can extract insight without clicking |
| Filter sidebar (5 checkboxes + 3 groups) | - | -3 | 99 | Decision cost for someone in a hurry |
| All checkboxes pre-checked | + | +2 | 101 | Smart default |
| "Show N more" collapsed | + | +1 | 102 | Keeps page scannable |
| "Hybrid search" label | + | +1 | 103 | Subtle confidence signal |

**Screen 4: Concepts Explorer (103 → 125)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| Two-panel list + detail | + | +4 | 107 | No page loads, browse and read |
| Full definition in styled block | + | +6 | 113 | Meeting-ready insight — the payoff |
| "Appears in 4 sections" | + | +3 | 116 | Can dive deeper |
| Related concepts as chips | + | +3 | 119 | Connected understanding |
| Cross-book concept (purple) | + | +4 | 123 | Unexpected delight |
| Related annotation with personal note | + | +3 | 126 | Reminds of prior thinking |
| Filter bar (5 controls) | - | -2 | 124 | Visual weight, mostly ignorable |
| "Edit" link on definition | + | +1 | 125 | Sense of ownership |

### Interventions Needed

| Priority | Intervention | Current Impact | Expected Impact |
|----------|-------------|---------------|----------------|
| **Medium** | Auto-collapse filter sidebar until result count > 20 | -3 | 0 |
| **Low** | Add "Copy definition" button to concept detail | — | +2 (meeting-ready export) |

---

## Journey 4: AI Chat

**Persona:** Active Learner | **Start: 40** | **End: 76**

### Screen-by-Screen Scoring

**Screen 1: AI Button Access (40 → 45)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| "AI" button always visible in header | + | +3 | 43 | Discoverable, persistent |
| Purple accent | + | +1 | 44 | Visual distinction |
| Breadcrumb shows current chapter | + | +1 | 45 | Orientation |

**Screen 2: Thread List (45 → 50)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| Annotations/Ask AI tabs | - | -1 | 44 | Minor decision |
| "Reading Ch.3" context line | + | +2 | 46 | AI knows what you're reading |
| Existing threads with previews | + | +3 | 49 | Past conversations = saved progress |
| "+ New Thread" button | + | +1 | 50 | Clear affordance |

**Screen 3: New Thread — Context + Input (50 → 56)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| **Selected text context block** | **+** | **+5** | **55** | **Key moment — AI "sees" what confused you. Trust signal.** |
| Chapter attribution | + | +1 | 56 | Provenance builds confidence |
| "Ask about this book..." placeholder | + | +1 | 57 | No blank-page paralysis |
| Hint text (slightly redundant) | - | -1 | 56 | Minor clutter |

**Screen 4: AI Response (56 → 64)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| **Structured response (numbered list, bold terms)** | **+** | **+5** | **61** | **"Aha" moment — complex concept broken down** |
| Cited source from the book | + | +3 | 64 | Grounds answer, builds trust |
| Action row (Save/Copy/Regenerate) | + | +2 | 66 | User feels in control |
| Typing indicator (dots only) | - | -2 | 64 | No progress signal |

**Screen 5: Follow-up (64 → 71)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| Cross-chapter context badge | + | +4 | 68 | AI connects across chapters — feels intelligent |
| Conversation continuity | + | +3 | 71 | Feels like a real tutor |

**Screen 6: Save as Annotation (71 → 73)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| "Save as note" inline link | + | +3 | 74 | Insight becomes permanent, one click |
| No visible confirmation toast | - | -1 | 73 | Did it save? |

**Screen 7: Multi-Section Context (73 → 75)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| "+ Context" pill button | + | +2 | 75 | Discoverable, not intrusive |
| Section picker checkboxes | - | -2 | 73 | Decision: which chapters? |
| "3 selected" count | + | +1 | 74 | Feedback |
| Dismissible context chips | + | +2 | 76 | Visible, reversible |
| "Done" button | - | -1 | 75 | Extra tap |

**Screen 8: Mobile Bottom Sheet (75 → 76)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| Bottom sheet over dimmed reader | + | +2 | 77 | Context preserved |
| Drag handle | + | +1 | 78 | Intuitive physical metaphor |
| Thread cards with chapter tags | + | +2 | 80 | Scannable |
| Small touch targets (9-11px) | - | -3 | 77 | Fat-finger risk |
| Section picker replaces conversation | - | -1 | 76 | Disorienting |

### Interventions Needed

| Priority | Intervention | Current Impact | Expected Impact |
|----------|-------------|---------------|----------------|
| **High** | Add confirmation toast after "Save as note" | -1 (uncertainty) | +1 (reassurance) |
| **Medium** | Increase mobile touch targets to 14px minimum | -3 | -1 |
| **Medium** | Show progress bar during AI response, not just dots | -2 | 0 |
| **Low** | Add "AI-suggested chapters" default in section picker | -2 | 0 |

---

## Journey 5: Mobile Reading

**Persona:** Mobile Reader | **Start: 30** | **End: 74**

### Screen-by-Screen Scoring

**Screen 1: LAN Setup on Desktop (30 → 28)** -- CAUTION ZONE

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| Config toggle required | - | -4 | 26 | Must find settings, edit config |
| QR code generation | + | +3 | 29 | Visual, no URL typing |
| Optional token auth decision | - | -2 | 27 | Another decision |
| mDNS alternative | + | +1 | 28 | Fallback, but adds confusion |

**Screen 2: QR Scan to Library (28 → 33)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| QR scan lands directly in library | + | +4 | 32 | Instant payoff |
| No app install (web) | + | +3 | 35 | Zero friction vs App Store |
| Possible token prompt | - | -2 | 33 | One more gate |

**Screen 3: Mobile Library (33 → 41)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| Books already synced from desktop | + | +5 | 38 | Core value — no re-upload |
| List view with thumbnails + status | + | +2 | 40 | Scannable |
| Custom view tabs from desktop | + | +3 | 43 | "Currently Reading" gets you there fast |
| Filter dropdowns | - | -1 | 42 | Optional decisions |
| 5-tab bottom nav | - | -1 | 41 | "Concepts" unclear to casual reader |

**Screen 4: Mobile Reader Layout (41 → 53)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| Back arrow + chapter dropdown | + | +2 | 43 | Simple navigation |
| Original/Summary toggle | + | +4 | 47 | Core feature, one tap |
| Full-width content, 1.8 line-height | + | +3 | 50 | Comfortable |
| Labeled bottom action bar | + | +2 | 52 | Thumb-reachable |
| No tab bar in reader | + | +1 | 53 | Maximizes reading space |

**Screen 5: Summary Content (53 → 60)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| Eval banner | + | +2 | 55 | Trust signal |
| Concept chips (tappable) | + | +2 | 57 | Invites exploration |
| Bullet-point format | + | +3 | 60 | Easy mobile scanning |
| Highlighted terms | + | +1 | 61 | Visual anchoring |
| Preset selector dropdown | - | -1 | 60 | Extra decision for casual reader |

**Screen 6: Reader Settings (60 → 67)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| Full-screen modal with "Done" | + | +1 | 61 | Clear exit |
| Preset cards (one-tap) | + | +3 | 64 | No slider fiddling |
| Font/spacing sliders | + | +1 | 65 | Available, not forced |
| Background swatches (sepia/dark) | + | +2 | 67 | Night reading use case |
| Live preview | + | +1 | 68 | Immediate feedback |
| Content width slider (locked on mobile) | - | -1 | 67 | Non-functional control, confusing |

**Screen 7: Mobile Annotation (67 → 74)**

| Element | +/- | Score | Total | Notes |
|---------|-----|-------|-------|-------|
| Long-press triggers toolbar | + | +2 | 69 | Native-feeling |
| Bottom sheet with drag handle | + | +2 | 71 | Familiar pattern |
| Color-coded annotation cards | + | +2 | 73 | Visually distinct |
| "+ Add" button | + | +1 | 74 | Low friction |
| Cross-view indicators | + | +1 | 75 | Views linked |
| Two different bottom sheets | - | -1 | 74 | Could confuse |

### Interventions Needed

| Priority | Intervention | Current Impact | Expected Impact |
|----------|-------------|---------------|----------------|
| **Critical** | Auto-enable LAN with one confirmation prompt (not config edit) | -4 (config toggle) | -1 (one prompt) |
| **Medium** | Remove locked content-width slider on mobile | -1 | 0 |
| **Medium** | Collapse 5 bottom tabs to 4 (merge Concepts into Search) | -1 | 0 |

---

## Aggregated Findings

### Psych Score Visualization (approximate trajectory per journey)

```
Score
130│                                                          ╱ Search (125)
120│                                                        ╱
110│                                                      ╱
100│                                                    ╱
 90│                                    ╱── Reading (89)
 80│                                  ╱           ╱── AI Chat (76)
 70│                                ╱           ╱     ╱── Mobile (74)
 60│ Search start ──╱             ╱           ╱     ╱
 50│              ╱             ╱           ╱     ╱  ╱── Upload (46)
 40│ Read/AI ──╱╱             ╱           ╱     ╱  ╱
 30│ Mobile ──╱    ╲         ╱           ╱    ╱  ╱
 25│ Upload ──╱     ╲──────╱           ╱   ╱  ╱
 20│────────────────────────────────────────────── DANGER ZONE ──
   └──────────────────────────────────────────────────────────────
    Screen 1    2      3      4      5      6      7      8
```

### Top +Psych Elements (highest scoring across all journeys)

| Element | Score | Journey | Why It Works |
|---------|-------|---------|-------------|
| Instant grouped search results | +7 | Search | Answers appear before finishing typing |
| Concept definition panel | +6 | Search | Meeting-ready insight, the payoff |
| Cmd+K shortcut access | +6 | Search | Zero-navigation, muscle memory |
| "Start with Recommended Settings" CTA | +5 | Upload | Eliminates 3 wizard steps for low-intent users |
| Concept chips in summary | +5 | Reading | Key ideas surfaced visually, clickable |
| Visual reader preset cards | +5 | Reading | Actual rendering preview, one-click apply |
| Selected text context block in AI | +5 | AI Chat | AI "sees" what confused you — trust signal |
| Structured AI response | +5 | AI Chat | Complex concept broken down clearly |
| Books synced from desktop (mobile) | +5 | Mobile | Core value — no re-upload needed |
| Recent searches in palette | +5 | Search | May already see what they need |

### Top -Psych Elements (highest draining across all journeys)

| Element | Score | Journey | Why It Hurts |
|---------|-------|---------|-------------|
| **Surprise cost discovery at Step 6** | **-4** | **Upload** | **User didn't know this costs money. Worst moment.** |
| LAN config toggle requirement | -4 | Mobile | Must find settings, edit config |
| Annotation Link Dialog (full modal) | -4 | Reading | Heavy modal interrupts study flow |
| 5-step progress stepper | -3 | Upload | Intimidating for low-intent users |
| Eval detail expansion (5 categories) | -3 | Reading | QA dashboard, not a study tool |
| Filter sidebar on results page | -3 | Search | Decision cost for someone in a hurry |
| Mobile touch targets (9-11px) | -3 | AI Chat | Fat-finger risk, readability strain |
| ~8 minute processing wait | -3 | Upload | Long wait, no intermediate value |
| Preset choice overload (4 options + create) | -3 | Upload | "Which one am I?" for first-timers |

### Consolidated Interventions (Ranked by Impact)

| # | Intervention | Journey | Current | Expected | Priority |
|---|-------------|---------|---------|----------|----------|
| P1 | Move cost indication to library or Step 1 | Upload | -4 at Step 6 | -1 earlier | Critical |
| P2 | Auto-enable LAN with single prompt | Mobile | -4 at setup | -1 | Critical |
| P3 | Hide eval/retry under "Advanced" | Upload | -2 at Step 6 | 0 | High |
| P4 | Show first section summary during processing | Upload | -3 wait | +3 aha | High |
| P5 | Collapse eval to single trust badge | Reading | -6 total | -1 | High |
| P6 | Lighten Link Dialog to inline quick-link | Reading | -4 modal | -1 | High |
| P7 | Add "Save as note" confirmation toast | AI Chat | -1 | +1 | High |
| P8 | Reduce visible stepper to 3 steps | Upload | -3 | -1 | Medium |
| P9 | Increase mobile AI chat touch targets | AI Chat | -3 | -1 | Medium |
| P10 | Auto-collapse search filter sidebar | Search | -3 | 0 | Medium |
| P11 | Auto-select latest summary version | Reading | -2 | 0 | Medium |
| P12 | Show AI response progress bar (not just dots) | AI Chat | -2 | 0 | Medium |
| P13 | Remove locked content-width slider on mobile | Mobile | -1 | 0 | Low |
| P14 | Add "Copy definition" to concept detail | Search | — | +2 | Low |
| P15 | Reduce fonts from 8 to 4-5 with expansion | Reading | -2 | -1 | Low |

---

## Key Insight: The Psych Inversion Problem

The two lowest-scoring journeys (Upload: 46, Mobile: 74) share a pattern: **they front-load friction and back-load reward.** The user must push through configuration, decisions, and jargon before seeing any value.

The two highest-scoring journeys (Search: 125, Reading: 89) do the opposite: **they front-load reward and defer friction.** Cmd+K gives instant results. The reader shows content immediately. Configuration is optional and accessible but not required.

**Design principle**: Every journey should deliver its first +5 Psych moment within the first 2 screens. Currently:
- Search: Screen 2 (instant results) -- excellent
- Reading: Screen 1 (breadcrumb + chapter dots) -- good
- AI Chat: Screen 3 (context block) -- acceptable
- Mobile: Screen 3 (books synced) -- too late (setup friction precedes)
- Upload: Screen 3 (Quick Upload fork) -- acceptable, but only on fast path

The interventions P1 (early cost) and P2 (auto-LAN) directly address this by removing front-loaded friction.
