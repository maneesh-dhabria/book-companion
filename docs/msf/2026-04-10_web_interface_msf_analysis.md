# Book Companion Web Interface — User Motivation, Satisfaction & Friction Analysis

**Date:** 2026-04-10
**Analyzed against:** [V1 Web Interface Requirements](../requirements/2026-04-10_web_interface_v1_requirements.md)
**Wireframes reviewed:** [V2 Web Interface Wireframes](../wireframes/2026-04-10_v2_web_interface/README.md)
**Predecessor analysis:** [V1 CLI MSF Analysis (2026-04-01)](2026-04-01_user_msf_analysis.md)

---

## User Segments

The web interface broadens access beyond CLI-comfortable users. Four segments capture distinct usage modes with different needs, urgency, and friction tolerance.

| Segment | Description | When this mode activates |
|---------|-------------|------------------------|
| **A. The Mobile Reader** | Reads summaries and annotations on phone/tablet (couch, commute, bed). Wants comfortable reading, not complex operations. | Has processed books on desktop, now consuming on mobile via LAN. |
| **B. The Power Organizer** | Manages a growing library (10+ books). Creates views, tags, filters, presets. Values organization and findability. | Library has grown enough that "All Books" is unwieldy. Needs structure. |
| **C. The Active Learner** | Annotates heavily, links ideas across books, uses AI chat for comprehension. Treats books as study material. | Studying a book seriously — highlighting, asking questions, connecting concepts. |
| **D. The First-Upload User** | Just opened the web UI for the first time. Has zero books. Needs to understand the product and get value quickly. | Day 1 of web interface. May or may not have used the CLI before. |

---

## Segment A: The Mobile Reader

### Motivation

| Question | Analysis |
|----------|----------|
| What is the job? | Read book summaries and review annotations comfortably on a mobile device, away from the desk |
| How important? | Medium-high — this is the "consumption" side of a tool that's heavy on "production" (upload, summarize, organize happen on desktop) |
| How urgent? | Low-medium — usually leisure or study time, not time-critical |
| What else could be more important? | Social media, podcasts, Kindle reading, YouTube — all compete for the same "downtime reading" slot |
| Benefits of action? | Revisit knowledge on the go, make the processing investment pay off across contexts |
| Consequences of inaction? | Knowledge stays locked on the desktop; the "I'll review it later" never happens |
| Alternatives? | Export summaries as markdown and read in any notes app; use Kindle highlights + Readwise on phone |

### Friction Analysis

| Question | Analysis | Severity |
|----------|----------|----------|
| Will the user understand this product? | On mobile, yes — the bottom tab bar (Library, Search, Concepts, Notes, Settings) is familiar from any mobile app. The reader layout is clean. | LOW |
| When does the user need to decide to act? | When they want to read on their phone. The LAN setup is a one-time barrier. | MEDIUM |
| How complex is the decision to act? | **The LAN setup is the primary blocker.** User must: (1) open desktop Settings, (2) enable "Allow LAN Access", (3) acknowledge security warning, (4) scan QR code or type IP:port on phone. This is non-trivial for less technical users. | HIGH |
| What is the cost of a wrong decision? | Low — if LAN setup fails, they just can't access from phone. No data loss. | LOW |
| Do they understand their next action? | **After LAN setup, yes.** The mobile UI is intuitive. But reaching the LAN toggle requires navigating to Settings > General, which is not discoverable from the mobile device itself (chicken-and-egg: you need desktop to enable mobile access). | MEDIUM |
| How difficult is it to initiate? | Medium — requires both devices available simultaneously for QR scan. | MEDIUM |
| How difficult will they think it is? | If they see "LAN Access" in settings, they may assume it's a networking task and avoid it. The QR code helps reduce perceived difficulty. | MEDIUM |
| What else is going on? | Competing with easier consumption (podcasts, social media). If the setup takes more than 2 minutes, they may abandon. | HIGH |
| What do they stand to lose? | Nothing — but also nothing gained if they don't set it up. Low stakes = low motivation to push through friction. | LOW |
| How inconsistent with expectations? | **Mobile wireframes rename "Annotations" to "Notes"** in the bottom tab bar, while desktop calls it "Annotations." This terminology inconsistency may cause confusion. | MEDIUM |
| How much thought before acting? | Minimal once set up. The reader experience is straightforward. | LOW |

### Friction Points from Wireframe Walkthrough

