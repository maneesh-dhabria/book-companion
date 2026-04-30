# Task 18 — F9b: Export 250 ms loader + clipboard text-only fallback

## Files touched
- frontend/src/views/BookOverviewView.vue (onExportClick + onCopyClick)
- frontend/src/views/__tests__/BookOverviewView.export.spec.ts (3 new tests + URL.createObjectURL polyfill in beforeEach)

## Decisions / deviations
- The "Copied (text only)" toast says exactly that, distinct from the
  primary success message — so users notice when images were stripped.
- STRIP_IMG_RE matches the inner Markdown image form `![alt](url)` and
  replaces it with `alt`. Nested brackets in alt text aren't realistic
  in our content (book summaries / annotations), so the regex stays
  simple per spec §11.2a.
- The spinner-floor test uses fake timers and asserts the spinner is
  present at 50 ms (export resolved) and absent at 270 ms (>=250 ms).

## Runtime evidence
- `npx vitest run BookOverviewView` — 12 / 12 pass.
- `npm run type-check` — clean.
