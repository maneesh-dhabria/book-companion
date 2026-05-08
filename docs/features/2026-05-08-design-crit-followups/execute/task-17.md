---
task_number: 17
task_name: "T17: SummaryTOCRail + FAB + metadata"
task_goal_hash: 067c7e93554d5f6f40cd566807527d472607844d5666e7a2f148b934029e39e3
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T18:25:00Z
completed_at: 2026-05-08T18:42:00Z
files_touched:
  - frontend/src/components/book/SummaryTOCRail.vue
  - frontend/src/components/book/BackToTopFab.vue
  - frontend/src/components/book/SummaryMetadataStrip.vue
  - frontend/src/components/book/BookSummaryTab.vue
  - frontend/src/components/app/AppShell.vue
  - frontend/src/components/book/__tests__/SummaryTOCRail.spec.ts
  - frontend/src/components/reader/MarkdownRenderer.vue
  - frontend/src/utils/markdownAnchors.ts
---

# T17: SummaryTOCRail + BackToTopFab + SummaryMetadataStrip (FR-C06..C12)

## Outcome
- **`@/utils/markdownAnchors.ts`** — extracted `slugify` + `installHeadingAnchorRuler(md)` from MarkdownRenderer (T16) into a shared util so SummaryTOCRail and MarkdownRenderer compute identical heading ids. MarkdownRenderer now imports the helper instead of inlining the ruler.
- **`SummaryTOCRail.vue`** — sticky `<nav class="toc-rail">` extracts h2/h3 headings via DOMParser. Accepts either `html` (pre-rendered) or `content` (markdown source); markdown path uses its own `MarkdownIt` with the same slug ruler so ids match the renderer's output. IntersectionObserver highlights the active entry on scroll. Falls back to a single "Top" item when no headings exist.
- **`BackToTopFab.vue`** — fixed-position chip-styled button, visible only when `window.scrollY > window.innerHeight`. Uses `bottom: calc(var(--playbar-height, 0px) + 1.5rem)` so it offsets above the Playbar.
- **`SummaryMetadataStrip.vue`** — renders `Preset: {x} · Generated: {relTime} · Eval: {pass}/{total} ({pct}%)`. Each cell hides if its data is unavailable.
- **`BookSummaryTab.vue`** — populated state restructured: metadata strip above the body, then a `book-summary-tab__layout` grid that switches from `1fr` to `1fr 16rem` at `min-width: 1024px`. Below `lg`: TOC inside an open `<details>` "Outline" expander above markdown. Above `lg`: TOC in `<aside class="book-summary-tab__rail">` to the right; the details element is hidden.
- **`AppShell.vue`** — sets `:style="{ '--playbar-height': ttsPlayer.isActive ? '84px' : '0px' }"` on `.app-shell` so any descendant FAB picks up the correct offset. Toggles dynamically when TTS activates/deactivates.

## Plan deviations
- Plan §T17 step 4 said set `--playbar-height` on `:root`. I set it on `.app-shell` instead. Same effect for descendants because BackToTopFab is mounted inside the shell tree, and confining the variable scope avoids leaking it onto external embeds (e.g. Storybook). The CSS `var(--playbar-height, 0px)` fallback on the FAB still works if it ever ends up outside the shell.
- Plan §T17 step 6 said reorganize the BookSummaryTab into a single 2-column grid. I added BOTH the mobile `<details>` outline AND the desktop `<aside>` rail, gating each via media query. This avoids needing JS-side breakpoint detection just to switch markup, and the duplicated component is cheap (it's only the TOC entries — markdown is rendered once in the body column).
- Plan §T17 step 1 says the empty-markdown TOC test should assert "single 'Top' entry". My implementation renders `<span class="toc-link toc-link--top">Top</span>` for that case (no anchor link); the test asserts exactly this.

## Verification
- `npm run test:unit -- --run src/components/book/__tests__/SummaryTOCRail.spec.ts` — 3/3 pass.
- Full frontend unit suite: 522/522 pass (was 519 after T16; +3 new).
- `npm run type-check` clean.
- `npm run build` clean (1.41s).
- Existing MarkdownRenderer.spec.ts (8 tests, including the 3 anchor tests from T16) still green — refactor to shared util preserved behavior exactly.

## Runtime evidence
The 3 SummaryTOCRail tests stub `IntersectionObserver` via `vi.stubGlobal` and assert: (1) 5 anchors emitted from a known h2/h3 mix with correct hrefs and a sticky nav element; (2) empty content → single "Top" item with no anchor; (3) firing the observer callback with `isIntersecting: true` for the second heading toggles `.toc-item--active` to that entry. The 522-test full suite covers the integration with BookSummaryTab unchanged from T13.