| Screen/Step | Observation | Severity |
|-------------|-------------|----------|
| **Mobile Library** | Defaults to list view (good for mobile), but **drops Author, Eval, and Format filters** that exist on desktop. Users who created filtered views on desktop cannot reproduce them on mobile. | MEDIUM |
| **Mobile Library — Custom Views** | Desktop shows Notion-style custom view tabs. Mobile shows **different categories** ("All / Reading / Summarized / Archived") that appear to be status-based quick filters, NOT the user's saved views. **Users cannot access their custom desktop views on mobile.** | HIGH |
| **Mobile Reader — Bottom Action Bar** | Icons lack text labels (Aa, sparkle, chat bubble, ellipsis). The sparkle icon for AI and the chat bubble for annotations are **not self-explanatory** without labels. | MEDIUM |
| **Mobile Reader — Bottom Sheets** | The three snap points (30%, 50%, 90%) for annotation/AI sheets are well-designed. However, **no swipe-to-navigate between sections** is shown — users must open the chapter dropdown each time. | LOW |
| **Mobile Reader Settings** | Presented as full-screen modal (good). Simplified font options (System, Serif, Mono, OpenDyslexic) vs. desktop's 8+ fonts. **No "Reset to Default" option**, making it hard to undo experimentation. | LOW |
| **Mobile Search** | Full-screen search replacing the desktop command palette is appropriate. Filter chips replace the sidebar. Well adapted. | LOW |
| **Offline behavior** | Requirements state cached pages work offline (service worker) but new navigation fails with an error. **No offline indicator** is shown in wireframes — user may not know why things stopped working. | MEDIUM |

### Satisfaction Analysis

| Question | Analysis |
|----------|----------|
| Did it fulfill the promised job? | Partially. Reading summaries on mobile works well. But the inability to access custom views and reduced filtering means the mobile experience feels like a "lite" version, not full parity. |
| Did it live up to expectations? | If the user expects "same app on phone," the view/filter gaps will disappoint. If they expect "reading mode on phone," it meets expectations. |
| Did it generate happy hormones? | Reading your processed book summaries on the couch — yes. The reader experience with customizable fonts/backgrounds is satisfying. |
| Did it feel reassuring? | The QR code for setup is reassuring. The "no auth by default" warning may create anxiety about security on shared networks. |
| Did it raise prestige/self-esteem? | Having a personal knowledge library accessible on your phone feels premium. |
| Did it make them feel smart? | Yes — reviewing annotations and concepts on the go reinforces the "I understand this deeply" feeling. |

### Recommendations for Segment A

| # | Recommendation | Impact | Effort |
|---|---------------|--------|--------|
| A1 | **Sync custom views to mobile**: Mobile should show the same saved view tabs as desktop, not a separate set of status-based filters. Views are already persisted in DB; just render them. | HIGH | LOW |
| A2 | **Add text labels to mobile bottom action bar**: Show "Settings", "AI", "Notes", "More" below icons. Touch targets already meet 44px minimum; adding 10px labels improves discoverability significantly. | MEDIUM | LOW |
| A3 | **Add offline indicator**: When LAN connection is lost, show a persistent top banner "Offline — showing cached content" instead of only erroring on navigation. | MEDIUM | LOW |
| A4 | **Simplify LAN setup with guided flow**: When user first opens Settings > General, show a step-by-step "Set up mobile access" card with numbered steps + QR code, not just a toggle buried among other settings. | MEDIUM | LOW |
| A5 | **Consistent terminology**: Use "Annotations" everywhere (desktop and mobile), or use "Notes" everywhere. Don't mix them. | LOW | LOW |

---

## Segment B: The Power Organizer

### Motivation

| Question | Analysis |
|----------|----------|
| What is the job? | Organize a growing library into meaningful collections, quickly find and filter books, manage presets and views for different use cases |
| How important? | High — without organization, a 20+ book library becomes a pile, not a system |
| How urgent? | Builds gradually — not urgent for any single session, but critical cumulatively |
| What else could be more important? | Actually reading and studying the books (Segment C). Organization is a means, not an end. |
| Benefits of action? | O(1) access to the right book/section instead of O(n) scrolling. Views for different contexts (work, study, personal). |
| Consequences of inaction? | Library becomes a graveyard of processed books the user never revisits. The knowledge compounding value proposition fails. |
| Alternatives? | Notion/Obsidian for manual organization; Calibre for ebook library management; filesystem folders |

### Friction Analysis

| Question | Analysis | Severity |
|----------|----------|----------|
| Will the user understand this product? | The Notion-style views are a pattern power users already know. The filter row (Tags, Status, Author, Eval, Format) is clear. **Three display modes (grid/list/table)** give flexibility. | LOW |
| When does the user need to decide to act? | When "All Books" becomes too long to scan. Typically at 8-10 books. | LOW |
| How complex is the decision to act? | **Creating a view is well-designed**: filter first, then save. The auto-generated name from active filters ("completed + Psychology") reduces cognitive load. | LOW |
| Cost of wrong decision? | Low — views can be deleted and recreated easily. | LOW |
| Do they understand their next action? | The "+ New View" tab is visible but subtle. **The unsaved changes indicator (dot on tab) is elegant** but the "click dot to save or reset" interaction may not be discoverable.  | MEDIUM |
| How difficult to initiate? | Easy — filters are always visible, one click each. | LOW |
| How difficult will they think it is? | The view system looks simple (tabs) but the full capabilities (column configuration in table mode, drag-to-reorder tabs) are hidden. This is good progressive disclosure. | LOW |
| What else is going on? | Organizing is maintenance work — users do it between reading sessions. Needs to be fast and not feel like a chore. | MEDIUM |
| What do they stand to lose? | Deleting a view is permanent (with confirmation). Accidentally deleting a complex view would be frustrating. | LOW |
| How inconsistent with expectations? | Users familiar with Notion will expect the view system to work similarly. The design closely matches Notion's pattern. | LOW |
| Thought before acting? | Low for simple filters. Medium for deciding on view organization strategy. | LOW |

