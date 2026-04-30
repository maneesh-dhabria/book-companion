# Upload + Summarize Flow — UX Fixes Wireframes (2026-04-30)

Static HTML wireframes attached to [`docs/requirements/2026-04-30-upload-summarize-flow-ux-fixes.md`](../../requirements/2026-04-30-upload-summarize-flow-ux-fixes.md).

Open [`index.html`](./index.html) in a browser for the full set, or click any file directly. Wireframes are self-contained except for the shared `_shared.css`.

## Components

| # | File | Component | Maps to |
|---|------|-----------|---------|
| 01 | `01-step1-upload.html` | Step 1 upload — per-file card with two-phase indicator | Issue #1 · G1 · D2 |
| 02 | `02-step2-structure-editor.html` | Step 2 structure editor — table + multi-select toolbar | Issue #2 · G2 · D3 · D13 · D14 |
| 03 | `03-split-modal.html` | Split modal with 3 modes (heading / paragraph / cursor) | Issue #2 · D5 · OQ6 |
| 04 | `04-step3-preset-with-cli-preflight.html` | Step 3 preset picker + blocked state on CLI preflight failure | Issue #4 · G6 · D9 |
| 05 | `05-step4-live-progress.html` | Step 4 live progress card + completion success card | Issue #3 · G4 · D7 |
| 06 | `06-persistent-processing-indicator.html` | Bottom bar with queue badge + expandable queue panel | Issue #3 + multi-book · G5 · D8 |
| 07 | `07-settings-llm-validation.html` | Settings → LLM with persistent banner + inline save error | Issue #4 · D9 · E1a/b |
| 08 | `08-edit-structure-post-summary.html` | Edit Structure tab on Book Detail + invalidation confirm | Issue #2 · G3 · D4 · D6 |

## Visual language

- Apple-system aesthetic: `system-ui` font, soft borders, light shadows
- Dark mode via `prefers-color-scheme`
- Same palette and spacing tokens as existing wireframes in `docs/wireframes/2026-04-10_v2_web_interface/`
- Each wireframe shows multiple states (default / active / error / completed) inline so reviewers can see the variants without clicking through

## Notes for /spec

- OQ1 (settings hard-block vs warn): wireframe 07 shows the warn-with-escape-hatch variant
- OQ2 (cancel running job): wireframe 06 shows running-Cancel disabled
- OQ3 (browser refresh during Step 4): not wireframed — left for /spec
- OQ4 (upload progress accuracy): wireframe 01 commits to determinate-during-upload + indeterminate-during-parse
- OQ5 (Edit Structure surface IA): wireframe 08 commits to a tab on the book detail view
- OQ6 (split preview depth): wireframe 03 commits to title + first-line snippet + char count (lighter variant)

These are wireframe-level commitments, not requirements-doc commitments. /spec can revisit before locking design.
