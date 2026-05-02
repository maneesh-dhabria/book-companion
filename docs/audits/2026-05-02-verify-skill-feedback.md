# Feedback for the `/verify` skill author

## Context

Ran `/verify` on a 22-task UX cohesion bundle (53 files, 18 user-facing ACs across Book Detail, Section Reader, app shell, 4 Settings pages). Static checks + behavioral DOM probes via Playwright MCP all came back green and I declared Phase 4 complete. The user then asked: "Did you verify UX or only functionality?" — and screenshots immediately surfaced three significant visual regressions the skill had marked as **Verified**:

- A primary CTA (`<a class="btn-primary">`) had no CSS rule → rendered as unstyled body text
- A new tab strip (`.book-tabs`/`.book-tab`) had no CSS rules → "OverviewSummarySections" rendered as run-on text with no separators or active indicator
- Reading Settings theme cards passed identical bg/fg to every card and laid them out in a width-less flex container → all six cards rendered as ~49px white labels instead of the bordered, theme-colored cards the popover shows

All three would have been visible in a single screenshot. None showed up in DOM-attribute probes (tab count was 3, button had `cursor: pointer`, class names matched).

## Root cause

Phase 4's evidence-type allowlist for "UI surface" reads:

> "Playwright MCP screenshot, `browser_evaluate` DOM assertion, or a specific test file covering the rendered output"

The "or" in that line is load-bearing — and wrong. `browser_evaluate` queries (counts, class names, computed styles on individual properties) verify **wiring**, not **appearance**. They tell you the structure exists and that *some* style applies; they don't tell you the rendered surface looks like the spec/wireframe expects. A unit test covering "the rendered output" similarly verifies behavior, not pixels.

The skill currently treats these as interchangeable evidence types. They're not. A DOM probe and a screenshot answer different questions:

| Probe | Answers |
|---|---|
| `tabs.length === 3` | "Did the developer render three tab elements?" |
| `getComputedStyle(tab).cursor === 'pointer'` | "Is *one* style applied?" |
| Screenshot | "Does this look like a tab strip?" |

When the spec is a UX cohesion / polish bundle (every AC is some variant of "this should look like X"), the DOM-probe-only path is structurally insufficient — it cannot fail on the very class of defect the bundle was written to fix.

## Suggested structural change

In Phase 4's entry-gate evidence allowlist, **split UI evidence into two required types when the AC is a visual/polish AC**:

- **Structural** evidence: DOM probe, computed-style assertion, or test (verifies wiring exists)
- **Visual** evidence: a screenshot of the rendered surface, captured *after* the relevant interaction (verifies it looks right)

For UI-surface ACs, both must be produced; one is not a substitute for the other. The screenshot's role is not decorative — it is the only artifact that can detect "class is applied but no CSS rule exists," "container has no width so cards collapse," "wrong CSS variable name silently falls through to default," and similar failures that pass every behavioral check.

Two specific tweaks would have caught everything in this session:

1. **Mandate a full-page screenshot per affected surface** at Phase 4 entry, before the per-AC checks run. Reviewing the screenshot is itself a checklist item: "Does each FR's artifact look like the wireframe / spec text? List anything that doesn't." This forces the agent to *look* at the page once with fresh eyes instead of going straight to per-FR DOM queries.

2. **Add a Phase 4 red-flag entry** for the specific failure mode I hit: "I queried the DOM and the structure is right." Reality: structure ≠ rendered UX. If the AC says anything about appearance — buttons, tabs, cards, spacing, theme, hover — a screenshot is required, not optional.

A smaller, related point: when a unit test or DOM probe does pass, the skill currently treats that as sufficient even for visual ACs. The three-state table in Phase 5 ("Verified / NA-alt-evidence / Unverified") could explicitly disallow `Verified` for a visual AC unless screenshot evidence is cited in the row. That would force the structural→visual split to surface in the compliance table, not just in the entry gate.

## Smaller observations from this run

- The Phase 4 entry gate did its job for "did I attempt verification?" — every AC had a todo. It did not catch "did I attempt the *right* verification?" The evidence-type table needs to encode the difference between structural and visual evidence; without that, a thorough agent can dutifully tick every todo with the wrong artifact.
- The "noted but not blocking" 50–74 confidence bucket in Phase 3 worked well — three findings landed there and didn't derail the run, but were preserved for the report.
- The Phase 0 instruction to read `~/.pmos/learnings.md` was useful (the entry about pre-existing main-branch lint debt prevented a false static-failure report). Worth keeping.

## TL;DR

For UX/visual bundles, structural and visual evidence are not interchangeable. Make screenshots required (not optional / not substitutable) for any AC whose spec text describes appearance. The current evidence allowlist's `or` clause silently downgrades visual ACs to structural-only verification, and a thorough agent following the skill verbatim will still miss every "class applied but unstyled" defect.