### Friction Points from Wireframe Walkthrough

| Screen/Step | Observation | Severity |
|-------------|-------------|----------|
| **Library — Filter Row** | Five filter dropdowns + sort + display mode toggle in one row. On tablet widths (768-1023px), this row may overflow or feel cramped. **No wireframe shows the tablet filter layout.** | MEDIUM |
| **Library — Table Mode** | The view switcher shows a table icon but **no wireframe shows the actual table view**. Column visibility toggle, drag-to-reorder columns, and column sorting are specified in requirements but not validated in wireframes. | MEDIUM |
| **Library — View Tab Management** | Right-click context menu for view actions (Rename, Duplicate, Set as default, Reorder, Delete) is desktop-only. **No equivalent on mobile or touch devices** (long-press not specified). | MEDIUM |
| **Library — Empty States** | Requirements specify three empty states (no books, no filter matches, view has no books). **None are wireframed.** First-time users will see an empty library with no visual guidance. | HIGH |
| **Library — Book Card** | Grid cards pack 6 data points (cover, title, author, tags, status, eval, section count). This is dense but well-organized in the wireframe. Tag pills max at 3 with "+N" overflow — good. | LOW |
| **Library — Bulk Operations** | Right-click context menu on book cards includes Summarize, Evaluate, Export, Delete. But **no multi-select capability** for bulk operations across books (e.g., "tag these 5 books", "delete these 3 books"). | MEDIUM |
| **Settings — Preset Management** | List/detail layout mirrors Concepts Explorer pattern (consistent). System presets are read-only with "Duplicate as User Preset" — clear mental model. Well-designed. | LOW |

### Satisfaction Analysis

| Question | Analysis |
|----------|----------|
| Did it fulfill the promised job? | Yes — the view system, filter row, and three display modes provide strong organizational tools for a growing library. |
| Did it live up to expectations? | Meets expectations for Notion-like view management. Exceeds expectations for a "personal tool" — this is surprisingly sophisticated. |
| Did it generate happy hormones? | Switching between a "Psychology Reading" view and a "Technical Books" view and seeing curated collections — yes, satisfying. |
| Did it feel reassuring? | The unsaved changes dot and auto-generated view names provide good feedback. The "cannot delete last view" guard rail is reassuring. |
| Did it raise prestige/self-esteem? | Having a well-organized personal library visible as a polished grid of book cards — yes. |
| Did it make them feel smart? | The view system rewards organizational effort. "I set up views for my different interests" feels smart. |

### Recommendations for Segment B

| # | Recommendation | Impact | Effort |
|---|---------------|--------|--------|
| B1 | **Wireframe the table view**: Table mode is specified in requirements but not wireframed. Given that power organizers are the primary table mode users, this needs visual validation. | HIGH | LOW |
| B2 | **Add multi-select for bulk book operations**: Checkbox on book cards (visible on hover or via "Select" mode toggle). Bulk actions: Tag, Delete, Export, Summarize. Critical for 20+ book libraries. | HIGH | MEDIUM |
| B3 | **Wireframe the empty library state**: First-time users (Segment D) and power organizers filtering to zero results both need clear empty states with CTAs. This is a high-visibility gap. | HIGH | LOW |
| B4 | **Specify tablet filter layout**: The 5-filter + sort + display row needs explicit tablet adaptation — possibly a scrollable row or collapsible filter group. | MEDIUM | LOW |
| B5 | **Add "Undo delete" for views**: Instead of just a confirmation dialog, offer a 5-second undo toast after view deletion (consistent with section deletion pattern in upload flow). | LOW | LOW |

---

## Segment C: The Active Learner

### Motivation

| Question | Analysis |
|----------|----------|
| What is the job? | Deeply engage with book content — highlight key passages, take notes, ask AI questions, link ideas across books, build a connected knowledge base |
| How important? | Very high — this is the "make it my own" dimension that transforms summaries from AI output into personal knowledge |
| How urgent? | Medium — study sessions are planned, not reactive. But within a session, flow state matters — friction breaks concentration. |
| What else could be more important? | Actually reading the source material (which the tool should facilitate, not replace) |
| Benefits of action? | Persistent, searchable annotations and concept connections that compound across books and time |
| Consequences of inaction? | Knowledge remains passive ("I read it") instead of active ("I understood, connected, and can recall it") |
| Alternatives? | Kindle + Readwise ($8/mo), Notion manual notes, Obsidian with book notes, physical marginalia |

