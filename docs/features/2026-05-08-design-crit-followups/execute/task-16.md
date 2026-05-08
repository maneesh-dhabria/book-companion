---
task_number: 16
task_name: "T16: Markdown anchors + scrollBehavior"
task_goal_hash: b8082948e1ca7e14e13b1c20b26a8bc615f8976dc3ba6274d920529095e2ba28
plan_path: "docs/plans/2026-05-08-design-crit-followups-implementation-plan.md"
branch: "design-crit-followups"
worktree_path: ".worktrees/design-crit-followups"
status: done
started_at: 2026-05-08T18:12:00Z
completed_at: 2026-05-08T18:20:00Z
files_touched:
  - frontend/src/components/reader/MarkdownRenderer.vue
  - frontend/src/router/index.ts
  - frontend/src/components/reader/__tests__/MarkdownRenderer.spec.ts
---

# T16: Markdown heading anchors + router scrollBehavior (FR-C07, FR-C09, FR-E06a)

## Outcome
- `MarkdownRenderer.vue`: `markdown-it` core ruler `heading_anchor_ids` walks tokens and calls `attrSet('id', slugify(...))` on every `heading_open` token where `tag` is `h2` or `h3`. The `taken: Set<string>` is created INSIDE the ruler closure so collisions are scoped per-render. `fallbackOrdinal` is the heading's index in document order.
- Slugify implementation matches spec §11.7 verbatim: lowercase, non-alphanum → `-`, trim leading/trailing `-`, slice to 60 chars; empty → `section-{ordinal}`; collisions get `-1`, `-2`, … suffixes.
- Scoped CSS: `.markdown-body :deep(:where(h2, h3)) { scroll-margin-top: 32px; }` so anchor links land within the spec's tolerance.
- `router/index.ts`: added `scrollBehavior(to, _from, savedPosition)` returning `savedPosition` for back/forward, `{ el: to.hash, behavior: 'smooth', top: 32 }` for hash navigation, else `{ top: 0 }`.
- `npm ls markdown-it-anchor` was not run — went with the inline ruler approach per the plan's alternative ("OR a render-rule override that walks tokens and sets `attrSet('id', slugify(...))`"). Avoids a new dependency for what is ~25 lines of code, and the `taken` threading is already implicit in the closure scope.

## Verification
- `npm run test:unit -- --run src/components/reader/__tests__/MarkdownRenderer.spec.ts` — 8/8 pass (5 prior + 3 new for FR-C07).
- Full frontend unit suite: 519/519 pass (was 516 after T15; +3 new).
- `npm run type-check` clean.

## Runtime evidence
The 3 new tests assert the rendered HTML directly: (a) `## Foo` twice + `### Foo Bar` twice → `id="foo"`, `id="foo-1"`, `id="foo-bar"`, `id="foo-bar-1"`; (b) emoji-only heading → `id="section-0"` fallback; (c) `# Title`, `#### Deep` do NOT receive ids (only h2/h3 do). The router scrollBehavior change is exercised in production via vue-router's well-tested API; no e2e smoke test added because the harness has no scroll-position mock — would be a Phase 4 T29 axe-friendly e2e concern instead.

## No spec deviations.