### Friction Analysis

| Question | Analysis | Severity |
|----------|----------|----------|
| Will the user understand this product? | The reader with annotation sidebar is familiar (Kindle, Google Docs). The AI chat sidebar is novel but the chat pattern is well-understood. **Concept chips in summaries** are a unique feature that needs learning. | MEDIUM |
| When does the user decide to act? | In the moment — while reading, they see something worth annotating. Speed matters. | HIGH |
| How complex is the decision? | Low for highlights (one click). Medium for notes (click + type). High for linking (search + select target). | VARIES |
| Cost of wrong decision? | Low — annotations can be edited and deleted. But **no undo is shown after highlight creation**, and **no confirmation for annotation deletion**. | MEDIUM |
| Do they understand next action? | The floating toolbar (Highlight, Note, Ask AI, Link, Copy) is clear on desktop. On mobile, **text selection via long-press is standard** but the toolbar may overlap with native OS selection handles. | MEDIUM |
| How difficult to initiate? | **Desktop: Excellent.** Select text → floating toolbar → one click. Minimal friction. **Mobile: Good.** Long-press → toolbar, but larger touch targets needed (specified at 44px — good). | LOW |
| How difficult will they think it is? | The inline annotation workflow looks effortless. The AI chat looks inviting. Cross-book linking may look complex. | LOW-MEDIUM |
| What else is going on? | They're in a reading/study session. **Any friction that breaks reading flow is magnified.** Modal dialogs, page navigations, and loading delays are especially harmful. | HIGH |
| What do they stand to lose? | Time invested in annotations. **No export/backup of annotations alone** is shown in the reader — only on the global Annotations page. | LOW |
| How inconsistent with expectations? | **Annotations on summaries are separate from annotations on original content** (different `content_type`). This is technically correct but may surprise users who expect their highlights to appear in both views. | HIGH |
| Thought before acting? | For highlights: zero thought (impulsive, good). For AI questions: some thought to formulate. For linking: significant thought to identify the connection target. | VARIES |

### Friction Points from Wireframe Walkthrough

| Screen/Step | Observation | Severity |
|-------------|-------------|----------|
| **Reader — Text Selection Toolbar** | Five actions (Highlight, Note, Ask AI, Link, Copy). "Ask AI" is visually differentiated (purple). Good hierarchy. But **toolbar positioning when text is near the top of viewport** (flip below) is mentioned in requirements but not wireframed. | LOW |
| **Reader — Annotation Sidebar** | Annotations are ordered by text position (`text_start`) — good. **Margin alignment** between sidebar annotations and content highlights is specified but would be technically challenging and is not wireframed. | MEDIUM |
| **Reader — Annotations on Summary vs Original** | Requirements state annotations have `content_type` = `section_content` or `section_summary`. Annotations made on summaries **do not appear when reading the original** and vice versa. **This is not communicated to the user anywhere in the wireframes.** Users will highlight text in a summary, switch to Original view, and wonder where their highlight went. | HIGH |
| **AI Chat — Thread Management** | Thread list shows title, message count, date, preview. **No way to delete a thread** is shown in wireframes (requirements mention delete but it's not in the UI). Thread list could grow unwieldy. | MEDIUM |
| **AI Chat — Save as Note** | Each AI response has "Save as note" action. This creates a freeform annotation on the current section. Good. But **no feedback shows what "saved" means** — does it go to the Annotations sidebar? Does a badge update? | MEDIUM |
| **AI Chat — Multi-section Context** | AI can reference multiple sections. Cross-section references show clickable links. But **how does the user trigger a multi-section question?** The context always defaults to the current section. No UI for "ask about chapters 3-7." | MEDIUM |
| **Concept Chips in Summary** | Clicking a concept shows tooltip with definition + related concepts. Good. But **concept chips are only in summary view, not original view.** Active learners reading originals get no concept overlays. | MEDIUM |
| **Cross-Book Annotation Linking** | The Link dialog requires searching for a target annotation. But **the search scope is unclear** — does it search all annotations across all books? How does the user find the right one in a large library? | HIGH |
| **Global Annotations Page** | Well-designed with filters and grouping. **But no "create annotation" affordance** exists on this page — you can only create annotations while reading. This is limiting for users who want to add retrospective notes. | MEDIUM |
| **Concepts Explorer — Term Editing** | The concept editor locks the Term field as read-only. **Users cannot correct typos** in LLM-extracted concept names. Only the definition is editable. | MEDIUM |
| **Editing — Summary Editing** | Inline rich-text editing with formatting toolbar. Clear `user_edited` flag notice. **But no version history** — once edited, the original AI summary is overwritten (no "see AI version" option). | MEDIUM |
| **Editing — No undo for merge/split** | Section merge and split have Confirm buttons but **no undo**. These are destructive operations affecting summaries and eval traces downstream. | HIGH |

### Satisfaction Analysis

| Question | Analysis |
|----------|----------|
| Did it fulfill the promised job? | Mostly yes. The annotation creation flow is smooth. AI chat is well-integrated. Concept discovery is a standout feature. But annotation isolation between original/summary content, and the difficulty of cross-book linking, create gaps. |
| Did it live up to expectations? | The reader + sidebar layout meets "Kindle-like" expectations. The AI chat sidebar exceeds expectations. Concept chips are a novel delight. |
| Did it generate happy hormones? | Highlighting text and immediately asking AI "explain this" — peak flow state. Seeing concept connections across books — discovery dopamine. |
| Did it feel reassuring? | The eval banner on summaries builds trust. But the lack of undo on destructive edits (merge/split) creates anxiety. |
| Did it raise prestige/self-esteem? | Building a richly annotated, AI-augmented knowledge base from your reading — very high prestige feeling. |
| Did it make them feel smart? | Concept chips make connections visible that the user might have missed. AI chat fills comprehension gaps. This is the "feel smart" segment. |

### Recommendations for Segment C

| # | Recommendation | Impact | Effort |
|---|---------------|--------|--------|
| C1 | **Show annotation visibility scope**: When creating an annotation in Summary view, show a subtle indicator: "This annotation is on the summary. Switch to Original to annotate source text." Prevent the "where did my highlight go?" moment. | HIGH | LOW |
| C2 | **Add undo for section merge/split**: After confirming a merge or split, show a 10-second undo toast. The operation should be reversible during this window (keep original sections in a soft-delete state). | HIGH | MEDIUM |
| C3 | **Improve cross-book linking UX**: The Link dialog should (a) show recent annotations first, (b) allow filtering by book, (c) show a preview of the target annotation before confirming. The current "search for an annotation" pattern is too vague for large libraries. | HIGH | MEDIUM |
| C4 | **Allow concept term editing**: Unlock the Term field in the concept editor. If a user corrects a concept name, mark it `user_edited` like definitions. Typos in LLM-extracted terms are common. | MEDIUM | LOW |
| C5 | **Show concepts in Original view too**: If concept terms appear in the original text, show subtle underline/chip styling (less prominent than summary view). Helps Active Learners who prefer reading originals. | MEDIUM | MEDIUM |
| C6 | **Add "Ask about multiple sections" UI**: In the AI chat, add a "+ Add context" button that lets users select additional sections (checkbox list from TOC). This enables cross-chapter questions. | MEDIUM | MEDIUM |
| C7 | **Preserve original AI summary after user edit**: When a user edits a summary, save the edit as a new version rather than overwriting. Show "AI version" and "My version" in the version selector. | MEDIUM | LOW |
| C8 | **Add undo/confirmation for annotation deletion**: Show confirmation dialog or 5-second undo toast when deleting annotations. | LOW | LOW |
| C9 | **Add "Add note" button on global Annotations page**: Allow creating freeform annotations (for a specific book/section) from the global page, not just while reading. | LOW | LOW |

---

## Segment D: The First-Upload User

### Motivation

| Question | Analysis |
|----------|----------|
| What is the job? | Upload their first book and see the tool deliver value. Validate that the web UI is worth using. |
| How important? | Low — they're exploring, not committed. The web UI is a new interface for an existing tool OR a completely new user. |
| How urgent? | Not urgent. They're trying it out. If friction is high, they'll close the tab. |
| What else could be more important? | Almost anything. A new user's attention is the scarcest resource. Every extra click is a chance to abandon. |
| Benefits of action? | See a book transformed into a structured, searchable, AI-augmented knowledge artifact |
| Consequences of inaction? | None. They'll just continue reading books the way they always have. |
| Alternatives? | ChatGPT/Claude direct (paste chapters, free), Blinkist ($15/mo, instant), Shortform ($25/mo, high quality), do nothing |

### Friction Analysis

| Question | Analysis | Severity |
|----------|----------|----------|
| Will the user understand this product? | **The empty library is the first thing they see**, and the requirements specify an empty state with illustration + "Upload your first book" button. Good. But **this empty state is not wireframed**, so the actual experience is unvalidated. | HIGH |
| When do they need to decide? | Right now — they have the app open and 30 seconds of attention. | CRITICAL |
| How complex is the decision? | The upload flow is a **5-step wizard** (Upload, Metadata, Structure Review, Preset Selection, Processing). For a first-time user, this is daunting. They don't know what "presets" or "structure review" mean. | HIGH |
| Cost of wrong decision? | Low technically (can delete and re-upload). But **processing costs real money** (Claude API tokens) and this cost is not shown anywhere in the upload flow or the web UI. | HIGH |
| Do they understand their next action? | If the empty state has a clear "Upload" CTA, yes. The drag-and-drop zone in Step 1 is intuitive. | LOW |
| How difficult to initiate? | **Easy** — drag a file or click "Browse." The entry point is good. | LOW |
| How difficult will they think it is? | After Step 1 (upload), they see Step 2 (metadata — fine), then Step 3 (Structure Review — **potentially overwhelming**). 38 sections with quality warnings, merge/split options, section type dropdowns... a first-time user doesn't know if they should edit anything. | HIGH |
| What else is going on? | They're evaluating the tool. Every moment of confusion is a "maybe I'll come back later" (= never). | CRITICAL |
| What do they stand to lose? | Time + LLM processing cost (unknown amount). | MEDIUM |
| How inconsistent with expectations? | Expectations: "upload a book, get a summary." Reality: 5-step wizard with structure review and preset selection. This exceeds expectations in complexity. | HIGH |
| Thought before acting? | Step 1-2: zero thought (upload + confirm metadata). Step 3: "Should I edit the sections?" Step 4: "Which preset should I pick?" Both require domain knowledge the user doesn't have yet. | HIGH |

### Friction Points from Wireframe Walkthrough

| Screen/Step | Observation | Severity |
|-------------|-------------|----------|
| **Empty Library** | Not wireframed. The first screen a new user sees has no visual validation. Requirements specify illustration + CTA, but the tone, messaging, and guidance are undefined. | HIGH |
| **Upload Step 1** | Clean drag-and-drop zone with format info. Good. **But no indication of what happens next** (how many steps, how long processing takes, what it costs). | MEDIUM |
| **Upload Step 2 (Metadata)** | Auto-populated fields are excellent — reduces friction. Tags are optional. Good defaults. | LOW |
| **Upload Step 3 (Structure Review)** | **Most problematic step for first-time users.** Shows 38 sections with quality warnings (stub sections, empty sections, very long sections). Actions include merge, split, delete, reorder, change type. A new user has no context for these decisions. **The "Save without processing" escape hatch is good** but it's phrased as an alternative, not as "skip this step." | HIGH |
| **Upload Step 4 (Preset Selection)** | Preset cards show names like "balanced", "practitioner_bullets", "academic". Descriptions help, but **a first-time user doesn't know which preset matches their needs.** No "Recommended for first-time use" badge or default selection guidance. | HIGH |
| **Upload Step 5 (Processing)** | Redirects to Book Detail with progress card. **Completed sections are immediately browsable** — this is the V1 CLI recommendation A3 implemented! Good. But **no estimated time shown** in the wireframe (recommended in CLI MSF as A4). | MEDIUM |
| **Mobile Upload** | Wizard compressed to 3 steps (File, Details, Options). This is actually **better for first-time users** — fewer decision points. But the desktop/mobile step mismatch may confuse cross-device users. | MEDIUM |
| **Processing Cost** | **Not shown anywhere** in the upload flow, settings, or processing view. The V1 CLI MSF flagged this as a key friction point (D2/F6). Still unaddressed in the web interface. | HIGH |

### Satisfaction Analysis

| Question | Analysis |
|----------|----------|
| Did it fulfill the promised job? | Depends on whether the user persists through the 5-step wizard. If they reach the processing stage and see their first section summary, YES — strong "aha" moment. |
| Did it live up to expectations? | If they expected "drag file, get summary": NO, the wizard has too many intermediate steps. If they expected a book management tool: YES, the polish is impressive. |
| Did it generate happy hormones? | The first completed section summary appearing while processing is still running — YES. Seeing concept chips light up — YES. But these moments are gated behind 5-8 minutes of wizard + processing time. |
| Did it feel reassuring? | The step indicator (numbered circles with progress) is reassuring. Quality warnings in Structure Review may create anxiety ("Is my book broken?"). |
| Did it raise prestige/self-esteem? | After processing completes and they see their book in the library with a cover image, summary, eval score — yes, strong. |
| Did it make them feel smart? | The preset selection step may make them feel dumb ("I don't know what 'practitioner_bullets' means"). The final result (summarized, evaluated book) makes them feel smart. |

### Recommendations for Segment D

| # | Recommendation | Impact | Effort |
|---|---------------|--------|--------|
| D1 | **Add a "Quick Upload" fast path**: For first-time users, offer a 2-step flow: (1) Upload file, (2) "Start with recommended settings" button that uses the default preset and skips structure review. Advanced users can still use the full 5-step wizard. | HIGH | MEDIUM |
| D2 | **Show estimated processing time and cost**: After parsing (Step 2), show "Estimated: ~8 minutes, ~$1.50 in API usage (15 sections)". Addresses the "opaque cost" problem carried over from V1 CLI. | HIGH | LOW |
| D3 | **Wireframe the empty library state**: This is the most critical first impression screen. Design it with: welcome message, 3-step "how it works" illustration, "Upload your first book" CTA, supported formats, and estimated processing cost for a typical book. | HIGH | LOW |
| D4 | **Mark a recommended preset**: In Step 4 (Preset Selection), visually distinguish one preset as "Recommended" or "Best for most books" (e.g., "balanced" preset with a star badge). Eliminates the "which one?" paralysis. | HIGH | LOW |
| D5 | **Soften Structure Review for first-time users**: If no quality warnings exist, auto-advance past Step 3 (or show a dismissible "Everything looks good! You can review section structure later." card). Only show the full structure editor when there are actual issues. | MEDIUM | MEDIUM |
| D6 | **Unify wizard step count across devices**: Either use 5 steps on both desktop and mobile, or clearly communicate that mobile combines steps ("Step 2: Details & Structure"). The 5-vs-3 mismatch is confusing. | MEDIUM | LOW |

---

## Cross-Segment Aggregated Findings

### Top Friction Points (by severity across segments)

| # | Friction | Affected Segments | Severity |
|---|---------|-------------------|----------|
| F1 | **No processing cost visibility** — users don't know what summarizing a book costs in API usage | D, A | CRITICAL |
| F2 | **5-step upload wizard overwhelming for first-time users** — Structure Review and Preset Selection require domain knowledge | D | HIGH |
| F3 | **Annotations invisible across Original/Summary views** — users will lose track of highlights when toggling | C | HIGH |
| F4 | **Empty library state not wireframed** — first impression screen is unvalidated | D, B | HIGH |
| F5 | **Custom views don't sync to mobile** — mobile shows different filter categories than desktop views | A, B | HIGH |
| F6 | **No undo for destructive section operations** (merge/split) | C, D | HIGH |
| F7 | **Cross-book annotation linking is too vague** — search-based target selection doesn't scale | C | HIGH |
| F8 | **Table view not wireframed** — power organizers' preferred mode is unvalidated | B | MEDIUM |
| F9 | **Mobile bottom bar icons lack labels** — AI and Annotations buttons not self-explanatory | A | MEDIUM |
| F10 | **No estimated processing time shown during upload or processing** | D, A | MEDIUM |
| F11 | **"Annotations" vs "Notes" terminology inconsistency** between desktop and mobile | A, C | MEDIUM |
| F12 | **Concept term names not editable** — can't fix LLM extraction typos | C | MEDIUM |
| F13 | **No recommended preset indicator for first-time users** | D | MEDIUM |

### Top Satisfaction Opportunities (already strong)

| # | Satisfaction Driver | Segments | Strength |
|---|-------------------|----------|----------|
| S1 | **Concept chips in summaries** — clickable terms with definitions and cross-references are a novel delight | C, B | VERY HIGH |
| S2 | **AI chat sidebar integrated with reader** — ask questions about what you're reading without leaving context | C, A | VERY HIGH |
| S3 | **Customizable reader settings with live preview** — visual presets, 8+ fonts, custom colors, WCAG contrast | A, C | HIGH |
| S4 | **Real-time processing with browsable completed sections** — don't wait for 100% to start reading | D, C | HIGH |
| S5 | **Notion-style library views** — sophisticated organization that rewards investment | B | HIGH |
| S6 | **Text selection floating toolbar** — smooth highlight/note/AI flow in one gesture | C | HIGH |
| S7 | **Eval banner building trust in summaries** — "16/16 passed" creates confidence in AI output quality | C, D | HIGH |
| S8 | **QR code for mobile LAN setup** — reduces a networking task to a camera scan | A | MEDIUM |

### Top Motivation Blockers

| # | Blocker | Detail |
|---|---------|--------|
| M1 | **First-time value is gated behind a 5-step wizard** | Unlike Blinkist (one-tap access), the upload wizard demands multiple decisions before delivering value. The "Quick Upload" fast path (D1) addresses this. |
| M2 | **Cost is invisible** | Users don't know if processing a book costs $0.50 or $50. This uncertainty may prevent them from even starting. Blinkist/Shortform have fixed subscription costs — predictable. |
| M3 | **Mobile experience feels like a "lite" version** | Custom views, advanced filters, and some editing features are desktop-only. Mobile readers may feel like second-class users. |
| M4 | **Organization investment has no immediate payoff** | Creating views and tags only pays off when the library grows. For 1-3 books, it's overhead. The tool needs to **nudge** organization at the right moment, not front-load it. |

### Cross-Cutting Wireframe Gaps

| # | Gap | Affected Screens | Impact |
|---|-----|-----------------|--------|
| G1 | **No loading/skeleton states shown** in any wireframe | Reader, Library, Search, Processing | Users get no feedback during async data loads |
| G2 | **No error states shown** beyond upload failures | All screens | Network errors, server crashes, and LLM failures need UI treatment |
| G3 | **No confirmation/undo patterns** for destructive actions | Annotations delete, Section merge/split, View delete | Data loss risk without user awareness |
| G4 | **No onboarding or empty states** for Annotations, Concepts pages | Annotations, Concepts Explorer | First-time visitors to these pages see unexplained empty screens |
| G5 | **Eval detail expansion not wireframed** | Book Detail reader | "View eval details" link leads to an undesigned destination |

---

## Prioritized Recommendations

Combining all segment-specific recommendations, ranked by impact and cross-segment value:

### Must Address (High impact, affects core value proposition)

| # | Recommendation | Source | Addresses |
|---|---------------|--------|-----------|
| **R1** | **Show processing cost estimates** in upload flow and processing view ("~$1.50 for 15 sections") | D2 | F1, M2 |
| **R2** | **Add a "Quick Upload" 2-step fast path** for first-time users (upload → start with defaults) | D1 | F2, M1 |
| **R3** | **Show annotation content-type scope** when creating annotations on Summary vs Original, and indicate that highlights only appear in the view where they were created | C1 | F3 |
| **R4** | **Wireframe the empty library state** with welcome message, how-it-works illustration, CTA, and cost guidance | D3 | F4, G4 |
| **R5** | **Sync custom views to mobile** — render the same saved view tabs on both platforms | A1 | F5, M3 |
| **R6** | **Add undo for section merge/split operations** (10-second toast with undo action) | C2 | F6, G3 |
| **R7** | **Improve cross-book linking UX** with recent annotations, book filter, and preview before confirm | C3 | F7 |

### Should Address (Medium impact, improves key flows)

| # | Recommendation | Source | Addresses |
|---|---------------|--------|-----------|
| **R8** | **Mark a recommended preset** ("Best for most books") in preset selection step | D4 | F13, M1 |
| **R9** | **Wireframe table view mode** for library page | B1 | F8 |
| **R10** | **Add text labels to mobile bottom action bar** icons | A2 | F9 |
| **R11** | **Show estimated processing time** after parsing and during progress tracking | D6 (related to A4 from CLI MSF) | F10 |
| **R12** | **Consistent terminology**: Pick "Annotations" or "Notes" and use it everywhere | A5 | F11 |
| **R13** | **Allow concept term editing** (not just definition editing) | C4 | F12 |
| **R14** | **Soften Structure Review for first-time users** — auto-advance when no quality warnings | D5 | F2 |
| **R15** | **Add multi-select for bulk book operations** in Library | B2 | — |
| **R16** | **Add "Ask about multiple sections" UI** in AI chat | C6 | — |

### Nice to Have (Lower impact, polish)

| # | Recommendation | Source | Addresses |
|---|---------------|--------|-----------|
| **R17** | **Add offline indicator banner** on mobile when LAN connection drops | A3 | — |
| **R18** | **Preserve original AI summary after user edit** as a version | C7 | — |
| **R19** | **Add confirmation/undo for annotation deletion** | C8 | G3 |
| **R20** | **Add "Add note" button on global Annotations page** | C9 | — |
| **R21** | **Show concepts in Original view** (subtle styling) | C5 | — |
| **R22** | **Simplify LAN setup with guided flow card** in Settings | A4 | — |
| **R23** | **Add loading/skeleton states** across all screens | — | G1 |
| **R24** | **Wireframe eval detail expansion** in Book Detail reader | — | G5 |
| **R25** | **Unify wizard step count** across desktop (5) and mobile (3) | D6 | — |

---

## Key Insight: The "Wizard Wall" Problem

The V1 CLI MSF identified the **"Setup Wall"** as the critical first-time friction. The web interface elegantly solves the installation/dependency problem (it's just a browser tab), but **replaces it with a "Wizard Wall"** — a 5-step upload flow that demands decisions the user isn't equipped to make yet.

> **The first-time experience should have exactly TWO decision points: (1) which file to upload, and (2) "Start" to begin processing.**

Everything else (metadata review, structure editing, preset selection) should either use smart defaults or be deferrable. The requirements already specify "Save without processing" at Step 3 — this same philosophy should extend to a "use recommended settings" fast path that skips Steps 3 and 4 entirely for first-time users.

The web interface's core UX innovation over the CLI — **browsable completed sections during processing** — is the right "aha moment." The goal is to get users to that moment as fast as possible. Every wizard step between "drop file" and "see your first summary" is friction against the product's strongest satisfaction driver.

## Comparison with V1 CLI MSF Findings

| V1 CLI Issue | Web Interface Status |
|-------------|---------------------|
| **Heavy setup before first value (F1)** | **RESOLVED** — web UI eliminates dependency installation. Browser tab = ready. |
| **No quick summary mode (F2)** | **PARTIALLY ADDRESSED** — completed sections are browsable during processing, but no "book-level summary first" option exists. |
| **No way to edit summaries/concepts (F3)** | **RESOLVED** — inline editing with `user_edited` flag is well-designed. Concept term editing still locked (R13). |
| **Cross-book linking unspecified (F4)** | **ADDRESSED BUT NEEDS UX WORK** — Link dialog exists but scales poorly (R7). |
| **Annotations hard to create in CLI (F5)** | **RESOLVED** — text selection + floating toolbar is excellent. |
| **Processing cost opaque (F6)** | **STILL UNADDRESSED** — no cost visibility in web UI (R1). |
| **No search within annotations (F7)** | **RESOLVED** — global Annotations page with search + full search includes annotations. |
| **No demo/sample output (F8)** | **PARTIALLY ADDRESSED** — web UI is more visually appealing, but empty library state still needs design (R4). |
